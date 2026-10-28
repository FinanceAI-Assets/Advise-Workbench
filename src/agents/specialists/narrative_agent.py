"""Narrative brief agent."""

from __future__ import annotations

from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import context_excerpt_block, process_model_json_block
from src.core.config import settings
from src.core.observability.metrics import increment
from src.agents.specialists import _shared
from src.llm import gateway
from src.agents.specialists._shared import (
    _append_conversation_digest_block,
    _build_system_from_skill,
    _grounded_context_excerpt,
    _model,
    _run_post_processor,
)
from src.prompts.registry import get_prompt


def run_narrative_agent(ctx: AgentContext) -> AgentOutput:
    """
    Legacy content generator retained for direct invocation in tests/tooling.
    This agent writes to narrative_md (legacy state key).
    For new output routing, use run_docx_agent with narrative_v2 skill active.
    """
    pm = _model(ctx)
    actx = (ctx.assembled_context or "").strip()
    if _shared.is_claude_enabled():
        # [EXTERNALIZED to config/prompts/agent_narrative_fallback.yaml]
        fallback_system = get_prompt("agent_narrative_fallback").render_system()
        sb = _build_system_from_skill(
            ctx, "narrative",
            fallback_system=fallback_system,
        )
        prompt = get_prompt("narrative_agent_user")
        user = prompt.render_user(
            process_model=process_model_json_block(pm),
            context=context_excerpt_block(_grounded_context_excerpt(ctx, 4000), 4000)
        )
        user = _append_conversation_digest_block(user, ctx)
        md: str | None = None
        if settings.subagent_narrative_thinking_enabled and _shared.is_claude_enabled():
            try:
                # [DEPRECATED: Hardcoded claude_generate_with_thinking - only works for Anthropic]
                # res = _shared.claude_generate_with_thinking(
                #     system=sb.system,
                #     user=user,
                #     max_tokens=1800,
                #     budget_tokens=settings.anthropic_subagent_thinking_budget_tokens,
                # )
                
                # [NEW: Capability-aware thinking - uses thinking if available, fallback for other providers]
                # gateway imported at module level (line ~12)
                if gateway.capabilities().extended_thinking:
                    # Provider supports thinking (e.g., Anthropic)
                    res = _shared.claude_generate_with_thinking(
                        system=sb.system,
                        user=user,
                        max_tokens=1800,
                        budget_tokens=settings.anthropic_subagent_thinking_budget_tokens,
                    )
                else:
                    # Provider doesn't support thinking - use regular generation
                    from src.agents.tool_agent import _record_message_usage, _extract_final_text_from_message
                    msg = gateway.create_message(
                        model=gateway.model_for("default"),
                        max_tokens=1800,
                        temperature=sb.temperature,
                        system=sb.system,
                        messages=[{"role": "user", "content": user}],
                    )
                    _record_message_usage(msg)
                    res = {"text": _extract_final_text_from_message(msg), "thinking_text": None}
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
