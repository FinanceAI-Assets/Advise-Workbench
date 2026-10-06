"""Narrative brief agent."""

from __future__ import annotations

from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import context_excerpt_block, process_model_json_block
from src.core.config import settings
from src.core.observability.metrics import increment
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _append_conversation_digest_block,
    _build_system_from_skill,
    _grounded_context_excerpt,
    _model,
    _run_post_processor,
)


def run_narrative_agent(ctx: AgentContext) -> AgentOutput:
    """
    Legacy content generator retained for direct invocation in tests/tooling.
    This agent writes to narrative_md (legacy state key).
    For new output routing, use run_docx_agent with narrative_v2 skill active.
    """
    pm = _model(ctx)
    actx = (ctx.assembled_context or "").strip()
    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "narrative",
            fallback_system=(
                "You are a management consultant writing a client-facing briefing note. "
                "Audience: a senior stakeholder who will not read technical details — they need insight, not procedure. "
                "Tone: authoritative, direct, no hedging language ('it appears', 'it seems', 'we believe'). "
                "Return ONLY valid Markdown starting with a # heading. No HTML. No preamble."
            ),
        )
        user = (
            "Write an executive briefing note from the ProcessModel and context excerpt below.\n\n"
            "Document structure — use EXACTLY these sections in this order:\n"
            "1. `# <process_name> — Executive Briefing` — H1 title\n"
            "2. `## What This Process Does` — 2–4 sentences: the business outcome delivered by this process, "
            "who initiates it, and who benefits; do not describe individual steps\n"
            "3. `## Key Activities` — bulleted list of ≤6 items; each item names the activity and its owner role "
            "in ≤12 words; derived from ProcessModel.steps; omit low-signal steps if there are more than 6\n"
            "4. `## Roles and Accountability` — one bullet per role in ProcessModel.roles; "
            "state what that role is accountable for in this process in ≤15 words\n"
            "5. `## Recommended Next Actions` — exactly 2–4 numbered items; "
            "each action must be specific to this process (not generic advice); "
            "each item ≤20 words; no action should duplicate another\n\n"
            "Constraints:\n"
            "  - Do not quote or paraphrase the context excerpt verbatim.\n"
            "  - Do not add a 'Context Used' or 'References' section.\n"
            "  - Do not repeat information across sections.\n"
            "  - Do not use the phrase 'in conclusion' or 'in summary'.\n\n"
            f"{process_model_json_block(pm)}\n"
            f"{context_excerpt_block(_grounded_context_excerpt(ctx, 4000), 4000)}"
        )
        user = _append_conversation_digest_block(user, ctx)
        md: str | None = None
        if settings.subagent_narrative_thinking_enabled and _shared.is_claude_enabled():
            try:
                res = _shared.claude_generate_with_thinking(
                    system=sb.system,
                    user=user,
                    max_tokens=1800,
                    budget_tokens=settings.anthropic_subagent_thinking_budget_tokens,
                )
                thinking_t = str(res.get("thinking_text") or "").strip()
                if thinking_t and ctx.emit_event:
                    ctx.emit_event("narrative_thinking_excerpt", {"thinking_excerpt": thinking_t[:1500]})
                increment("narrative_thinking_used_total")
                cand = str(res.get("text") or "").strip()
                if cand.startswith("#"):
                    md = cand
            except Exception:  # noqa: BLE001
                md = None
        if not md:
            md = _shared._run_subagent_tool_loop_text(
                ctx, agent_id="narrative", system=sb.system, user=user, temperature=sb.temperature, max_rounds=sb.max_rounds
            )
        if not md:
            try:
                md = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=1800)
            except Exception:  # noqa: BLE001 — fallback
                md = None
        if isinstance(md, str) and md.strip().startswith("#"):
            md = _shared._apply_quality_gate(ctx, "narrative", md, system=sb.system, temperature=sb.temperature)
            md = _run_post_processor(ctx, md)
            return AgentOutput(updates={"narrative_md": md})

    # Deterministic fallback.
    ctx_excerpt = (actx[:1200] + "…") if len(actx) > 1200 else actx
    name = pm.get("process_name") or "Engagement process"
    steps = pm.get("steps") or []
    roles = pm.get("roles") or []
    summary = (
        f"The following narrative summarizes **{name}**, structured as **{len(steps)}** workflow step(s) "
        f"across **{len(roles)}** role(s)."
    )
    if steps:
        highlights = "; ".join(f"{s.get('name', '')}" for s in steps[:5])
        if len(steps) > 5:
            highlights += "; …"
        summary += f" Key activities include: {highlights}."
    body = [
        f"# Executive narrative — {name}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Context used",
        "",
        "```",
        ctx_excerpt or "_No additional tiered context was available._",
        "```",
        "",
        "## Recommended next actions",
        "",
    ]
    if steps:
        body.append("1. Validate each step with process owners and update RACI where handoffs are unclear.")
        body.append("2. Confirm tooling and systems referenced in source materials.")
    else:
        body.append("1. Enrich the run instruction with numbered steps to unlock full SOP and diagram outputs.")
    body.extend(["", "---", "", "*Generated by Advise Workbench (deterministic extraction).*", ""])
    return AgentOutput(updates={"narrative_md": "\n".join(body).strip() + "\n"})
