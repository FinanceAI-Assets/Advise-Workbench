"""Spreadsheet agent."""

from __future__ import annotations

import logging
import re
from typing import Any
from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import process_model_json_block
from src.workflows.task_router.output_format_detection import is_financial_model_intent
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _build_system_from_skill,
    _deliverable_type_for_skill,
    _grounded_context_excerpt,
    _model,
    _primary_skill,
)

_LOG = logging.getLogger(__name__)


def _financial_assumptions_from_context(ctx: AgentContext, pm: dict[str, Any]) -> dict[str, Any]:
    """Build model assumptions from process metrics and discovery slots."""
    assumptions: dict[str, Any] = {
        "revenue": 1_000_000,
        "growth_rate": 0.08,
        "cogs_pct": 0.40,
        "opex": 200_000,
        "tax_rate": 0.21,
        "discount_rate": 0.10,
        "terminal_growth": 0.02,
        "capex": 50_000,
        "current_assets": 500_000,
        "fixed_assets": 2_000_000,
        "current_liabilities": 300_000,
        "long_term_debt": 1_000_000,
        "shareholders_equity": 1_200_000,
    }
    for metric in pm.get("metrics") or []:
        if not isinstance(metric, dict):
            continue
        stat = str(metric.get("stat") or "").strip().lower()
        label = str(metric.get("label") or metric.get("value") or "").strip()
        if not stat and not label:
            continue
        raw = stat or label
        digits = re.sub(r"[^\d.]", "", raw.replace(",", ""))
        if not digits:
            continue
        try:
            val = float(digits)
        except ValueError:
            continue
        if "revenue" in raw or "sales" in raw:
            assumptions["revenue"] = val
        elif "margin" in raw and val <= 1:
            assumptions["cogs_pct"] = max(0.0, min(1.0, 1.0 - val))
        elif "growth" in raw and val <= 1:
            assumptions["growth_rate"] = val
        elif "wacc" in raw or "discount" in raw:
            assumptions["discount_rate"] = val if val <= 1 else val / 100.0
    plan = ctx.plan_payload if isinstance(ctx.plan_payload, dict) else {}
    discovery = plan.get("discovery") if isinstance(plan.get("discovery"), dict) else {}
    if isinstance(discovery.get("assumptions"), dict):
        for k, v in discovery["assumptions"].items():
            if v is not None:
                assumptions[str(k)] = v
    return assumptions


def run_xlsx_agent(ctx: AgentContext) -> AgentOutput:
    """
    Skill-aware XLSX agent. When raci_v2 is the active skill, generates a RACI matrix
    (Activity | Responsible | Accountable | Consulted | Informed). Otherwise generates
    the standard process data table (Activity | Owner | Inputs | Outputs | Tools | Duration | Notes).

    For financial-model requests, composes a full formula-driven workbook via
    ``compose_financial_model`` (same engine as the Models API).
    """
    pm = _model(ctx)
    instruction_text = " ".join(
        x
        for x in (
            str(ctx.user_instruction or ""),
            _grounded_context_excerpt(ctx, 6000),
        )
        if x
    )
    if is_financial_model_intent(instruction_text):
        from src.extensions.financial_models.excel_model_composer import compose_financial_model

        assumptions = _financial_assumptions_from_context(ctx, pm)
        try:
            cells = compose_financial_model(assumptions)
            if cells:
                return AgentOutput(updates={"xlsx_cells": cells, "xlsx_markdown": ""})
        except Exception as exc:
            _LOG.warning("financial model compose failed, falling back to table agent: %s", exc)

    steps = pm.get("steps") or []
    roles = pm.get("roles") or []
    primary = _primary_skill(ctx)
    skill_id = str((primary or {}).get("id") or "")
    deliverable = _deliverable_type_for_skill(skill_id)
    is_raci = (deliverable == "raci")

    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "xlsx",
            fallback_system=(
                "You are a data normalisation specialist preparing worksheet content for XLSX export. "
                "Return ONLY a GitHub-flavored Markdown table — header row first, then one data row per step. "
                "No title, no section heading, no explanation before or after the table. "
                "Empty cells must contain '—', never left blank. "
                "Cell values containing '|' must escape it as '\\|'. "
                "No cell value may exceed 200 characters — truncate with '…' if longer."
            ),
        )
        if is_raci:
            accountable = roles[0] if roles else "Process Owner"
            user = (
                "Build a RACI matrix Markdown table from the ProcessModel below.\n\n"
                "Column definitions (in this exact order):\n"
                "  Activity     — step.name\n"
                "  Responsible  — step.role; use roles[0] if step.role is absent\n"
                "  Accountable  — the role that owns the outcome (exactly one per row); "
                f"default to '{accountable}' unless a more senior role is evident\n"
                "  Consulted    — roles whose input is required; '—' if none\n"
                "  Informed     — roles notified after completion; '—' if none\n\n"
                "Header row: | Activity | Responsible | Accountable | Consulted | Informed |\n"
                "Separator:  |---|---|---|---|---|\n"
                "One data row per step. No title, no caption — table only.\n"
                "Exactly one Accountable per row — never blank, never multiple.\n\n"
                f"{process_model_json_block(pm)}"
            )
        else:
            user = (
                "Build a worksheet table from the ProcessModel below. "
                "Each row represents one step from ProcessModel.steps, in the order they appear.\n\n"
                "Column definitions (in this exact order):\n"
                "  Activity  — step.name\n"
                "  Owner     — step.role; use ProcessModel.roles[0] if step.role is absent\n"
                "  Inputs    — step.inputs joined by ', '; '—' if empty\n"
                "  Outputs   — step.outputs joined by ', '; '—' if empty\n"
                "  Tools     — step.tools joined by ', '; '—' if empty\n"
                "  Duration  — step.duration_estimate; '—' if absent\n"
                "  Notes     — step.notes; '—' if absent\n\n"
                "Header row format: | Activity | Owner | Inputs | Outputs | Tools | Duration | Notes |\n"
                "Separator row format: |---|---|---|---|---|---|---|\n"
                "One data row per step. No title, no summary row.\n\n"
                f"{process_model_json_block(pm)}"
            )
        _xlsx_feedback = ctx.plan_payload.get("xlsx_visual_feedback") or []
        if _xlsx_feedback and isinstance(_xlsx_feedback, list):
            _xlsx_hints = "\n".join(
                f"- {h.get('instruction', '')}" for h in _xlsx_feedback
                if isinstance(h, dict) and h.get("instruction")
            )
            if _xlsx_hints:
                user += f"\n\nVisual QA feedback from previous generation (must be addressed):\n{_xlsx_hints}"
        md = _shared._run_subagent_tool_loop_text(ctx, agent_id="xlsx", system=sb.system, user=user,
                                          temperature=sb.temperature, max_rounds=sb.max_rounds)
        if not md:
            try:
                md = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=1800)
            except Exception:
                md = None
        if isinstance(md, str) and "|" in md:
            md = _shared._apply_quality_gate(ctx, "xlsx", md, system=sb.system, temperature=sb.temperature)
            return AgentOutput(updates={"xlsx_markdown": md})

    # Deterministic fallback
    if is_raci:
        accountable = roles[0] if roles else "Process Owner"
        lines = ["| Activity | Responsible | Accountable | Consulted | Informed |", "|---|---|---|---|---|"]
        if not steps:
            lines.append("| No extracted activity | TBD | TBD | — | — |")
        else:
            for st in steps:
                if not isinstance(st, dict):
                    continue
                nm = (st.get("name") or "—").replace("|", "\\|")
                resp = (st.get("role") or (roles[0] if roles else "TBD")).replace("|", "\\|")
                others = [r for r in roles if r not in (st.get("role"), accountable)]
                cons = (", ".join(others[:3]) if others else "—").replace("|", "\\|")
                lines.append(f"| {nm} | {resp} | {accountable} | {cons} | — |")
    else:
        lines = [
            "| Activity | Owner | Inputs | Outputs | Tools | Duration | Notes |",
            "|---|---|---|---|---|---|---|",
        ]
        if not steps:
            lines.append("| No extracted activity | TBD | - | - | - | - | Add structured steps in instruction |")
        else:
            for st in steps:
                if not isinstance(st, dict):
                    continue
                activity = str(st.get("name") or "Step").replace("|", "\\|")
                owner = str(st.get("role") or (roles[0] if roles else "TBD")).replace("|", "\\|")
                inputs = ", ".join([str(v) for v in (st.get("inputs") or [])[:4]]) or "-"
                outputs = ", ".join([str(v) for v in (st.get("outputs") or [])[:4]]) or "-"
                tools = ", ".join([str(v) for v in (st.get("tools") or [])[:4]]) or "-"
                duration = str(st.get("duration_estimate") or "-").replace("|", "\\|")
                notes = str(st.get("notes") or "-").replace("|", "\\|")
                lines.append(f"| {activity} | {owner} | {inputs} | {outputs} | {tools} | {duration} | {notes} |")
    return AgentOutput(updates={"xlsx_markdown": "\n".join(lines)})
