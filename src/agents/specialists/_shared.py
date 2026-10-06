"""Helpers shared by the document agents: prompt building, the tool loop, quality gate and post-processing.

The model-call functions the tests replace are imported here; agents reach them as ``_shared.<name>``.
"""

from __future__ import annotations

import logging
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from src.agents.base_agent import AgentContext
from src.prompts.prompt_hygiene import UNTRUSTED_SKILL_SYSTEM_NOTE, wrap_untrusted
from src.core.config import settings
from src.core.state import ProcessModel
from src.llm.claude import (  # noqa: F401 — the agents reach these as _shared.<name>
    claude_generate,
    claude_generate_json,
    claude_generate_with_thinking,
    is_claude_enabled,
)
from src.agents.tool_agent import run_subagent_tool_loop
from src.core.observability.metrics import increment
from src.agents.process_extraction import extract_process_model
from src.tools.registry import anthropic_tool_definitions, default_tools_for_output_type, tool_names_for_skill
from src.agents.specialists.pptx_slide_batching import _generate_slides_batched  # noqa: F401 — reached by the agents as _shared._generate_slides_batched

_LOG = logging.getLogger(__name__)


_SWARM_READ_TOOLS: tuple[str, ...] = (
    "swarm_list_tasks",
    "swarm_list_messages",
    "swarm_send_message",
)


_SWARM_LEAD_ONLY_TOOLS: tuple[str, ...] = (
    "swarm_create_task",
    "swarm_update_task",
    "swarm_broadcast",
)


_SWARM_TOOL_NAMES: tuple[str, ...] = _SWARM_READ_TOOLS + _SWARM_LEAD_ONLY_TOOLS  # backward compat


_DEBUG_LOG_PATH = Path(settings.advise_workbench_coordinator_debug_log).expanduser() if str(settings.advise_workbench_coordinator_debug_log or "").strip() else None


_DEBUG_SESSION_ID = "a9841a"


def _append_conversation_digest_block(user: str, ctx: AgentContext) -> str:
    extra_parts: list[str] = []
    d = (ctx.conversation_digest or "").strip()
    if d:
        cap = max(0, int(settings.subagent_conversation_digest_max_chars))
        if cap > 0:
            extra_parts.append(f"## Confirmed conversation (digest)\n{d[:cap]}")

    # Shared enrichment is now passed via AgentContext; include compact hints for all agents.
    if ctx.enrichment is not None:
        audience = ctx.get_audience_hints().strip()
        risk = ctx.get_risk_focus().strip()
        value = ctx.get_value_emphasis().strip()
        analytics = getattr(ctx.enrichment, "process_analytics", None)
        metrics: list[str] = []
        if analytics is not None:
            metrics.append(f"steps={getattr(analytics, 'steps_count', 0)}")
            metrics.append(f"roles={getattr(analytics, 'roles_count', 0)}")
            metrics.append(f"decisions={getattr(analytics, 'decision_points', 0)}")
        lines = [x for x in [audience, risk, value, ("Process analytics: " + ", ".join(metrics)) if metrics else ""] if x]
        if lines:
            extra_parts.append("## Shared enrichment\n" + "\n".join(f"- {ln}" for ln in lines))

    if not extra_parts:
        return user
    cap = max(0, int(settings.subagent_conversation_digest_max_chars))
    if cap <= 0 and d:
        return user
    bundle = "\n\n".join(extra_parts).strip()
    wrapped = wrap_untrusted("conversation_digest_and_enrichment", bundle)
    return f"{user}\n\n{wrapped}\n" if wrapped else user


def _session_debug_log(*, run_id: str | None, hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    if _DEBUG_LOG_PATH is None:
        return
    try:
        payload = {
            "sessionId": _DEBUG_SESSION_ID,
            "runId": str(run_id or ""),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:  # noqa: S110 — best-effort, non-fatal
        pass


def _model(ctx: AgentContext) -> ProcessModel:
    return ctx.process_model or extract_process_model(ctx.raw_text, ctx.assembled_context)


def _pref(ctx: AgentContext, key: str, default: str) -> str:
    prefs = ctx.output_type_representations or {}
    if not isinstance(prefs, dict):
        return default
    value = str(prefs.get(key) or "").strip().lower()
    return value or default


def _skill_instruction(ctx: AgentContext, output_type: str) -> str:
    all_instr = ctx.skill_instructions_by_output or {}
    if not isinstance(all_instr, dict):
        return ""
    text = str(all_instr.get(output_type) or "").strip()
    return text


def _primary_skill(ctx: AgentContext) -> dict | None:
    sc = ctx.skill_card if isinstance(ctx.skill_card, dict) else {}
    primary = sc.get("primary_skill_by_output_type") if isinstance(sc, dict) else None
    if not isinstance(primary, dict):
        return None
    card = primary.get(ctx.output_type)
    return card if isinstance(card, dict) else None


# Map skill freedom_level to Claude temperature.
_FREEDOM_TEMPERATURE: dict[str, float] = {
    "low": 0.1,   # deterministic, policy-bound output
    "medium": 0.3,  # balanced creativity/accuracy
    "high": 0.7,   # exploratory, narrative-rich output
}


def _render_zoned_system_prompt(
    *,
    zone1_stable: list[str],
    zone2_run_specific: list[str],
    zone3_dynamic: list[str],
) -> str:
    """
    Enforce deterministic prompt ordering for cache efficiency:
    Zone 1 (stable) -> Zone 2 (run metadata) -> Zone 3 (dynamic directives).
    """
    z1 = "\n".join([p for p in zone1_stable if p and str(p).strip()]).strip()
    z2 = "\n".join([p for p in zone2_run_specific if p and str(p).strip()]).strip()
    z3 = "\n".join([p for p in zone3_dynamic if p and str(p).strip()]).strip()
    blocks = [
        "### Zone1_StableSkillInstructions",
        z1,
        "",
        "### Zone2_RunMetadata",
        z2,
        "",
        "### Zone3_DynamicDirectives",
        z3,
    ]
    return "\n".join(blocks).strip()


@dataclass
class _SkillBuild:
    """Result of _build_system_from_skill — groups all skill-derived call parameters."""
    system: str
    temperature: float
    max_rounds: int | None  # None → use global settings.subagent_tool_max_rounds


def _append_archetype_prompt(sb: _SkillBuild, ctx: AgentContext, output_type: str) -> _SkillBuild:
    from src.agents.deliverable_archetype import archetype_prompt_block

    block = archetype_prompt_block(
        ctx.deliverable_archetype or "process_doc",  # type: ignore[arg-type]
        output_type,
    )
    if not block:
        return sb
    return _SkillBuild(system=sb.system + block, temperature=sb.temperature, max_rounds=sb.max_rounds)


def _build_system_from_skill(
    ctx: AgentContext,
    output_type: str,
    *,
    fallback_system: str,
    fallback_temperature: float = 0.3,
) -> _SkillBuild:
    """
    Build a rich system prompt from the skill card rather than hard-coding
    agent identity in sub-agent functions.

    In Cowork, the skill card IS the agent's identity — its display_name,
    prompt_instructions, workflow_steps, and acceptance_checks together
    form the complete system prompt.  Editing a SKILL.md file changes agent
    behaviour without touching Python code.

    Gap implementations:
      - Gap 1: prompt_instructions injected into SYSTEM (not USER) turn
      - Gap 3: feedback_loop length drives per-skill max_rounds cap
      - Acceptance criteria included as explicit quality gate in system prompt
      - freedom_level drives temperature
    """
    primary = _primary_skill(ctx)
    if not primary:
        # Even in fallback mode, append the tool usage policy so agents know
        # to call retrieve_context and validators before returning output.
        system_with_policy = _render_zoned_system_prompt(
            zone1_stable=[fallback_system.strip()],
            zone2_run_specific=[],
            zone3_dynamic=[_TOOL_USAGE_POLICY.strip()],
        )
        return _SkillBuild(system=system_with_policy, temperature=fallback_temperature, max_rounds=None)

    zone1_parts: list[str] = []
    zone2_parts: list[str] = []
    zone3_parts: list[str] = []

    # 1. Agent identity from skill metadata
    display_name = str(primary.get("display_name") or primary.get("id") or "Specialist")
    description = str(primary.get("description") or "").strip()
    zone1_parts.append(f"You are {display_name}.")
    if description:
        desc_wrapped = wrap_untrusted("skill_description", description, max_chars=4000)
        zone1_parts.append(desc_wrapped if desc_wrapped else description)

    # 2. Core craft instructions — the SKILL.md body (prompt_instructions).
    #    These go into the SYSTEM prompt so they define the agent's persona
    #    and mandate, not just a user-side hint.
    prompt_instructions = _skill_instruction(ctx, output_type)
    if prompt_instructions:
        zone1_parts.append("")
        instr_wrapped = wrap_untrusted("skill_prompt_instructions", prompt_instructions, max_chars=48_000)
        zone1_parts.append(instr_wrapped if instr_wrapped else prompt_instructions)

    # 3. Structured reasoning sequence from workflow_steps
    workflow_steps = primary.get("workflow_steps")
    if isinstance(workflow_steps, list) and workflow_steps:
        zone1_parts.append("")
        zone1_parts.append("Follow this reasoning sequence:")
        seq_lines = "\n".join(f"  {i}. {step}" for i, step in enumerate(workflow_steps, 1))
        seq_wrapped = wrap_untrusted("skill_workflow_steps", seq_lines, max_chars=16_000)
        zone1_parts.append(seq_wrapped if seq_wrapped else seq_lines)

    # 4. Gap 3 — feedback_loop drives max_rounds and self-correction guidance.
    #    Each feedback_loop entry = one tool-use round budget.
    feedback_loop = primary.get("feedback_loop")
    max_rounds: int | None = None
    if isinstance(feedback_loop, list) and len(feedback_loop) >= 2:
        max_rounds = max(len(feedback_loop), 2)
        zone3_parts.append("")
        zone3_parts.append("Self-correction loop — use your available tools across these rounds:")
        fb_lines = "\n".join(f"  Round {i}: {step}" for i, step in enumerate(feedback_loop, 1))
        fb_wrapped = wrap_untrusted("skill_feedback_loop", fb_lines, max_chars=8000)
        zone3_parts.append(fb_wrapped if fb_wrapped else fb_lines)
        zone3_parts.append(
            "Use qa_validator and style_enforcer tools where available to complete checking rounds. "
            "Produce the final output only after the loop is complete."
        )

    # 5. Quality gate from acceptance_checks
    acceptance_checks = primary.get("acceptance_checks")
    if isinstance(acceptance_checks, list) and acceptance_checks:
        zone3_parts.append("")
        zone3_parts.append("Your output MUST satisfy ALL of the following acceptance criteria:")
        chk_lines = "\n".join(f"  - {check}" for check in acceptance_checks)
        chk_wrapped = wrap_untrusted("skill_acceptance_checks", chk_lines, max_chars=8000)
        zone3_parts.append(chk_wrapped if chk_wrapped else chk_lines)
        zone3_parts.append(
            "After drafting, re-read your output and verify each criterion is met. "
            "Fix anything that fails before returning."
        )

    # 5.5 Companion files — domain reference material co-located with the skill.
    #     These are loaded from disk and injected into the system prompt so that
    #     leading practices, templates, and checklists are always available to the
    #     agent without requiring a separate tool call.
    companion_files_list = primary.get("companion_files")
    skill_md_path = primary.get("_skill_md_path")
    if isinstance(companion_files_list, list) and companion_files_list and skill_md_path:
        skill_dir = Path(skill_md_path).parent
        loaded_companions: list[str] = []
        for cf in companion_files_list:
            if not isinstance(cf, str) or not cf.strip():
                continue
            try:
                cf_path = (skill_dir / cf.strip()).resolve()
                content = cf_path.read_text(encoding="utf-8").strip()
                if content:
                    safe_name = ("".join(c if c.isalnum() or c in ".-_" else "_" for c in cf_path.name))[:120] or "companion"
                    cw = wrap_untrusted(f"skill_companion_{safe_name}", content, max_chars=48_000)
                    loaded_companions.append(f"### Reference: {cf_path.name}\n\n{cw if cw else content}")
            except OSError:
                pass
        if loaded_companions:
            zone1_parts.append("")
            zone1_parts.append(
                "Domain reference material (use this knowledge when generating — "
                "it contains leading practices, quality checklists, and conventions "
                "specific to this skill):"
            )
            for companion in loaded_companions:
                zone1_parts.append("")
                zone1_parts.append(companion)

    # 5.6 Inline post-processor rules — merge brand/tone guidelines from
    #     post_processor skills into the primary generation prompt instead of
    #     running a separate Claude call.  The post-processor instructions are
    #     generic guardrails (tighten titles, brand compliance) that don't need
    #     to see "naive" output first.  Inlining them saves a full API round-trip.
    sc_for_pp = ctx.skill_card if isinstance(ctx.skill_card, dict) else {}
    post_processors: list[dict] = (
        (sc_for_pp.get("post_processor_skills_by_output_type") or {}).get(output_type) or []
    )
    if post_processors:
        zone3_parts.append("")
        zone3_parts.append(
            "Brand & tone rules (apply during generation — do NOT wait for a second pass):"
        )
        zone3_parts.append(
            "Preserve facts, numbers, and process names accurately. "
            "Tighten titles, bullets, descriptions, and table cells for clarity and conciseness."
        )
        for pp_skill in post_processors:
            pp_name = str(pp_skill.get("display_name") or pp_skill.get("id") or "Brand")
            pp_instr = str(pp_skill.get("prompt_instructions") or "").strip()
            if pp_instr:
                pp_label = "".join(c if c.isalnum() or c in ".-_" else "_" for c in pp_name)[:64] or "post_processor"
                pp_wrapped = wrap_untrusted(f"post_processor_{pp_label}", pp_instr, max_chars=16_000)
                zone3_parts.append(f"  ## {pp_name}")
                zone3_parts.append(f"  {pp_wrapped}" if pp_wrapped else f"  {pp_instr}")

    # 6. Tool invocation policy — agents must be told when to call tools vs. generate
    #    directly. Without this guidance agents skip retrieve_context and generate
    #    from the ProcessModel JSON alone, missing all project-specific context.
    zone3_parts.append("")
    zone3_parts.append("Tool usage policy (follow in order):")
    zone3_parts.append(
        "  1. BEFORE generating: call retrieve_context with a query describing the process "
        "domain (e.g. 'client onboarding compliance KYC'). Use returned chunks to ground "
        "your output in project-specific facts rather than generic content."
    )
    zone3_parts.append(
        "  2. BEFORE generating: if search_leading_practices is available, call it with "
        "the process name to retrieve industry reference material."
    )
    zone3_parts.append(
        "  3. BEFORE generating: if process_model_query is available, call it with "
        "filter_type='summary' first to confirm step/role counts, then use specific "
        "filter types (e.g. 'steps_by_role', 'all_decisions') to fetch only the data "
        "you need rather than re-reading the full ProcessModel JSON."
    )
    zone3_parts.append(
        "  4. AFTER first draft: save the draft with save_draft(key='v1', content=...) "
        "before running validators. This way you can load and revise rather than "
        "regenerate from scratch if validation finds issues."
    )
    zone3_parts.append(
        "  5. AFTER first draft: call the structural validator for your output type — "
        "document_builder, table_builder, diagram_builder, or outline_validator. "
        "Fix every CRITICAL and HIGH issue, then call qa_validator to get a quality score."
    )
    zone3_parts.append(
        "  6. AFTER revision: if cross_reference_checker is available, call it to verify "
        "that all role names and step names in the output match the ProcessModel."
    )
    zone3_parts.append(
        "  7. If format_table is available and your output includes a tabular section, "
        "call format_table to build the table deterministically rather than manually."
    )
    zone3_parts.append(
        "  8. Reserve web_search for regulatory standards, external benchmarks, or "
        "terminology definitions not in the project context. Do NOT search for facts "
        "already present in retrieve_context results or the ProcessModel."
    )
    plan = ctx.plan_payload if isinstance(ctx.plan_payload, dict) else {}
    strategy = plan.get("selected_strategy") if isinstance(plan.get("selected_strategy"), dict) else {}
    option_id = str(strategy.get("option_id") or "").strip()
    if option_id:
        zone2_parts.append(f"SelectedStrategyOption: {option_id}")
    regen = str(plan.get("regeneration_directive") or "").strip()
    if regen:
        regen_wrapped = wrap_untrusted("regeneration_directive", regen, max_chars=800)
        zone2_parts.append(f"RegenerationDirective:\n{regen_wrapped}" if regen_wrapped else f"RegenerationDirective: {regen[:800]}")
    zone1_fingerprint = hashlib.sha256("\n".join(zone1_parts).encode("utf-8")).hexdigest()[:16]
    zone2_parts.append(f"Zone1Fingerprint: {zone1_fingerprint}")

    # 7. Temperature from freedom_level
    freedom = str(primary.get("freedom_level") or "medium").strip().lower()
    temperature = _FREEDOM_TEMPERATURE.get(freedom, fallback_temperature)

    rendered = _render_zoned_system_prompt(
        zone1_stable=zone1_parts,
        zone2_run_specific=zone2_parts,
        zone3_dynamic=zone3_parts,
    )
    return _SkillBuild(
        system=f"{UNTRUSTED_SKILL_SYSTEM_NOTE}{rendered}",
        temperature=temperature,
        max_rounds=max_rounds,
    )


def _recover_latest_draft(project_id: str, run_id: str, agent_id: str) -> str | None:
    """
    Fallback: return the content of the most recently modified draft saved by
    ``save_draft`` for this agent/run combination.  Used when the tool loop's
    final text is chatter rather than a document.
    """
    try:
        from src.core.storage import workspace_path

        base = workspace_path(project_id)
        candidates: list[Any] = []
        for draft_dir in [
            base / "runs" / run_id / "drafts" if run_id else None,
            base / "drafts",
        ]:
            if draft_dir is None or not draft_dir.is_dir():
                continue
            for f in draft_dir.glob(f"{agent_id}_*.md"):
                candidates.append(f)
            # Also accept drafts where the agent prefixed differently (model can
            # supply its own agent_id to save_draft); pick any .md in the run drafts
            # dir if nothing matched the exact prefix.
            if not candidates and draft_dir == base / "runs" / run_id / "drafts":
                candidates = list(draft_dir.glob("*.md"))
        if not candidates:
            return None
        # Prefer the lexicographically last key so v2 > v1, final > v2, etc.
        candidates.sort(key=lambda p: p.name)
        latest = candidates[-1]
        content = latest.read_text(encoding="utf-8").strip()
        return content if content.lstrip().startswith("#") else None
    except Exception:  # noqa: BLE001
        return None


def _run_subagent_tool_loop_text(
    ctx: AgentContext,
    *,
    agent_id: str,
    system: str,
    user: str,
    temperature: float = 0.3,
    max_rounds: int | None = None,
) -> str | None:
    """Run iterative tool loop; return final assistant text or None on failure / missing project."""
    try:
        primary = _primary_skill(ctx)
        names = tool_names_for_skill(primary) if primary else []
        defaults = default_tools_for_output_type(ctx.output_type)
        if not names:
            # No skill active or skill declared no tools → use output-type defaults.
            names = defaults
        else:
            # Merge: add any default tools not already in the skill-declared list.
            # This ensures that phantom tool slots (e.g. document_builder declared in
            # skill but not yet in registry) are filled by equivalent registry tools,
            # rather than leaving the agent with a narrower-than-intended tool set.
            for t in defaults:
                if t not in names:
                    names = list(names) + [t]
        if getattr(settings, "swarm_orchestration_enabled", False):
            from src.extensions.swarm.swarm import SWARM_LEAD_ONLY_TOOLS as _SLO, get_teammate_role
            _rid = str(ctx.run_id or "")
            _tm = str(ctx.swarm_teammate_id or "")
            _role = get_teammate_role(run_id=_rid, teammate_id=_tm) if _rid and _tm else "worker"
            _swarm_names = _SWARM_READ_TOOLS + (_SWARM_LEAD_ONLY_TOOLS if _role == "lead" else ())
            for n in _swarm_names:
                if n not in names:
                    names.append(n)
        tool_defs = anthropic_tool_definitions(names)
        if not tool_defs:
            return None
        pid = str(ctx.project_id or "").strip()
        if not pid:
            return None
        from src.extensions.swarm.swarm import SWARM_LEAD_PREAMBLE, SWARM_WORKER_PREAMBLE, get_teammate_role as _gtr

        sys_prompt = system
        if getattr(settings, "swarm_orchestration_enabled", False):
            _rid2 = str(ctx.run_id or "")
            _tm2 = str(ctx.swarm_teammate_id or "")
            _role2 = _gtr(run_id=_rid2, teammate_id=_tm2) if _rid2 and _tm2 else "worker"
            _preamble = SWARM_LEAD_PREAMBLE if _role2 == "lead" else SWARM_WORKER_PREAMBLE
            sys_prompt = f"{_preamble}\n\n{system}"
        nc: dict[str, Any] = {
            "project_id": pid,
            "user_id": ctx.user_id,
            "process_model": ctx.process_model,
            "run_id": str(ctx.run_id or ""),
            "agent_id": agent_id,
        }
        if ctx.swarm_teammate_id:
            nc["swarm_teammate_id"] = ctx.swarm_teammate_id
        out = run_subagent_tool_loop(
            system=sys_prompt,
            user=user,
            project_id=pid,
            tool_defs=tool_defs,
            native_context=nc,
            emit_event=ctx.emit_event,
            agent_id=agent_id,
            run_id=str(ctx.run_id or ""),
            temperature=temperature,
            max_rounds=max_rounds,  # None → global default from settings
        )
        text = (out.get("text") or "").strip()
        # Guard: if the final text is not a document (doesn't start with a '#' heading),
        # the agent finished with status chatter instead of content.  Fall back to the
        # most recently saved draft so the deliverable is never corrupted by inner monologue.
        if text and not text.lstrip().startswith("#"):
            recovered = _recover_latest_draft(pid, str(ctx.run_id or ""), agent_id)
            if recovered:
                _LOG.warning(
                    "subagent %r final text is not a document (starts: %r); "
                    "recovering from latest draft",
                    agent_id, text[:80],
                )
                text = recovered
        return text if text else None
    except Exception:  # noqa: BLE001
        return None


def _apply_quality_gate(
    ctx: AgentContext,
    output_type: str,
    content: str,
    *,
    system: str,
    temperature: float,
) -> str:
    """
    Compare output quality against the skill's quality_thresholds[output_type].

    If the qa_validator score falls below the declared threshold, one remediation
    pass is requested from Claude with the list of issues injected into the prompt.
    Returns the (possibly improved) content; never raises.
    """
    if not content.strip() or not is_claude_enabled():
        return content

    primary = _primary_skill(ctx)
    if not primary:
        return content

    thresholds = primary.get("quality_thresholds") or {}
    threshold = float((thresholds or {}).get(output_type) or 0)
    if threshold <= 0:
        return content

    # In-process qa_validator call (no tool-loop overhead for the gate check)
    try:
        from src.tools.registry import qa_validator as _qa_validator
        qa_result = _qa_validator(text=content, output_type=output_type)
    except Exception:  # noqa: BLE001
        return content

    score = float(qa_result.get("score") or 1.0)
    issues: list[str] = qa_result.get("issues") or []

    if score >= threshold or not issues:
        return content  # ✅ passes gate

    # Emit a quality gate event if an emitter is available
    emit = ctx.emit_event
    if emit:
        try:
            emit("quality_gate", {
                "output_type": output_type,
                "score": score,
                "threshold": threshold,
                "issues": issues,
                "action": "remediation_pass",
            })
        except Exception:  # noqa: BLE001, S110, SIM105
            pass

    remediation_prompt = (
        f"Your output did not meet the quality threshold "
        f"(score {score:.2f} < required {threshold:.2f}).\n\n"
        "Issues to fix:\n"
        + "\n".join(f"  - {issue}" for issue in issues)
        + "\n\nPlease revise to address ALL issues listed above. "
        "Return the complete corrected output only — no explanations."
        f"\n\nPrevious output:\n{content}"
    )
    try:
        if output_type == "pptx":
            improved_obj = claude_generate_json(
                system=(
                    system
                    + "\n\nThe revision MUST be one JSON object: {\"slides\": [...]} matching the prior schema. "
                    "No markdown fences, no commentary."
                ),
                user=remediation_prompt,
                temperature=temperature,
                max_tokens=8192,
            )
            if isinstance(improved_obj, dict) and isinstance(improved_obj.get("slides"), list):
                return json.dumps({"slides": improved_obj["slides"]}, ensure_ascii=False)
        else:
            improved = claude_generate(
                system=system,
                user=remediation_prompt,
                temperature=temperature,
                max_tokens=2500,
            )
            if isinstance(improved, str) and improved.strip():
                return improved
    except Exception:  # noqa: BLE001, S110
        pass
    return content


def _run_post_processor(ctx: AgentContext, content: str) -> str:
    """
    Apply post-processor skills (role=post_processor) to the primary output.

    Post-processors such as brand_guidelines_v1 are applied AFTER the primary
    agent generates content — they refine tone, styling, and brand compliance
    without being mixed into the generation prompt.

    Returns the refined content, or the original if no post-processors are
    configured for this output type or Claude is unavailable.
    """
    if not content.strip() or not is_claude_enabled():
        return content

    sc = ctx.skill_card if isinstance(ctx.skill_card, dict) else {}
    post_processors: list[dict] = (sc.get("post_processor_skills_by_output_type") or {}).get(ctx.output_type) or []
    if not post_processors:
        return content

    # Collect instructions and workflow_steps from all post-processors for this output
    system_parts: list[str] = ["You are a post-processing specialist."]
    for skill in post_processors:
        name = str(skill.get("display_name") or skill.get("id") or "Brand Stylist")
        instr = str(skill.get("prompt_instructions") or "").strip()
        steps = skill.get("workflow_steps")
        checks = skill.get("acceptance_checks")

        system_parts.append(f"\n## {name}")
        if instr:
            system_parts.append(instr)
        if isinstance(steps, list) and steps:
            system_parts.append("\nFollow these steps:")
            for i, s in enumerate(steps, 1):
                system_parts.append(f"  {i}. {s}")
        if isinstance(checks, list) and checks:
            system_parts.append("\nEnsure the output satisfies:")
            for c in checks:
                system_parts.append(f"  - {c}")

    system_parts.append(
        "\nPreserve ALL information from the original. "
        "Only improve tone, style, and brand compliance. "
        "Return the complete refined output only."
    )

    system = "\n".join(system_parts)
    user = (
        f"Refine the following {ctx.output_type} output according to the style guidelines above.\n\n"
        f"CONTENT:\n{content}"
    )

    emit = ctx.emit_event
    skill_label = ", ".join(str(s.get("display_name") or s.get("id") or "") for s in post_processors)
    if emit:
        try:
            emit(
                "step",
                {
                    "status": "post_processing_start",
                    "skill_name": skill_label,
                    "output_type": ctx.output_type,
                },
            )
        except Exception:  # noqa: BLE001, S110, SIM105
            pass

    try:
        refined = claude_generate(system=system, user=user, temperature=0.1, max_tokens=3000)
        out = refined if isinstance(refined, str) and refined.strip() else content
        if emit:
            try:
                emit(
                    "step",
                    {
                        "status": "post_processing_done",
                        "skill_name": skill_label,
                        "output_type": ctx.output_type,
                    },
                )
            except Exception:  # noqa: BLE001, S110, SIM105
                pass
        return out
    except Exception:  # noqa: BLE001
        if emit:
            try:
                emit(
                    "step",
                    {
                        "status": "post_processing_done",
                        "skill_name": skill_label,
                        "output_type": ctx.output_type,
                        "error": True,
                    },
                )
            except Exception:  # noqa: BLE001, S110, SIM105
                pass
        return content


def _run_pptx_post_processor(ctx: AgentContext, slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply brand / post_processor skills to slide JSON (same slide count and slide_types).

    When a primary skill is present, post-processor rules are already inlined into
    the primary generation prompt by _build_system_from_skill (Section 5.6), so this
    separate Claude call is skipped — saving a full API round-trip.
    """
    if not slides or not is_claude_enabled():
        return slides
    sc = ctx.skill_card if isinstance(ctx.skill_card, dict) else {}
    post_processors: list[dict] = (sc.get("post_processor_skills_by_output_type") or {}).get("pptx") or []
    if not post_processors:
        return slides
    # Skip separate post-processing when rules were already inlined into the
    # primary generation prompt (primary skill present → rules in Zone 3).
    if _primary_skill(ctx):
        return slides

    _pp_company = getattr(ctx.branding, "company_name", None) or "Deloitte"
    system_parts: list[str] = [
        "You post-process a slide deck JSON blueprint for brand tone, clarity, and consistency.",
        "Input and output: one JSON object {\"slides\": [...]} only — no markdown fences or commentary.",
        "Preserve the same number of slides in the same order; do not change any slide_type value.",
        "Keep facts, numbers, and process names accurate; tighten titles, bullets, descriptions, and table cells.",
        "HEADLINE QUALITY: Scan every slide title. Convert any topic label (a name that merely describes "
        "content — e.g., 'Overview', 'Approach', 'Risks', 'Current State', 'Three Pillars') into an "
        "assertion headline (a claim that states an insight — e.g., 'Manual Work Consumes 40% of Capacity', "
        "'Four Failure Modes That Derail Programs Like This'). Preserve all facts and numbers.",
        f"BRAND VOICE: This is a {_pp_company} executive deck. All titles and bullets must read as "
        "confident, data-grounded points of view — no hedge words ('may', 'could potentially'), "
        "no passive voice on impact claims.",
    ]
    for skill in post_processors:
        name = str(skill.get("display_name") or skill.get("id") or "Brand")
        instr = str(skill.get("prompt_instructions") or "").strip()
        system_parts.append(f"\n## {name}")
        if instr:
            system_parts.append(instr)
    system = "\n".join(system_parts)
    payload = json.dumps({"slides": slides}, ensure_ascii=False)

    emit = ctx.emit_event
    skill_label = ", ".join(str(s.get("display_name") or s.get("id") or "") for s in post_processors)
    if emit:
        try:
            emit(
                "step",
                {
                    "status": "post_processing_start",
                    "skill_name": skill_label,
                    "output_type": "pptx",
                },
            )
        except Exception:  # noqa: BLE001, S110, SIM105
            pass

    try:
        out = claude_generate_json(
            system=system,
            user=f"Refine this deck JSON per the guidelines above:\n\n{payload}",
            temperature=0.1,
            max_tokens=8192,
        )
        if isinstance(out, dict):
            new_slides = out.get("slides")
            if isinstance(new_slides, list) and len(new_slides) == len(slides):
                merged: list[dict[str, Any]] = []
                for i, raw in enumerate(new_slides):
                    merged.append(raw if isinstance(raw, dict) else slides[i])
                if emit:
                    try:
                        emit(
                            "step",
                            {
                                "status": "post_processing_done",
                                "skill_name": skill_label,
                                "output_type": "pptx",
                            },
                        )
                    except Exception:  # noqa: BLE001, S110, SIM105
                        pass
                return merged
    except Exception:  # noqa: BLE001, S110
        pass
    if emit:
        try:
            emit(
                "step",
                {
                    "status": "post_processing_done",
                    "skill_name": skill_label,
                    "output_type": "pptx",
                    "error": True,
                },
            )
        except Exception:  # noqa: BLE001, S110, SIM105
            pass
    return slides


_TOOL_USAGE_POLICY = (
    "\n\nTool usage policy (follow in order):\n"
    "1. BEFORE generating: call retrieve_context with a query describing the process domain.\n"
    "2. BEFORE generating: call process_model_query(filter_type='summary') to confirm step/role counts.\n"
    "3. BEFORE generating: call search_leading_practices if available.\n"
    "4. AFTER first draft: call save_draft(key='v1', content=...) to persist the draft.\n"
    "5. AFTER first draft: call the structural validator "
    "(document_builder / table_builder / diagram_builder / outline_validator) and fix issues.\n"
    "6. AFTER revision: call cross_reference_checker to verify roles and step names match the ProcessModel.\n"
    "7. Use format_table for tabular output rather than building rows manually.\n"
    "8. Reserve web_search for external standards not in the project context.\n"
    "9. FINAL STEP (mandatory): after all tool calls are complete, output the full final document "
    "as your last response text. Do NOT end with a status summary, validation report, or commentary — "
    "your final message MUST be the complete document content starting with a '# ' heading. "
    "The system captures your final text response as the deliverable; if you output anything other "
    "than the document itself, the deliverable will be empty or corrupted."
)


def _deliverable_type_for_skill(skill_id: str) -> str:
    """
    Map an active skill ID to a deliverable type string for content routing.

    Format agents use this to select the appropriate user prompt and
    deterministic fallback for their active content skill.

    Returns one of: 'sop', 'raci', 'narrative', 'brd', 'approach_note',
    'proposal', or 'generic' (default).
    """
    sid = (skill_id or "").lower()
    if "sop" in sid:
        return "sop"
    if "raci" in sid:
        return "raci"
    if "narrative" in sid:
        return "narrative"
    if "brd" in sid:
        return "brd"
    if "approach_note" in sid:
        return "approach_note"
    if "proposal" in sid:
        return "proposal"
    return "generic"


def _grounded_context_excerpt(ctx: AgentContext, char_cap: int) -> str:
    """Context excerpt that keeps query-ranked retrieval chunks in the prompt.

    assembled_context is tier-ordered (CONTEXT.md → LP snippets → ranked doc
    chunks), so a plain head slice never reaches the BM25/MMR-ranked source
    chunks. Split the cap between the head of assembled_context (curated
    context plus any prepended QA remediation) and the relevance-ordered
    retrieval excerpt, which is safe to head-slice.
    """
    cap = max(0, int(char_cap))
    ac = (ctx.assembled_context or "").strip()
    ranked = str(ctx.retrieval_excerpt or "").strip()
    if ranked.startswith("## Planner retrieval excerpt"):
        ranked = ranked[len("## Planner retrieval excerpt"):].strip()
    if not ranked:
        out = ac[:cap]
    elif not ac:
        out = ranked[:cap]
    else:
        head = ac[: cap // 2]
        out = f"{head}\n\n### Ranked source excerpts (query-aligned)\n{ranked}"[:cap]
    agent = re.sub(r"[^a-z0-9_]", "", str(ctx.output_type or "").lower()) or "unknown"
    offered = len(ac) + len(ranked)
    increment(f"subagent_context_offered_chars_{agent}_total", offered)
    increment(f"subagent_context_consumed_chars_{agent}_total", len(out))
    if offered > len(out):
        increment("subagent_context_truncated_total")
    return out


def _resolve_arc_key(plan_discovery: dict[str, Any]) -> str:
    """Map a free-form narrative_arc hint onto a canonical ARC_LIBRARY key."""
    raw = str((plan_discovery or {}).get("narrative_arc") or "").strip().lower()
    if "scqa" in raw or "situation" in raw or "complication" in raw:
        return "scqa"
    if "case" in raw or "momentum" in raw:
        return "case_led"
    return "pyramid"


def _process_summary_for_storyline(pm: dict[str, Any]) -> str:
    """Compact, evidence-bearing process summary fed to the storyline planner."""
    if not isinstance(pm, dict):
        return ""
    parts: list[str] = []
    name = str(pm.get("name") or pm.get("process_name") or "").strip()
    if name:
        parts.append(f"Process: {name}")
    steps = pm.get("steps") if isinstance(pm.get("steps"), list) else []
    if steps:
        parts.append(f"Steps ({len(steps)}):")
        for i, s in enumerate(steps[:14], 1):
            if isinstance(s, dict):
                lbl = str(s.get("name") or s.get("label") or s.get("activity") or "").strip()
                role = str(s.get("role") or s.get("owner") or "").strip()
                parts.append(f"  {i}. {lbl}" + (f" — {role}" if role else ""))
    for key, title in (
        ("roles", "Roles"), ("systems", "Systems"), ("metrics", "Metrics"),
        ("kpis", "KPIs"), ("pain_points", "Pain points"),
    ):
        vals = pm.get(key)
        if isinstance(vals, list) and vals:
            flat = ", ".join(
                str((v or {}).get("name") if isinstance(v, dict) else v) for v in vals[:8]
            )
            parts.append(f"{title}: {flat}")
    return "\n".join(parts)[:3500]


def _storyline_spine_block(
    ctx: AgentContext,
    pm: dict[str, Any],
    plan_discovery: dict[str, Any],
    target_slides: int,
    mode: str = "deck",
) -> str:
    """Build/load the run's storyline contract and render it as a prompt spine.

    Persists to ``<run_dir>/storyline.json`` so PPTX and DOCX share one spine.
    ``mode="document"`` renders the beats as prose-section guidance for DOCX.
    Fail-open: returns "" on any error or when disabled.
    """
    if not getattr(settings, "storyline_contract_enabled", True):
        return ""
    try:
        from src.agents.conversation.storyline_builder import (
            build_storyline_contract,
            load_storyline_contract,
            persist_storyline_contract,
            render_contract_for_prompt,
            tone_directive,
        )
        from src.core.storage import workspace_path

        run_dir = None
        pid = str(ctx.project_id or "").strip()
        rid = str(ctx.run_id or "").strip()
        if pid and rid:
            run_dir = workspace_path(pid) / "runs" / rid

        contract = load_storyline_contract(run_dir) if run_dir else None
        if not (isinstance(contract, dict) and contract.get("slides")):
            enrichment: dict[str, Any] = {}
            pa = getattr(ctx.enrichment, "process_analytics", None)
            if pa is not None:
                enrichment = {
                    "steps_count": getattr(pa, "steps_count", None),
                    "roles_count": getattr(pa, "roles_count", None),
                    "decision_points": getattr(pa, "decision_points", None),
                }
            contract = build_storyline_contract(
                arc_key=_resolve_arc_key(plan_discovery),
                discovery_slots=plan_discovery if isinstance(plan_discovery, dict) else {},
                process_summary=_process_summary_for_storyline(pm),
                enrichment=enrichment,
                target_slides=target_slides,
            )
            if run_dir and isinstance(contract, dict) and contract.get("slides"):
                persist_storyline_contract(run_dir, contract)
        block = render_contract_for_prompt(contract, mode=mode) if isinstance(contract, dict) else ""
        if block:
            client = plan_discovery.get("client") if isinstance(plan_discovery.get("client"), dict) else {}
            outcome = plan_discovery.get("outcome") if isinstance(plan_discovery.get("outcome"), dict) else {}
            tone = tone_directive(f"{client.get('industry') or ''} {outcome.get('primary') or ''}")
            if tone:
                block = block + "\n\n" + tone
        return block
    except Exception as exc:  # noqa: BLE001 — spine is best-effort
        _LOG.warning("storyline spine injection skipped: %s", exc)
        return ""
