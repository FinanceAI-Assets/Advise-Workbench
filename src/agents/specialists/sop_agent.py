"""Standard operating procedure agent."""

from __future__ import annotations

from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import process_model_json_block
from src.agents.specialists import _shared
from src.llm import gateway
from src.agents.specialists._shared import (
    _build_system_from_skill,
    _model,
    _run_post_processor,
)
from src.prompts.registry import get_prompt


def run_sop_agent(ctx: AgentContext) -> AgentOutput:
    """
    Legacy content generator retained for direct invocation in tests/tooling.
    This agent writes to sop_markdown (legacy state key).
    For new output routing, use run_docx_agent with sop_v2 skill active.
    """
    pm = _model(ctx)
    if _shared.is_claude_enabled():
        # [EXTERNALIZED to config/prompts/agent_sop_fallback.yaml]
        fallback_system = get_prompt("agent_sop_fallback").render_system()
        sb = _build_system_from_skill(
            ctx, "sop",
            fallback_system=fallback_system,
        )
        prompt = get_prompt("sop_user")
        user = prompt.render_user(process_model=process_model_json_block(pm))
        md = _shared._run_subagent_tool_loop_text(ctx, agent_id="sop", system=sb.system, user=user, temperature=sb.temperature, max_rounds=sb.max_rounds)
        if not md:
            try:
                # [DEPRECATED: Hardcoded claude_generate] Use gateway for provider-agnostic call
                # md = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=2200)
                
                # [NEW: Gateway-based provider-agnostic call - Supports all LLM providers]
                # gateway imported at module level (line ~12)
                from src.agents.tool_agent import _record_message_usage, _extract_final_text_from_message
                msg = gateway.create_message(
                    model=gateway.model_for("default"),
                    max_tokens=2200,
                    temperature=sb.temperature,
                    system=sb.system,
                    messages=[{"role": "user", "content": user}],
                )
                _record_message_usage(msg)
                md = _extract_final_text_from_message(msg)
            except Exception:  # noqa: BLE001 — fallback
                md = None
        if isinstance(md, str) and md.strip().startswith("#"):
            md = _shared._apply_quality_gate(ctx, "sop", md, system=sb.system, temperature=sb.temperature)
            md = _run_post_processor(ctx, md)
            return AgentOutput(updates={"sop_markdown": md})

    # Deterministic fallback.
    name = pm.get("process_name") or "Standard Operating Procedure"
    steps = pm.get("steps") or []
    roles = ", ".join(pm.get("roles") or [])
    lines: list[str] = [
        f"# {name}",
        "",
        "## Purpose",
        "",
        "This procedure documents the workflow extracted from the engagement instruction and project context.",
        "",
        "## Roles",
        "",
        roles or "_Not specified — inferred defaults._",
        "",
        "## Procedure",
        "",
    ]
    if not steps:
        lines.extend(
            [
                "_No discrete steps were parsed. Provide numbered (1., 2.) or bullet (-) steps in the run instruction._",
                "",
            ]
        )
    else:
        for i, st in enumerate(steps, start=1):
            role = st.get("role") or "TBD"
            nm = st.get("name") or "Step"
            lines.append(f"{i}. **{nm}** — _{role}_")
            if st.get("notes"):
                lines.append(f"   - Notes: {st['notes']}")
            lines.append("")

    decs = pm.get("decisions") or []
    if decs:
        lines.extend(["## Decision points", ""])
        for d in decs:
            lines.append(f"- **{d.get('id', '?')}**: {d.get('condition', '')}")
        lines.append("")

    lines.extend(
        [
            "## References",
            "",
            "- Source: assembled project context and run instruction (see run artifacts).",
            "",
        ]
    )
    return AgentOutput(updates={"sop_markdown": "\n".join(lines).strip() + "\n"})
