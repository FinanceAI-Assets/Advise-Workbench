"""PDF report agent."""

from __future__ import annotations

from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import context_excerpt_block, process_model_json_block
from src.guardrails.policy import PROPOSAL_SKILL_ID, proposal_prompt_contract
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _build_system_from_skill,
    _deliverable_type_for_skill,
    _grounded_context_excerpt,
    _model,
    _primary_skill,
    _run_post_processor,
)


def run_pdf_agent(ctx: AgentContext) -> AgentOutput:
    """
    Skill-aware PDF agent. When narrative_v2 is active, generates an executive
    narrative report. When sop_v2 is active, generates an SOP-style PDF report.
    Default produces a standard process report.
    """
    pm = _model(ctx)
    primary = _primary_skill(ctx)
    skill_id = str((primary or {}).get("id") or "")
    deliverable = _deliverable_type_for_skill(skill_id)

    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "pdf",
            fallback_system=(
                "You are a management consultant authoring a client-facing report for PDF export. "
                "Audience: a senior decision-maker who reads the executive summary first. "
                "Tone: authoritative, factual, present tense. No hedging phrases. "
                "Return ONLY valid Markdown. The document must start with a # heading. No HTML. No preamble."
            ),
        )
        if deliverable == "narrative":
            user = (
                "Write an executive briefing note for PDF export from the ProcessModel and context below.\n\n"
                "Document structure — use EXACTLY these sections in this order:\n"
                "1. `# <process_name> — Executive Briefing` — H1 title\n"
                "2. `## What This Process Does` — 2–4 sentences: business outcome, initiator, beneficiaries\n"
                "3. `## Key Activities` — ≤6 bulleted items naming activity and owner role in ≤12 words each\n"
                "4. `## Roles and Accountability` — one bullet per role in ≤15 words\n"
                "5. `## Recommended Next Actions` — exactly 2–4 numbered items, ≤20 words each\n\n"
                "Constraints: no hedging language; no 'Context Used' section; no repeated information.\n\n"
                f"{process_model_json_block(pm)}\n"
                f"{context_excerpt_block(_grounded_context_excerpt(ctx, 3500), 3500)}"
            )
        elif deliverable == "sop":
            user = (
                "Write an SOP-format report for PDF export from the ProcessModel below.\n\n"
                "Document structure:\n"
                "1. `# <process_name> — Standard Operating Procedure`\n"
                "2. `## Purpose` — 2–4 sentences\n"
                "3. `## Scope` — 1–2 sentences\n"
                "4. `## Roles` — bulleted list\n"
                "5. `## Procedure` — numbered steps from ProcessModel.steps\n"
                "6. `## Decision Points` — only if decisions is non-empty\n"
                "7. `## References` — Source: run instruction and project context\n\n"
                f"{process_model_json_block(pm)}"
            )
        elif deliverable == "proposal":
            p_skill = _primary_skill(ctx)
            _sid = str((p_skill or {}).get("id") or "").strip() or PROPOSAL_SKILL_ID
            contract = proposal_prompt_contract(
                "pdf", skill_id=_sid, skill_card=p_skill if isinstance(p_skill, dict) else None
            )
            sections = "\n".join(f"- {s}" for s in contract.get("sections", []))
            constraints = "\n".join(f"- {c}" for c in contract.get("constraints", []))
            user = (
                "Write a finance transformation proposal for PDF export.\n\n"
                "Use this section contract in the same order:\n"
                f"{sections}\n\n"
                "Proposal constraints:\n"
                f"{constraints}\n\n"
                "Formatting requirements:\n"
                "- Return only markdown with `#` title and `##` sections.\n"
                "- Include a concise value-case table (lever, impact, confidence, owner).\n"
                "- Include a 90-day workplan with milestones and governance cadence.\n\n"
                f"{process_model_json_block(pm)}\n"
                f"{context_excerpt_block(_grounded_context_excerpt(ctx, 3500), 3500)}"
            )
        else:
            user = (
                "Write a consulting report for PDF export from the ProcessModel and context below.\n\n"
                "Document structure — use EXACTLY these sections in this order:\n"
                "1. `# <process_name> — Process Report` — H1 title\n"
                "2. `## Executive Summary` — 3–5 sentences: process purpose, owner, step count, outcome\n"
                "3. `## Workflow Overview` — numbered list, one item per step; "
                "format: `N. **<step.name>** _(owner: <step.role>)_`\n"
                "4. `## Operational Considerations` — 3–5 bullets from ProcessModel or context only; "
                "if none evident: 'No explicit risks or constraints were identified.'\n"
                "5. `## Next Actions` — exactly 3 numbered items, ≤25 words each\n\n"
                f"{process_model_json_block(pm)}\n"
                f"{context_excerpt_block(_grounded_context_excerpt(ctx, 3500), 3500)}"
            )

        _pdf_feedback = ctx.plan_payload.get("pdf_visual_feedback") or []
        if _pdf_feedback and isinstance(_pdf_feedback, list):
            _pdf_hints = "\n".join(
                f"- {h.get('instruction', '')}" for h in _pdf_feedback
                if isinstance(h, dict) and h.get("instruction")
            )
            if _pdf_hints:
                user += f"\n\nVisual QA feedback from previous generation (must be addressed):\n{_pdf_hints}"

        _pdf_narrative = ctx.plan_payload.get("pdf_narrative_feedback") or []
        if _pdf_narrative and isinstance(_pdf_narrative, list):
            _pdf_narrative_hints = "\n".join(
                f"- {h.get('instruction', '')}" for h in _pdf_narrative
                if isinstance(h, dict) and h.get("instruction")
            )
            if _pdf_narrative_hints:
                user += (
                    "\n\nNarrative coherence feedback from previous generation "
                    "(must be addressed — tighten arc, transitions, and topic continuity):\n"
                    f"{_pdf_narrative_hints}"
                )
        md = _shared._run_subagent_tool_loop_text(ctx, agent_id="pdf", system=sb.system, user=user,
                                          temperature=sb.temperature, max_rounds=sb.max_rounds)
        if not md:
            try:
                md = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=1800)
            except Exception:
                md = None
        if isinstance(md, str) and md.strip():
            md = _shared._apply_quality_gate(ctx, "pdf", md, system=sb.system, temperature=sb.temperature)
            md = _run_post_processor(ctx, md)
            return AgentOutput(updates={"pdf_markdown": md})

    if deliverable == "proposal":
        title = pm.get("process_name") or "Finance Transformation Proposal"
        lines = [
            f"# {title}",
            "",
            "## Executive Summary",
            "This proposal summarizes transformation intent, value opportunities, and a phased execution path.",
            "",
            "## Workstreams and Timeline",
            "1. Mobilize and baseline",
            "2. Design and pilot",
            "3. Scale and stabilize",
            "",
            "## Value Case",
            "| Lever | Impact | Confidence | Owner |",
            "|---|---|---|---|",
            "| Close acceleration | [TBC] | Medium | CFO office |",
            "",
            "## Risks and Mitigations",
            "- Delivery capacity constraints -> phased rollout and governance cadence.",
            "",
            "## Next Steps",
            "1. Validate assumptions with finance and controllership teams.",
            "2. Finalize pilot scope and decision checkpoints.",
        ]
        return AgentOutput(updates={"pdf_markdown": "\n".join(lines)})
    title = pm.get("process_name") or "Process Report"
    steps = pm.get("steps") or []
    lines = [
        f"# {title}",
        "",
        "## Executive Summary",
        "",
        f"This report summarizes the process across {len(steps)} extracted step(s).",
        "",
        "## Workflow Overview",
        "",
    ]
    for i, st in enumerate(steps[:20], start=1):
        if not isinstance(st, dict):
            continue
        lines.append(f"{i}. **{st.get('name') or 'Step'}** — {st.get('role') or 'TBD'}")
    lines.extend(["", "## Next Actions", "", "- Validate step ownership", "- Finalize deliverable formatting"])
    return AgentOutput(updates={"pdf_markdown": "\n".join(lines)})
