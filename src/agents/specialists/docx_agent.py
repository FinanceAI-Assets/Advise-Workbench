"""Word document agent, with its deterministic fallback."""

from __future__ import annotations

from typing import Any
from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import context_excerpt_block, process_model_json_block
from src.core.config import settings
from src.core.state import ProcessModel
from src.guardrails.policy import PROPOSAL_SKILL_ID, proposal_prompt_contract
from src.agents.repair.docx_critique_repair import _critique_and_repair_docx
from src.agents.repair.pptx_critique_repair import _load_run_storyline
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _append_archetype_prompt,
    _append_conversation_digest_block,
    _build_system_from_skill,
    _deliverable_type_for_skill,
    _grounded_context_excerpt,
    _model,
    _primary_skill,
    _run_post_processor,
    _storyline_spine_block,
)


def run_docx_agent(ctx: AgentContext) -> AgentOutput:
    """
    Skill-aware DOCX agent. Content type (SOP, narrative, RACI, BRD, generic)
    is determined by the active primary skill. The skill's system prompt and
    the deliverable-specific user prompt together drive generation.
    """
    pm = _model(ctx)
    primary = _primary_skill(ctx)
    skill_id = str((primary or {}).get("id") or "")
    deliverable = _deliverable_type_for_skill(skill_id)

    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "docx",
            fallback_system=(
                "You are a technical documentation author preparing a DOCX-ready procedure document. "
                "Audience: an internal team member who will follow this document during execution. "
                "Heading hierarchy: # for title (H1), ## for main sections (H2), ### for sub-sections (H3). "
                "Return ONLY valid Markdown. The document must start with a # heading. No HTML. No preamble. "
                "Do not include YAML front matter. "
                "Never output source code (JavaScript, Python, the npm 'docx' library, python-docx) that "
                "would generate the document — your output IS the document body in Markdown."
            ),
        )
        sb = _append_archetype_prompt(sb, ctx, "docx")

        # Select the user prompt based on the active deliverable type
        if deliverable == "sop":
            user = (
                "Write a Standard Operating Procedure (SOP) from the ProcessModel below.\n\n"
                "Document structure — use EXACTLY these sections in this order:\n"
                "1. `# <process_name>` — H1 title only\n"
                "2. `## Purpose` — 2–4 sentences: what problem this process solves and who benefits\n"
                "3. `## Scope` — 1–2 sentences: what is covered and what is explicitly out of scope\n"
                "4. `## Roles` — bulleted list of each role with a one-sentence mandate\n"
                "5. `## Procedure` — numbered list, one item per step; "
                "format: `N. **<step.name>** _(role: <step.role>)_` with sub-bullets for inputs/outputs/tools if non-empty\n"
                "6. `## Decision Points` — only if decisions is non-empty; omit entirely otherwise\n"
                "7. `## References` — single bullet: 'Source: run instruction and assembled project context'\n\n"
                "Length constraint: ≤80 words per section (Purpose, Scope). "
                "Do not add sections beyond the seven listed above.\n\n"
                f"{process_model_json_block(pm)}"
            )
        elif deliverable == "narrative":
            user = (
                "Write an executive briefing note from the ProcessModel and context excerpt below.\n\n"
                "Document structure — use EXACTLY these sections in this order:\n"
                "1. `# <process_name> — Executive Briefing` — H1 title\n"
                "2. `## What This Process Does` — 2–4 sentences: business outcome, who initiates it, who benefits\n"
                "3. `## Key Activities` — ≤6 bulleted items naming activity and owner role in ≤12 words each\n"
                "4. `## Roles and Accountability` — one bullet per role in ≤15 words\n"
                "5. `## Recommended Next Actions` — exactly 2–4 numbered items, ≤20 words each, specific to this process\n\n"
                "Constraints: no hedging language; no 'Context Used' section; no section repetition.\n\n"
                f"{process_model_json_block(pm)}\n"
                f"{context_excerpt_block(_grounded_context_excerpt(ctx, 4000), 4000)}"
            )
        elif deliverable == "raci":
            user = (
                "Build a RACI matrix document from the ProcessModel below.\n\n"
                "Document structure:\n"
                "1. `# RACI Matrix — <process_name>` — H1 title\n"
                "2. `## Assignment Rules` — 2-sentence explanation of R/A/C/I definitions\n"
                "3. `## RACI Table` — Markdown table with columns: "
                "Activity | Responsible | Accountable | Consulted | Informed\n"
                "   Assignment rules: R = step.role; A = first role in roles[] or most senior; "
                "C/I = remaining roles; exactly one A per row; use '—' for empty cells.\n\n"
                "Return ONLY valid Markdown starting with the # heading.\n\n"
                f"{process_model_json_block(pm)}"
            )
        elif deliverable == "proposal":
            p_skill = _primary_skill(ctx)
            _sid = str((p_skill or {}).get("id") or "").strip() or PROPOSAL_SKILL_ID
            contract = proposal_prompt_contract(
                "docx", skill_id=_sid, skill_card=p_skill if isinstance(p_skill, dict) else None
            )
            discovery = (ctx.plan_payload or {}).get("discovery") if isinstance((ctx.plan_payload or {}).get("discovery"), dict) else {}
            discovery_client = discovery.get("client") if isinstance(discovery.get("client"), dict) else {}
            discovery_outcome = discovery.get("outcome") if isinstance(discovery.get("outcome"), dict) else {}
            discovery_themes = discovery.get("win_themes") if isinstance(discovery.get("win_themes"), list) else []
            discovery_block = (
                "Discovery context:\n"
                f"- Client: {discovery_client.get('name', '')} ({discovery_client.get('industry', '')})\n"
                f"- Target outcome: {discovery_outcome.get('primary', '')}\n"
                f"- Decision to enable: {discovery_outcome.get('decision', '')}\n"
                f"- Win themes: {', '.join(str(x) for x in discovery_themes[:3])}\n\n"
                if discovery
                else ""
            )
            sections = "\n".join(f"- {s}" for s in contract.get("sections", []))
            constraints = "\n".join(f"- {c}" for c in contract.get("constraints", []))
            user = (
                "Write a finance transformation proposal document suitable for DOCX export.\n\n"
                "Use this section contract in the same order:\n"
                f"{sections}\n\n"
                "Proposal constraints:\n"
                f"{constraints}\n\n"
                "Document requirements:\n"
                "- Use `#` for the document title and `##` for each contract section.\n"
                "- Add a quantified value case with assumptions and confidence levels.\n"
                "- Include implementation workstreams, sequencing, and ownership by role.\n"
                "- Include risks, mitigations, and measurable success criteria.\n\n"
                + discovery_block
                + f"{process_model_json_block(pm)}\n"
                + f"{context_excerpt_block(_grounded_context_excerpt(ctx, 4000), 4000)}"
            )
        elif deliverable == "brd":
            user = (
                "Write a Business Requirements Document (BRD) from the ProcessModel and context below.\n\n"
                "Document structure — use these sections:\n"
                "1. `# Business Requirements Document — <process_name>`\n"
                "2. `## Executive Summary` — 3–5 sentences on business need and objectives\n"
                "3. `## Current State` — describe the process as extracted from the ProcessModel\n"
                "4. `## Business Requirements` — numbered list of ≥5 specific, measurable requirements\n"
                "5. `## Roles and Stakeholders` — one bullet per role with responsibility\n"
                "6. `## Success Criteria` — 3–5 measurable criteria\n"
                "7. `## References` — Source: run instruction and project context\n\n"
                f"{process_model_json_block(pm)}\n"
                f"{context_excerpt_block(_grounded_context_excerpt(ctx, 3000), 3000)}"
            )
        else:
            # Generic DOCX — procedure document
            user = (
                "Write a procedure document for DOCX export from the ProcessModel below.\n\n"
                "Document structure — use EXACTLY these sections in this order:\n"
                "1. `# <process_name>` — H1 title only\n"
                "2. `## Purpose` — 2–4 sentences: the business reason this process exists\n"
                "3. `## Scope` — 2–3 sentences: activities and systems covered\n"
                "4. `## Roles and Responsibilities` — one bullet per role with mandate\n"
                "5. `## Procedure` — numbered steps matching ProcessModel.steps exactly\n"
                "6. `## Governance and Controls` — include only if ProcessModel.decisions is non-empty\n"
                "7. `## References` — single bullet: 'Source: run instruction and assembled project context'\n\n"
                "Constraints: Purpose and Scope ≤80 words each. "
                "Do not invent controls not present in the ProcessModel.\n\n"
                f"{process_model_json_block(pm)}"
            )

        # ── Storyline spine (shared with PPTX): same contract, document-mode render ──
        # Only argument-led documents follow the arc; SOP/RACI/generic keep their
        # mandated procedural section templates.
        if deliverable in ("narrative", "proposal", "brd") and getattr(
            settings, "docx_storyline_spine_enabled", True
        ):
            _docx_discovery = (ctx.plan_payload or {}).get("discovery") if isinstance((ctx.plan_payload or {}).get("discovery"), dict) else {}
            _docx_steps = len(pm.get("steps") or []) if isinstance(pm, dict) else 0
            _docx_spine = _storyline_spine_block(
                ctx, pm, _docx_discovery, max(8, min(14, _docx_steps + 4)), mode="document"
            )
            if _docx_spine:
                user += "\n\n" + _docx_spine

        _docx_feedback = ctx.plan_payload.get("docx_visual_feedback") or []
        if _docx_feedback and isinstance(_docx_feedback, list):
            _docx_hints = "\n".join(
                f"- {h.get('instruction', '')}" for h in _docx_feedback
                if isinstance(h, dict) and h.get("instruction")
            )
            if _docx_hints:
                user += f"\n\nVisual QA feedback from previous generation (must be addressed):\n{_docx_hints}"

        _docx_narrative = ctx.plan_payload.get("docx_narrative_feedback") or []
        if _docx_narrative and isinstance(_docx_narrative, list):
            _docx_narrative_hints = "\n".join(
                f"- {h.get('instruction', '')}" for h in _docx_narrative
                if isinstance(h, dict) and h.get("instruction")
            )
            if _docx_narrative_hints:
                user += (
                    "\n\nNarrative coherence feedback from previous generation "
                    "(must be addressed — tighten arc, transitions, and topic continuity):\n"
                    f"{_docx_narrative_hints}"
                )
        user = _append_conversation_digest_block(user, ctx)
        md = _shared._run_subagent_tool_loop_text(ctx, agent_id="docx", system=sb.system, user=user,
                                          temperature=sb.temperature, max_rounds=sb.max_rounds)
        if not md:
            try:
                md = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=2200)
            except Exception:
                md = None
        if isinstance(md, str) and md.strip():
            md = _guard_docx_representation(
                ctx, md, system=sb.system, user=user, temperature=sb.temperature
            )
            if md is None:
                return AgentOutput(updates={"docx_markdown": _docx_deterministic_fallback(pm, deliverable, _load_run_storyline(ctx))})
            md = _shared._apply_quality_gate(ctx, "docx", md, system=sb.system, temperature=sb.temperature)
            md = _critique_and_repair_docx(ctx, md, pm, deliverable)
            md = _run_post_processor(ctx, md)
            return AgentOutput(updates={"docx_markdown": md})

    # Deterministic fallback — deliverable-aware
    return AgentOutput(updates={"docx_markdown": _docx_deterministic_fallback(pm, deliverable, _load_run_storyline(ctx))})


def _guard_docx_representation(
    ctx: AgentContext, md: str, *, system: str, user: str, temperature: float
) -> str | None:
    """Reject generator-code output; one corrective retry, else ``None`` for fallback."""
    from src.deliverables.markdown_guard import detect_code_document, strip_outer_fence

    md = strip_outer_fence(md)
    issues = detect_code_document(md)
    if not issues:
        return md
    if ctx.emit_event:
        ctx.emit_event("docx_representation_guard", {"issues": issues, "action": "regenerate"})
    try:
        retry = _shared.claude_generate(
            system=system,
            user=(
                user
                + "\n\nPREVIOUS OUTPUT REJECTED: you emitted program source code that would generate "
                "the document, not the document itself. Output the document text as plain Markdown."
            ),
            temperature=temperature,
            max_tokens=2200,
        )
    except Exception:
        retry = None
    if isinstance(retry, str) and retry.strip():
        retry = strip_outer_fence(retry)
        if not detect_code_document(retry):
            return retry
    if ctx.emit_event:
        ctx.emit_event("docx_representation_guard", {"issues": issues, "action": "deterministic_fallback"})
    return None


def _docx_deterministic_fallback(
    pm: ProcessModel,
    deliverable: str,
    contract: dict[str, Any] | None = None,
) -> str:
    """Deterministic DOCX content for when Claude is unavailable."""
    name = pm.get("process_name") or "Process Document"
    steps = pm.get("steps") or []
    roles = pm.get("roles") or []
    decisions = pm.get("decisions") or pm.get("decision_points") or []
    roles_str = ", ".join(str(r if not isinstance(r, dict) else r.get("name") or r) for r in roles)
    beats = [b for b in (contract or {}).get("slides", []) if isinstance(b, dict)] if contract else []

    def _beat_sections(default_intro: str) -> list[str]:
        if not beats:
            return []
        lines: list[str] = [default_intro, ""]
        for b in beats:
            title = str(b.get("action_title") or b.get("key_message") or "Section").strip()
            msg = str(b.get("key_message") or "").strip()
            ev = str(b.get("required_evidence") or "").strip()
            lines += [f"## {title}", ""]
            if msg:
                lines.append(msg)
            elif ev:
                lines.append(f"Evidence focus: {ev}")
            else:
                lines.append(f"_Content for {title} drawn from the process model._")
            lines.append("")
        return lines

    if deliverable == "sop":
        lines = [f"# {name}", "", "## Purpose", "",
                 "This procedure documents the workflow extracted from the engagement instruction.", "",
                 "## Scope", "", roles_str or "_Roles not specified._", "", "## Roles", ""]
        for r in roles:
            lines.append(f"- **{r}**")
        lines += ["", "## Procedure", ""]
        for i, st in enumerate(steps, 1):
            lines.append(f"{i}. **{st.get('name') or 'Step'}** _(role: {st.get('role') or 'TBD'})_")
        lines += ["", "## References", "", "- Source: run instruction and assembled project context."]
        return "\n".join(lines).strip() + "\n"

    elif deliverable == "narrative":
        if beats:
            lines = [f"# {name} — Executive Briefing", ""] + _beat_sections("")
            lines += ["## Recommended Next Actions", "",
                      "1. Validate step ownership with process owners.",
                      "2. Confirm tooling and systems referenced in source materials."]
            return "\n".join(lines).strip() + "\n"
        n_steps = len(steps)
        n_roles = len(roles)
        highlights = "; ".join(s.get("name", "") for s in steps[:5])
        if len(steps) > 5:
            highlights += "; …"
        lines = [f"# {name} — Executive Briefing", "", "## What This Process Does", "",
                 f"This process covers **{name}**, structured across **{n_steps}** step(s) and **{n_roles}** role(s). "
                 f"Key activities include: {highlights}.", "", "## Key Activities", ""]
        for st in steps[:6]:
            lines.append(f"- **{st.get('name', '—')}** _(owner: {st.get('role', 'TBD')})_")
        lines += ["", "## Roles and Accountability", ""]
        for r in roles:
            lines.append(f"- **{r}**: accountable for their assigned steps in this process")
        lines += ["", "## Recommended Next Actions", "",
                  "1. Validate step ownership with process owners.",
                  "2. Confirm tooling and systems referenced in source materials."]
        return "\n".join(lines).strip() + "\n"

    elif deliverable == "raci":
        accountable = roles[0] if roles else "Process Owner"
        lines = [f"# RACI Matrix — {name}", "", "## Assignment Rules", "",
                 "R = Responsible (executes). A = Accountable (owns outcome, exactly one per row). "
                 "C = Consulted (input required). I = Informed (notified).", "",
                 "## RACI Table", "",
                 "| Activity | Responsible | Accountable | Consulted | Informed |",
                 "|---|---|---|---|---|"]
        for st in steps:
            nm = (st.get("name") or "—").replace("|", "\\|")
            resp = (st.get("role") or "—").replace("|", "\\|")
            others = [r for r in roles if r not in (st.get("role"), accountable)]
            cons = (", ".join(others[:3]) if others else "—").replace("|", "\\|")
            lines.append(f"| {nm} | {resp} | {accountable} | {cons} | — |")
        return "\n".join(lines).strip() + "\n"
    elif deliverable == "proposal":
        if beats:
            intro = (
                f"This proposal covers **{name}** with **{len(steps)}** workflow step(s) "
                f"and **{len(roles)}** role(s) from the extracted process model."
            )
            lines = [f"# Finance Transformation Proposal — {name}", ""] + _beat_sections(intro)
            if steps:
                lines += ["## Process Footprint", ""]
                for st in steps[:8]:
                    if isinstance(st, dict):
                        lines.append(
                            f"- **{st.get('name', '—')}** _(owner: {st.get('role', 'TBD')})_"
                        )
                lines.append("")
            lines += [
                "## Next Steps", "",
                "1. Validate assumptions with process owners and finance leadership.",
                "2. Approve pilot scope and governance forum.",
            ]
            return "\n".join(lines).strip() + "\n"
        highlights = "; ".join(
            str(s.get("name", "")) for s in steps[:5] if isinstance(s, dict)
        )
        owner = str(roles[0] if roles else "Process Owner")
        lines = [
            f"# Finance Transformation Proposal — {name}",
            "",
            "## Executive Summary",
            f"This proposal addresses **{name}**, spanning **{len(steps)}** step(s) and "
            f"**{len(roles)}** role(s). Key activities include: {highlights or 'see process model'}.",
            "",
            "## Current State and Problem Statement",
            "Current-state workflow complexity and handoff friction are captured in the extracted process model.",
            "",
            "## Target Operating Model",
            f"Standardize ownership across {roles_str or 'defined roles'} with clear accountability per step.",
            "",
            "## Workstreams and Timeline",
        ]
        for i, st in enumerate(steps[:6], 1):
            if isinstance(st, dict):
                lines.append(f"{i}. **{st.get('name', 'Workstream')}** — led by {st.get('role') or owner}")
        if len(steps) <= 1:
            lines += ["1. Mobilize and baseline", "2. Design and pilot", "3. Scale and stabilize"]
        lines += [
            "",
            "## Value Case",
            "| Lever | Impact | Confidence | Owner |",
            "|---|---|---|---|",
            f"| Process standardization ({name}) | Operational efficiency | Medium | {owner} |",
            "",
            "## Risks and Mitigations",
            "- Change adoption risk → role-based enablement and governance cadence.",
            "",
            "## Next Steps",
            "1. Validate assumptions with finance leadership.",
            "2. Approve pilot scope and governance forum.",
        ]
        return "\n".join(lines).strip() + "\n"

    elif deliverable == "brd":
        if beats:
            intro = (
                f"Business requirements for **{name}** derived from the process model "
                f"({len(steps)} step(s), {len(roles)} role(s))."
            )
            lines = [f"# Business Requirements Document — {name}", ""] + _beat_sections(intro)
            lines += ["## References", "", "- Source: run instruction and assembled project context."]
            return "\n".join(lines).strip() + "\n"
        req_lines = []
        for i, st in enumerate(steps[:8], 1):
            if isinstance(st, dict):
                req_lines.append(
                    f"{i}. The system shall support **{st.get('name', 'activity')}** "
                    f"with accountable owner **{st.get('role') or 'TBD'}**."
                )
        if decisions:
            for d in decisions[:3]:
                label = d.get("name") if isinstance(d, dict) else str(d)
                req_lines.append(
                    f"{len(req_lines) + 1}. Decision gate **{label}** shall be enforced before downstream steps."
                )
        if not req_lines:
            req_lines = [
                "1. The solution shall document and execute the end-to-end workflow.",
                "2. Each step shall have a named accountable role.",
            ]
        lines = [
            f"# Business Requirements Document — {name}",
            "",
            "## Executive Summary",
            f"This BRD defines requirements for **{name}** across **{len(steps)}** workflow step(s).",
            "",
            "## Current State",
            f"The as-is process involves {roles_str or 'roles to be confirmed'} executing {len(steps)} step(s).",
            "",
            "## Business Requirements",
            *req_lines,
            "",
            "## Roles and Stakeholders",
        ]
        for r in roles[:10]:
            lines.append(f"- **{r}**: responsible for assigned workflow activities.")
        lines += [
            "",
            "## Success Criteria",
            "1. All workflow steps are owned and executable end-to-end.",
            "2. Decision gates are documented and enforced.",
            "3. Roles and handoffs are unambiguous.",
            "",
            "## References",
            "",
            "- Source: run instruction and assembled project context.",
        ]
        return "\n".join(lines).strip() + "\n"

    else:
        # Generic
        lines = [f"# {name}", "", "## Purpose", "Documented procedure for operational execution.", "",
                 "## Procedure"]
        for i, st in enumerate(steps[:30], 1):
            if isinstance(st, dict):
                lines.append(f"{i}. {st.get('name') or 'Step'} ({st.get('role') or 'TBD'})")
        return "\n".join(lines)
