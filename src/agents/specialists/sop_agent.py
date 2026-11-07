"""Standard operating procedure agent."""

from __future__ import annotations

from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import process_model_json_block
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _build_system_from_skill,
    _model,
    _run_post_processor,
)


def run_sop_agent(ctx: AgentContext) -> AgentOutput:
    """
    Legacy content generator retained for direct invocation in tests/tooling.
    This agent writes to sop_markdown (legacy state key).
    For new output routing, use run_docx_agent with sop_v2 skill active.
    """
    pm = _model(ctx)
    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "sop",
            fallback_system=(
                "You are a technical procedure writer. "
                "Audience: an operator who must execute this process without prior context. "
                "Register: formal, imperative, present-tense verbs (e.g. 'Submit the form', not 'You should submit'). "
                "Return ONLY valid Markdown. No HTML. No preamble. The document must start with a # heading."
            ),
        )
        user = (
            "Write a Standard Operating Procedure (SOP) from the ProcessModel below.\n\n"
            "Document structure — use EXACTLY these sections in this order:\n"
            "1. `# <process_name>` — H1 title only, no subtitle\n"
            "2. `## Purpose` — 1–3 sentences: what problem this process solves and who benefits\n"
            "3. `## Scope` — 1–2 sentences: what is covered and what is explicitly out of scope\n"
            "4. `## Roles` — bulleted list of each role in ProcessModel.roles with a one-sentence description "
            "of their mandate in this process\n"
            "5. `## Procedure` — numbered list where each item corresponds to exactly one ProcessModel step; "
            "format: `N. **<step.name>** _(role: <step.role>)_` followed by a sub-list of inputs/outputs/tools "
            "if any are present in the step; do not add steps not in the ProcessModel\n"
            "6. `## Decision Points` — include only if ProcessModel.decisions is non-empty; "
            "for each decision: `**<condition>** → Yes: <true_path step names>, No: <false_path step names>`; "
            "omit this section entirely if decisions is []\n"
            "7. `## References` — single bullet: 'Source: run instruction and assembled project context'\n\n"
            "Length constraint: ≤80 words per section (Purpose, Scope). Procedure steps: ≤20 words per step name line.\n"
            "Do not add sections beyond the seven listed above.\n\n"
            f"{process_model_json_block(pm)}"
        )
        md = _shared._run_subagent_tool_loop_text(ctx, agent_id="sop", system=sb.system, user=user, temperature=sb.temperature, max_rounds=sb.max_rounds)
        if not md:
            try:
                md = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=2200)
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
