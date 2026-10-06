"""RACI matrix agent."""

from __future__ import annotations

import html
import textwrap
from typing import Any
from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import process_model_json_block
from src.core.state import ProcessModel
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _build_system_from_skill,
    _model,
    _pref,
    _run_post_processor,
)


def _raci_deterministic_updates(pm: ProcessModel, preferred: str) -> dict[str, Any]:
    steps = pm.get("steps") or []
    roles = pm.get("roles") or ["Process Owner", "Contributor"]
    accountable = roles[0] if roles else "Process Owner"
    rows: list[str] = []
    for st in steps:
        name = html.escape(st.get("name") or "—")
        resp = html.escape(st.get("role") or "—")
        acct = html.escape(accountable)
        others = [r for r in roles if r not in (st.get("role"), accountable)]
        consulted = html.escape(", ".join(others[:4]) if others else "—")
        rows.append(f"<tr><td>{name}</td><td>{resp}</td><td>{acct}</td><td>{consulted}</td><td>—</td></tr>")

    body = "\n        ".join(rows) if rows else (
        "<tr><td colspan=\"5\">No activities — add numbered or bulleted steps to the run instruction.</td></tr>"
    )
    title = html.escape(pm.get("process_name") or "RACI")
    html_fallback = textwrap.dedent(
        f"""\
        <!DOCTYPE html>
        <html lang="en"><head><meta charset="utf-8"/><title>{title}</title>
        <style>
          body {{ font-family: system-ui, sans-serif; margin: 1rem; }}
          table {{ border-collapse: collapse; width: 100%; max-width: 960px; }}
          th, td {{ border: 1px solid #ccc; padding: 8px 10px; text-align: left; }}
          th {{ background: #f0f4f8; }}
        </style></head><body>
        <h1>RACI — {title}</h1>
        <table>
          <thead><tr>
            <th>Activity</th><th>Responsible</th><th>Accountable</th><th>Consulted</th><th>Informed</th>
          </tr></thead>
          <tbody>
        {body}
          </tbody>
        </table>
        <p style="color:#666;font-size:0.9rem">RACI derived from extracted process steps and roles.</p>
        </body></html>
        """
    ).strip()
    updates: dict[str, Any] = {"raci_html": html_fallback}
    if preferred in {"markdown", "xlsx"}:
        md_rows = ["| Activity | Responsible | Accountable | Consulted | Informed |", "|---|---|---|---|---|"]
        for st in steps:
            name = (st.get("name") or "—").replace("|", "\\|")
            resp = (st.get("role") or "—").replace("|", "\\|")
            others = [r for r in roles if r not in (st.get("role"), accountable)]
            consulted = (", ".join(others[:4]) if others else "—").replace("|", "\\|")
            md_rows.append(f"| {name} | {resp} | {accountable} | {consulted} | — |")
        updates["raci_markdown"] = "\n".join(md_rows)
    return updates


def run_raci_agent(ctx: AgentContext) -> AgentOutput:
    """
    Legacy content generator retained for direct invocation in tests/tooling.
    This agent writes to raci_html / raci_markdown (legacy state keys).
    For new output routing, use run_xlsx_agent with raci_v2 skill active.
    """
    pm = _model(ctx)
    preferred = _pref(ctx, "raci", "xlsx")
    llm_target = "Markdown table" if preferred in {"markdown", "xlsx"} else "strict HTML table"
    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "raci",
            fallback_system=(
                f"You are a RACI matrix author. "
                f"Output format: {llm_target}. "
                "Return ONLY the table — no preamble, no section headings, no explanation. "
                "RACI definitions: "
                "R (Responsible) = the role that executes the activity. "
                "A (Accountable) = the role that owns the outcome and signs off — EXACTLY ONE per row. "
                "C (Consulted) = roles whose input is required before the step completes. "
                "I (Informed) = roles notified after the step completes. "
                "A role may hold multiple letters in one cell (e.g. 'R/A') only when the same person is both executor and owner. "
                "Never leave Accountable blank."
            ),
        )
        user = (
            "Build a RACI matrix from the ProcessModel below.\n\n"
            "Assignment rules:\n"
            "1. Responsible (R): use step.role. If step.role is absent or 'TBD', assign R to the first role in ProcessModel.roles.\n"
            "2. Accountable (A): assign to the first role in ProcessModel.roles unless a more senior role is evident from the name "
            "(e.g. 'Manager', 'Director', 'Lead', 'Owner'). Exactly one A per row — never blank, never multiple.\n"
            "3. Consulted (C): assign remaining roles whose work depends on or feeds into this step. "
            "If no such roles exist, use '—'.\n"
            "4. Informed (I): assign roles that receive the output of this step but do not participate. "
            "If none, use '—'.\n\n"
            f"Output format: {preferred} (markdown table with header row if markdown, full HTML table if html).\n"
            "Column order: Activity | Responsible | Accountable | Consulted | Informed\n"
            "One row per ProcessModel.steps entry. Do not add rows for roles — only for activities.\n"
            "Do not include a title row, caption, or explanatory text — table only.\n\n"
            f"{process_model_json_block(pm)}"
        )
        loop_out = _shared._run_subagent_tool_loop_text(ctx, agent_id="raci", system=sb.system, user=user, temperature=sb.temperature, max_rounds=sb.max_rounds)
        model_out = loop_out
        if not model_out:
            try:
                model_out = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=1800)
            except Exception:  # noqa: BLE001 — fallback
                model_out = None
        if isinstance(model_out, str) and model_out.strip():
            model_out = _shared._apply_quality_gate(ctx, "raci", model_out, system=sb.system, temperature=sb.temperature)
            model_out = _run_post_processor(ctx, model_out)
            if preferred in {"markdown", "xlsx"} and "|" in model_out:
                base = _raci_deterministic_updates(pm, preferred)
                base["raci_markdown"] = model_out
                return AgentOutput(updates=base)
            if preferred == "html" and "<table" in model_out.lower() and "<tr" in model_out.lower():
                return AgentOutput(updates={"raci_html": model_out})

    return AgentOutput(updates=_raci_deterministic_updates(pm, preferred))
