"""Process map (draw.io) agent."""

from __future__ import annotations

import html
from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import process_model_json_block
from src.deliverables.process_map.drawio_builder import process_model_to_drawio_xml
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _build_system_from_skill,
    _model,
    _pref,
)


def _normalize_drawio_xml(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    if text.startswith("&lt;"):
        text = html.unescape(text)
    if "<mxGraphModel" not in text and "<mxfile" not in text:
        return None
    start = text.find("<mxfile")
    if start == -1:
        start = text.find("<mxGraphModel")
    if start > 0:
        text = text[start:].strip()
    return text


def _drawio_context_hints(ctx: AgentContext, limit: int = 800) -> str:
    """Extract section headings + first content line from assembled_context for DrawIO hints."""
    ctx_text = ctx.assembled_context or ""
    if not ctx_text:
        return ""
    lines = ctx_text.split("\n")
    hints: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            hints.append(line)
            # Include the next non-empty line as a brief summary of that section.
            for j in range(i + 1, min(i + 4, len(lines))):
                if lines[j].strip():
                    hints.append(lines[j].strip())
                    break
    return "\n".join(hints)[:limit]


def run_drawio_agent(ctx: AgentContext) -> AgentOutput:
    pm = _model(ctx)
    preferred = _pref(ctx, "process_map", "drawio_xml")
    if preferred == "mermaid":
        steps = pm.get("steps") or []
        lines = ["flowchart TD"]
        for idx, step in enumerate(steps):
            node = f"s{idx+1}"
            label = str(step.get("name") or f"Step {idx+1}").replace('"', "'")
            lines.append(f'    {node}["{label}"]')
            if idx > 0:
                lines.append(f"    s{idx} --> {node}")
        if len(lines) == 1:
            lines.append('    s1["Process Start"]')
        return AgentOutput(updates={"process_map_mermaid": "\n".join(lines)})
    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "process_map",
            fallback_system=(
                "You are a diagrams.net (draw.io) mxGraph XML generator. "
                "Return ONLY valid mxGraphModel XML — no prose, no markdown fences, no XML declaration. "
                "The output must be parseable as-is by an XML parser. "
                "Every cell that is a vertex or edge must have parent='1'. "
                "The two scaffolding cells (id='0' root, id='1' layer) must always be present."
            ),
        )
        user = (
            "Generate a diagrams.net mxGraphModel XML diagram from the ProcessModel below.\n\n"
            "Required XML structure:\n"
            "<mxGraphModel><root>\n"
            "  <mxCell id='0'/>\n"
            "  <mxCell id='1' parent='0'/>\n"
            "  <!-- one mxCell per step, one mxCell per decision, one mxCell per edge -->\n"
            "</root></mxGraphModel>\n\n"
            "Step cells (one per ProcessModel.steps entry):\n"
            "  id='sN' where N is the step index (s1, s2, ...)\n"
            "  value='<step.name>'\n"
            "  vertex='1' parent='1'\n"
            "  style='rounded=1;whiteSpace=wrap;html=1;'\n"
            "  <mxGeometry x='{40 + (N-1)*160}' y='100' width='140' height='60' as='geometry'/>\n\n"
            "Decision cells (one per ProcessModel.decisions entry, only if non-empty):\n"
            "  id='dN' where N is the decision index (d1, d2, ...)\n"
            "  value='<decision.condition>'\n"
            "  vertex='1' parent='1'\n"
            "  style='rhombus;whiteSpace=wrap;html=1;'\n"
            "  <mxGeometry x='{x}' y='220' width='140' height='80' as='geometry'/>\n\n"
            "Edge cells (one per sequential step connection, plus true/false edges from decisions):\n"
            "  id='eN' where N is incremented globally\n"
            "  edge='1' source='<sourceId>' target='<targetId>' parent='1'\n"
            "  For decision edges: value='Yes' (true_path) or 'No' (false_path)\n"
            "  style='edgeStyle=orthogonalEdgeStyle;'\n"
            "  <mxGeometry relative='1' as='geometry'/>\n\n"
            "Swimlane rule: if ProcessModel.swimlanes is non-empty, group steps by role using "
            "swimlane container cells (style='swimlane;') with child cells inside them (parent='containerCellId'). "
            "If swimlanes is empty, place all cells flat under parent='1'.\n\n"
            "Do not output anything outside the <mxGraphModel> element.\n\n"
            f"{process_model_json_block(pm)}"
        )
        _drawio_hints = _drawio_context_hints(ctx)
        if _drawio_hints:
            user += f"\n\nContext hints for swimlane structure and roles:\n{_drawio_hints}"
        _pm_feedback = ctx.plan_payload.get("process_map_visual_feedback") or []
        if _pm_feedback and isinstance(_pm_feedback, list):
            _pm_hints = "\n".join(
                f"- {h.get('instruction', '')}" for h in _pm_feedback
                if isinstance(h, dict) and h.get("instruction")
            )
            if _pm_hints:
                user += f"\n\nVisual QA feedback from previous generation (must be addressed):\n{_pm_hints}"
        xml_out = _shared._run_subagent_tool_loop_text(ctx, agent_id="process_map", system=sb.system, user=user, temperature=sb.temperature, max_rounds=sb.max_rounds)
        if not xml_out:
            try:
                xml_out = _shared.claude_generate(system=sb.system, user=user, temperature=sb.temperature, max_tokens=1600)
            except Exception:  # noqa: BLE001 — fallback
                xml_out = None
        normalized = _normalize_drawio_xml(xml_out) if isinstance(xml_out, str) else None
        if normalized and "<mxCell" in normalized:
            return AgentOutput(updates={"drawio_xml": normalized})

    return AgentOutput(updates={"drawio_xml": process_model_to_drawio_xml(pm)})
