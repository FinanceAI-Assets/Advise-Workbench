"""Presentation agent, with title, storyline and deterministic slide helpers."""

from __future__ import annotations

import logging
import json
from typing import Any
from src.agents.base_agent import AgentContext, AgentOutput
from src.prompts.prompt_hygiene import process_model_json_block, wrap_untrusted_bundle
from src.core.state import ProcessModel
from src.llm.claude import _extract_first_json_object
from src.agents.repair.pptx_critique_repair import (
    _critique_and_repair_pptx,
    _load_run_storyline,
    _merge_pptx_slides_repair,
    _normalize_pptx_slide_identities,
    _pptx_visual_feedback_indices,
)
from src.agents.specialists import _shared
from src.agents.specialists._shared import (
    _SkillBuild,
    _append_archetype_prompt,
    _build_system_from_skill,
    _grounded_context_excerpt,
    _model,
    _primary_skill,
    _session_debug_log,
    _skill_instruction,
    _storyline_spine_block,
)

_LOG = logging.getLogger(__name__)


def _matching_context_lines(text: str, keywords: tuple[str, ...], *, max_chars: int = 600) -> str:
    """Lines from assembled context that mention any keyword, bounded for prompt use."""
    out: list[str] = []
    used = 0
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-•#").strip()
        if len(line) < 20:
            continue
        low = line.lower()
        if not any(kw in low for kw in keywords):
            continue
        snippet = f"- {line[:240]}"
        if used + len(snippet) + 1 > max_chars:
            break
        out.append(snippet)
        used += len(snippet) + 1
    return "\n".join(out)


def _shared_user_context_appendix(ctx: AgentContext) -> str:
    """
    Build the user-prompt context appendix with labelled sections.

    For PPTX output, context is segmented by purpose so the model can
    locate the right facts for each slide type without scanning 30KB:
      - QUANTITATIVE METRICS  → stat_cards slides
      - PAIN POINTS           → problem statement slides
      - VALUE DRIVERS & ROI   → value case slides
      - LEADING PRACTICES     → credibility / case study slides
    """
    blocks: list[str] = []
    ui = ctx.user_instruction.strip()
    if ui:
        blocks.append(f"## User instruction\n{ui[:2200]}")

    ac = ctx.assembled_context.strip()
    if ac and ctx.output_type == "pptx":
        # ── Labelled context for PPTX: segment by slide purpose ──────────
        # Split assembled_context into purpose-labelled sections so the model
        # can find the right facts per slide without scanning the entire blob.
        enrichment = ctx.enrichment
        metrics_parts: list[str] = []
        value_parts: list[str] = []

        # Extract structured metrics from enrichment if available
        if enrichment:
            steps = getattr(enrichment, "steps_count", None) or (
                getattr(getattr(enrichment, "process_analytics", None), "steps_count", None)
            )
            roles = getattr(enrichment, "roles_count", None) or (
                getattr(getattr(enrichment, "process_analytics", None), "roles_count", None)
            )
            systems = getattr(enrichment, "systems_count", None)
            if steps or roles or systems:
                metrics_parts.append(
                    f"Process scale: {steps or '?'} steps, "
                    f"{roles or '?'} roles, {systems or '?'} systems"
                )

            drivers = getattr(enrichment, "value_drivers", [])
            if isinstance(drivers, list) and drivers:
                driver_names = [
                    str(d.get("name") if isinstance(d, dict) else d)
                    for d in drivers[:5] if d
                ]
                value_parts.append("Value drivers: " + ", ".join(n for n in driver_names if n))

            risks_obj = getattr(enrichment, "risk_profile", None)
            risks = getattr(risks_obj, "risks", []) if risks_obj else []
            if isinstance(risks, list) and risks:
                risk_names = [
                    str(r.get("name") if isinstance(r, dict) else r)
                    for r in risks[:5] if r
                ]
                value_parts.append("Key risks: " + ", ".join(n for n in risk_names if n))

        # Build labelled sections
        labelled: list[str] = []
        if metrics_parts:
            labelled.append(
                "## QUANTITATIVE METRICS (use for stat_cards slides)\n" + "\n".join(metrics_parts)
            )

        # Scan assembled_context for pain-point / current-state signals
        ac_lower = ac.lower()
        has_value = any(kw in ac_lower for kw in ("saving", "roi", "cost reduction", "benefit", "improvement", "value"))
        pain_lines = _matching_context_lines(
            ac, ("pain point", "challenge", "problem", "current state", "issue", "gap")
        )
        lp_lines = _matching_context_lines(
            ac, ("case study", "leading practice", "benchmark", "reference")
        )

        if pain_lines:
            labelled.append(
                "## PAIN POINTS & CURRENT STATE (use for problem statement slides)\n" + pain_lines
            )
        if has_value and value_parts:
            labelled.append(
                "## VALUE DRIVERS & ROI (use for value case slides)\n" + "\n".join(value_parts)
            )
        elif value_parts:
            labelled.append("## VALUE DRIVERS\n" + "\n".join(value_parts))
        if lp_lines:
            labelled.append(
                "## LEADING PRACTICES & CASE STUDIES (use for credibility slides)\n" + lp_lines
            )

        excerpt = _grounded_context_excerpt(ctx, 3500)
        if labelled:
            # Prepend labels, then include full context below
            label_block = "\n\n".join(labelled)
            blocks.append(
                f"## Assembled project context (labelled for slide generation)\n"
                f"{label_block}\n\n"
                f"## Full context\n{excerpt}"
            )
        else:
            blocks.append(f"## Assembled project context (excerpt)\n{excerpt}")
    elif ac:
        blocks.append(f"## Assembled project context (excerpt)\n{_grounded_context_excerpt(ctx, 3500)}")

    pae = ctx.prior_artifacts_excerpt.strip()
    if pae:
        blocks.append(pae)
    enrichment_context = str(getattr(ctx.enrichment, "context_snippets", "") or "").strip()
    if enrichment_context:
        blocks.append(f"## Prior artifacts context\n{enrichment_context[:2200]}")
    if not blocks:
        return ""
    return wrap_untrusted_bundle("\n\n".join(blocks) + "\n\n---\n\n")


def _pptx_deterministic_slides(
    pm: ProcessModel,
    contract: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Full minimal deck when Claude is off or JSON fails — matches pptx_v1 mandatory sequence."""
    beats = [b for b in (contract or {}).get("slides", []) if isinstance(b, dict)] if contract else []
    if beats:
        slides: list[dict[str, Any]] = []
        process_name = str(pm.get("process_name") or "Process Overview")
        slides.append({
            "title": process_name,
            "slide_type": "title",
            "subtitle": str((contract or {}).get("governing_thought") or "Process Overview")[:120],
        })
        fill_rot = ["dark", "mid_dark", "green", "gray", "mid", "dark_green"]
        for i, b in enumerate(beats[:18]):
            vis = str(b.get("suggested_visual") or "bullets").lower()
            title = str(b.get("action_title") or f"Beat {i + 1}")
            msg = str(b.get("key_message") or "")
            slide: dict[str, Any] = {"title": title, "slide_type": vis if vis != "section_divider" else "section_divider"}
            if vis in ("bullets", "section_divider"):
                if msg:
                    slide["bullets"] = [msg]
            elif vis == "stat_cards":
                slide["stat_cards"] = [{"stat": "—", "label": title[:40], "description": msg[:120], "fill": fill_rot[i % len(fill_rot)]}]
            else:
                slide["slide_type"] = "bullets"
                slide["bullets"] = [msg] if msg else [title]
            slides.append(slide)
        return slides

    steps = pm.get("steps") or []
    roles = pm.get("roles") or []
    process_name = str(pm.get("process_name") or "Process Overview")
    n_s, n_r = len(steps), len(roles)
    fill_rot = ["dark", "mid_dark", "green", "gray", "mid", "dark_green"]
    step_src = steps or [{"name": "No steps extracted", "description": "", "role": "TBD"}]
    stack: list[dict[str, Any]] = []
    for i, s in enumerate(step_src[:6]):
        if isinstance(s, dict):
            stack.append(
                {
                    "label": str(s.get("name") or "Step")[:40],
                    "description": str(s.get("description") or f"Owner: {s.get('role') or 'TBD'}")[:100],
                    "fill": fill_rot[i % len(fill_rot)],
                }
            )
        else:
            stack.append({"label": f"Step {i + 1}", "description": "", "fill": fill_rot[i % len(fill_rot)]})

    role_bullets = [f"{r}: accountable for assigned activities in this process." for r in roles[:8]]
    if not role_bullets:
        role_bullets = ["Define process ownership and RACI with stakeholders."]

    table_rows: list[list[str]] = []
    for st in steps[:12]:
        if not isinstance(st, dict):
            continue
        ins = str(st.get("inputs") or "—")
        outs = str(st.get("outputs") or "—")
        io = f"{ins} → {outs}"
        table_rows.append(
            [
                str(st.get("name") or "—")[:40],
                str(st.get("role") or "TBD")[:30],
                io[:80],
            ]
        )
    if not table_rows:
        table_rows = [["—", "TBD", "See process documentation"]]

    return [
        {
            "title": process_name,
            "slide_type": "title",
            "subtitle": "Process Overview",
            "badges": [
                f"{n_s} workflow steps",
                f"{n_r} roles",
                "Advise Workbench",
            ],
        },
        {
            "title": "Process scale",
            "slide_type": "stat_cards",
            "stat_cards": [
                {
                    "stat": str(n_s),
                    "label": "workflow steps\ncaptured in model",
                    "description": "Step count shows scope of the process for prioritization and control design.",
                    "fill": "dark",
                },
                {
                    "stat": str(n_r),
                    "label": "distinct roles\ninvolved",
                    "description": "Role coverage highlights handoffs and accountability surfaces.",
                    "fill": "mid_dark",
                },
                {
                    "stat": "—",
                    "label": "SLA / run rate\n(to define)",
                    "description": "Quantify cycle time or frequency once operational data is available.",
                    "fill": "gray",
                },
            ],
        },
        {
            "title": "Operating pillars",
            "slide_type": "column_cards",
            "column_cards": [
                {
                    "heading": "Governance",
                    "accent": "green",
                    "body": "Controls, approvals, and policy checkpoints that keep the process compliant and auditable.",
                },
                {
                    "heading": "Execution",
                    "accent": "dark",
                    "body": "Day-to-day activities, handoffs, and tooling used to move work from intake to completion.",
                },
                {
                    "heading": "Insight",
                    "accent": "gray",
                    "body": "Metrics and feedback loops that expose bottlenecks and drive continuous improvement.",
                },
            ],
        },
        {
            "title": "Workflow layers",
            "slide_type": "stack_layers",
            "stack_layers": stack,
        },
        {
            "title": "Role mandates",
            "slide_type": "bullets",
            "bullets": role_bullets[:8],
        },
        {
            "title": "Workflow walkthrough",
            "slide_type": "table",
            "table": {
                "headers": ["Step", "Owner", "Inputs → Outputs"],
                "rows": table_rows,
                "x": 0.28,
                "y": 1.0,
                "w": 9.44,
                "h": 4.3,
            },
        },
        {
            "title": "Controls and metrics",
            "slide_type": "stat_cards",
            "stat_cards": [
                {
                    "stat": "—",
                    "label": "key control\npoints",
                    "description": "Map critical controls to steps once the control framework is agreed.",
                    "fill": "dark",
                },
                {
                    "stat": "—",
                    "label": "error or\nexception rate",
                    "description": "Track defect or rework rates where systems provide operational data.",
                    "fill": "mid_dark",
                },
                {
                    "stat": "—",
                    "label": "cycle time\nor SLA",
                    "description": "Baseline throughput targets after measuring end-to-end lead time.",
                    "fill": "gray",
                },
            ],
        },
        {
            "title": "Recommended next actions",
            "slide_type": "bullets",
            "bullets": [
                "1. Validate ownership per workflow step with process owners.",
                "2. Confirm control checks and handoffs against policy.",
                "3. Approve delivery format and communication plan.",
            ],
        },
    ]


_CHAT_MARKERS = ("assistant:", "user:", "👋", "💬", "🎯", "🚀", "qa remediation", "guardrail")


_CONVERSATIONAL_PREFIXES = (
    "help ",
    "help me ",
    "can you ",
    "could you ",
    "please ",
    "pls ",
    "i want ",
    "i need ",
    "i'd like ",
    "we want ",
    "we need ",
    "let's ",
    "lets ",
    "hey ",
    "hi ",
    "hello ",
)


_CONVERSATIONAL_VERBS = (
    "help create",
    "help me create",
    "help build",
    "help draft",
    "create a ",
    "build a ",
    "draft a ",
    "write a ",
    "make a ",
    "generate a ",
    "prepare a ",
    "put together",
)


def _looks_like_chat_line(text: str) -> bool:
    """Return True when the given string looks like a conversational command,
    not a deck-worthy title.

    Catches cases like "Help create the proposal please", "can you build a deck",
    "hi, I need a slide on finance ops", etc. — titles that happen to satisfy
    the length check but should never appear verbatim on a title slide.
    """
    if not text:
        return True
    t = text.strip().lower()
    if not t:
        return True
    if any(m in t for m in _CHAT_MARKERS):
        return True
    if t.endswith("?"):
        return True
    if any(t.startswith(p) for p in _CONVERSATIONAL_PREFIXES):
        return True
    if any(phrase in t for phrase in _CONVERSATIONAL_VERBS):
        return True
    # Catch conversational openers even when punctuation follows
    # (e.g. "Hi, I need a proposal", "Hey! Build me a deck").
    first_token = t.split(maxsplit=1)[0].rstrip(",.!?;:") if t.split() else ""
    if first_token in {"hi", "hey", "hello", "yo", "pls", "please", "help"}:
        return True
    # First-person imperatives are almost always chat, not a title.
    if first_token in {"i", "we", "i'd", "id"}:
        return True
    # Words like "please", "thanks" anywhere are strong chat signals.
    for chatty_word in (" please", " thanks", " thank you"):
        if chatty_word in t:
            return True
    return False


def _normalise_industry(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    # Drop redundant "industry"/"sector" suffixes.
    for tail in (" industry", " sector"):
        if s.lower().endswith(tail):
            s = s[: -len(tail)].rstrip()
    return s


def _title_from_discovery(discovery: dict | None) -> str:
    """Build a client-specific deck title from discovery inputs when possible."""
    if not isinstance(discovery, dict):
        return ""
    client = discovery.get("client") if isinstance(discovery.get("client"), dict) else {}
    client_name = str(client.get("name") or "").strip()
    if not client_name:
        return ""
    industry = _normalise_industry(str(client.get("industry") or ""))
    outcome = discovery.get("outcome") if isinstance(discovery.get("outcome"), dict) else {}
    outcome_primary = str(outcome.get("primary") or "").strip()
    audience = str(discovery.get("audience") or "").strip().lower()

    audience_label = {
        "cfo": "CFO",
        "board": "Board",
        "buying_committee": "Buying Committee",
        "mixed": "",
    }.get(audience, "")

    # Prefer the outcome phrasing when it's specific, otherwise fall back
    # to a lightweight "{Client} transformation proposal" pattern.
    headline = ""
    if outcome_primary and not _looks_like_chat_line(outcome_primary):
        headline = outcome_primary
    if not headline:
        headline = f"{client_name} transformation proposal"

    # Compose — keep it within 90 chars.
    if audience_label and audience_label.lower() not in headline.lower():
        title = f"{client_name} — {headline} ({audience_label} briefing)"
    else:
        title = f"{client_name} — {headline}" if client_name.lower() not in headline.lower() else headline

    # Light capitalisation for readability.
    if title.islower():
        title = title.title()
    return title[:118]


def _title_from_outline(deck_outline: dict | None) -> str:
    """Return the outline's title slide title if it looks plausible."""
    if not isinstance(deck_outline, dict):
        return ""
    slides = deck_outline.get("slides")
    if not isinstance(slides, list) or not slides:
        return ""
    first = slides[0]
    if not isinstance(first, dict):
        return ""
    title = str(first.get("title") or "").strip()
    if not title:
        return ""
    if _looks_like_chat_line(title):
        return ""
    if not (5 <= len(title) <= 120):
        return ""
    return title


def _resolve_presentation_title(
    pm: dict,
    state: dict,
    *,
    discovery: dict | None = None,
    deck_outline: dict | None = None,
) -> str:
    """
    Return the best available presentation title.

    Priority order:
      1. Approved deck-outline preview's first slide title (user confirmed it).
      2. A discovery-derived title such as "Varroc — Finance Transformation
         Proposal (CFO briefing)" when we know the client.
      3. ``pm["process_name"]`` if it looks like a real title.
      4. First meaningful line from ``user_intent_original`` ONLY when it does
         not look conversational (e.g. "Help create the proposal please").
      5. Final fallback: "Executive Briefing".
    """
    outline_title = _title_from_outline(deck_outline)
    if outline_title:
        return outline_title

    discovery_title = _title_from_discovery(discovery)
    if discovery_title:
        return discovery_title

    name = (pm.get("process_name") or "").strip()
    name_lower = name.lower()
    if (
        name
        and 5 <= len(name) <= 120
        and not any(m in name_lower for m in _CHAT_MARKERS)
        and not _looks_like_chat_line(name)
    ):
        return name

    intent = (state.get("user_intent_original") or "").strip()
    if intent:
        first_line = intent.splitlines()[0].strip()
        if 5 <= len(first_line) <= 120 and not _looks_like_chat_line(first_line):
            return first_line

    return "Executive Briefing"


def run_pptx_agent(ctx: AgentContext) -> AgentOutput:
    pm = _model(ctx)
    primary = _primary_skill(ctx) or {}
    # region agent log
    _session_debug_log(
        run_id=ctx.run_id,
        hypothesis_id="H4",
        location="subagents.py:run_pptx_agent:entry",
        message="PPTX agent entered",
        data={
            "claude_enabled": bool(_shared.is_claude_enabled()),
            "primary_skill_id": str(primary.get("id") or ""),
            "primary_skill_display_name": str(primary.get("display_name") or ""),
            "assembled_context_chars": len(str(ctx.assembled_context or "")),
            "process_model_steps": len(pm.get("steps") or []) if isinstance(pm, dict) else 0,
            "skill_instruction_chars": len(str(_skill_instruction(ctx, "pptx") or "")),
        },
    )
    # endregion
    if _shared.is_claude_enabled():
        sb = _build_system_from_skill(
            ctx, "pptx",
            fallback_system=(
                "You are generating a production-ready PowerPoint presentation deck. "
                "Your JSON output will be immediately rendered into a fully-branded .pptx file that users can download and open. "
                "Use varied, professional slide types — not just bullet lists. "
                "Return ONLY a JSON object with a single top-level key 'slides' containing an array. "
                "No prose, no markdown fences, no explanation. The JSON must be parseable with json.loads().\n\n"
                "CRITICAL: Always populate slides with actual data. Never generate empty arrays for stat_cards, column_cards, or table rows.\n\n"
                "HEADLINE RULE: Every slide title MUST be an insight assertion — a claim a senior executive would quote. "
                "Test: a good title completes 'This deck argues that ___.' "
                "BAD: 'Risk Management' | GOOD: 'Four Failure Modes That Derail Programs Like This' "
                "BAD: 'Current State Overview' | GOOD: 'Manual Reconciliation Consumes 40% of Finance Capacity' "
                "BAD: 'Proposed Approach' | GOOD: 'A Five-Layer Operating Model That Eliminates the Bottleneck' "
                "BAD: 'Process Scale & Scope' | GOOD: 'Manual Work Consumes 40% of Capacity' "
                "BAD: 'Three Pillars' | GOOD: 'Three Levers That Collapse the Bottleneck' "
                "BAD: 'Savings Opportunity' | GOOD: '$400M Left on the Table Annually'\n\n"
                "VISUAL RHYTHM: Use fill values to signal slide purpose:\n"
                "  'dark'     → heavyweight impact: economic reframe, proof trace, evidence\n"
                "  'green'    → opportunity/action: solution pillars, win themes, calls-to-action\n"
                "  'mid_dark' → evidence: delivery phases, secondary proof metrics, step boxes\n"
                "  'gray'     → reference/detail: supporting tables, supplementary stats\n"
                "Within stat_cards and column_cards, ALWAYS vary fills across cards "
                "(e.g., dark/mid_dark/gray or dark/green/gray). "
                "Never assign the same fill to all cards in one slide.\n\n"
                "SECTION RHYTHM: For 10+ slide decks, insert slide_type='section_divider' "
                "between major narrative acts (after slide 3 and after slide 7). "
                "section_divider title = the act's governing question (e.g., 'Why Act Now?').\n\n"
                "EYEBROW: Set the 'subtitle' field to a short ALL-CAPS context label "
                "(2–4 words, e.g., 'THE CENTRAL INSIGHT', 'REDEFINING THE BOTTLENECK'). "
                "This renders above the main title as visual hierarchy.\n\n"
                "EXAMPLE — stat_cards slide (slide_type=\"stat_cards\"):\n"
                '{"slide_type": "stat_cards", "title": "Manual Work Consumes 40% of Finance Capacity", "stat_cards": [\n'
                '  {"stat": "14", "label": "Process Steps", "description": "Each a manual handoff that adds cycle time and error risk", "fill": "dark"},\n'
                '  {"stat": "5", "label": "Key Roles", "description": "Procurement, Finance, Stores, Treasury, Vendors — all in silos", "fill": "mid_dark"},\n'
                '  {"stat": "$450M", "label": "Annual Spend at Risk", "description": "High-volume P2P with no automated controls", "fill": "gray"}\n'
                ']}\n\n'
                "EXAMPLE — column_cards slide (slide_type=\"column_cards\"):\n"
                '{"slide_type": "column_cards", "title": "Three Levers That Collapse the Bottleneck", "column_cards": [\n'
                '  {"heading": "Governance", "accent": "green", "body": "Centralize vendor master; enforce controls before a single invoice is processed"},\n'
                '  {"heading": "Quality Gates", "accent": "dark", "body": "Activate QM module; block failures at source, not after the fact"},\n'
                '  {"heading": "End-to-End Automation", "accent": "gray", "body": "OCR invoices; DMEE payment integration — zero manual keying"}\n'
                ']}\n\n'
                "EXAMPLE — table slide (slide_type=\"table\"):\n"
                '{"slide_type": "table", "title": "The Handoff Map: Where Delays Compound", "table": {\n'
                '  "headers": ["Step", "Owner", "Inputs → Outputs"],\n'
                '  "rows": [\n'
                '    ["1. Create PR", "Dept Head", "Material list → PR in ME51N"],\n'
                '    ["2. Countersign", "Finance", "PR >INR 50K → Approved"],\n'
                '    ["3. Create PO", "Procurement", "PR → PO in ME21N"]\n'
                "  ]\n"
                '}}\n\n'
                "EXAMPLE — chart slide (slide_type=\"chart\"):\n"
                '{"slide_type": "chart", "title": "Savings Accelerate After Month 6", "chart": {\n'
                '  "type": "column", "categories": ["Q1","Q2","Q3","Q4"],\n'
                '  "series": [{"name": "Cumulative Savings ($M)", "values": [15, 38, 65, 92]}],\n'
                '  "subtitle": "Source: FY2024 management accounts"\n'
                '}}\n\n'
                "EXAMPLE — big_number slide (slide_type=\"big_number\"):\n"
                '{"slide_type": "big_number", "title": "$400M Left on the Table Annually", "big_number": {\n'
                '  "stat": "$400M–$600M", "label": "Annual Savings Run-Rate",\n'
                '  "context": "Achievable by Month 18 with full $6B spendbase coverage.", "fill": "dark"}}\n\n'
                "EXAMPLE — process_flow slide (slide_type=\"process_flow\"):\n"
                '{"slide_type": "process_flow", "title": "Five Steps, One Owner at Each Gate", "process_flow": {"steps": [\n'
                '  {"label": "Initiation", "description": "Request raised in ERP system", "fill": "dark"},\n'
                '  {"label": "Review", "description": "Finance validates against approved budget", "fill": "green"},\n'
                '  {"label": "Approval", "description": "CFO signs off digitally", "fill": "mid_dark"}\n'
                ']}}\n\n'
                "RULE: Do NOT generate empty stat_cards=[], column_cards=[], or table.rows=[]. Always populate with real data.\n"
            ),
        )
        sb = _append_archetype_prompt(sb, ctx, "pptx")
        # Executive-deck consistency & altitude rules (applied on every pptx path).
        sb = _SkillBuild(
            system=sb.system + (
                "\n\nCONSISTENCY & ALTITUDE RULES:\n"
                "1. OWNERSHIP IS SINGLE-SOURCED. Take each step's owner verbatim from the process "
                "model's step.role. State an activity's owner identically on every slide it appears "
                "on — never reassign or paraphrase ownership differently across slides.\n"
                "2. OUTCOME METRICS, NOT PROCESS DESCRIPTORS. stat_cards and big_number must show "
                "business outcomes (time saved, cycle time, cost per unit, accuracy %, throughput, "
                "$ impact). Do NOT headline raw process counts (number of steps/roles) as if they "
                "were efficiency metrics; if only a count is available, pair it with the outcome it "
                "drives.\n"
                "3. NO RAW ACCOUNTING CODES. Do not surface GL codes, cost-center codes, or GST/tax "
                "treatment codes on executive slides unless the user explicitly asked for them; "
                "express governance and compliance in business terms.\n"
            ),
            temperature=sb.temperature,
            max_rounds=sb.max_rounds,
        )
        plan_discovery = (ctx.plan_payload or {}).get("discovery") if isinstance((ctx.plan_payload or {}).get("discovery"), dict) else {}
        # Fill narrative_arc from deck_outline_preview when plan discovery omits it.
        if not plan_discovery.get("narrative_arc"):
            _outline_arc = str(
                ((ctx.plan_payload or {}).get("deck_outline_preview") or {}).get("narrative_arc") or ""
            ).strip().lower()
            if _outline_arc:
                plan_discovery = {**plan_discovery, "narrative_arc": _outline_arc}
        is_proposal_skill = bool(str(primary.get("id") or "").startswith("proposal_")) if isinstance(primary, dict) else False
        company_name = getattr(ctx.branding, "company_name", None) or "Deloitte"
        n_steps = len(pm.get("steps") or [])
        discovery_budget = (plan_discovery.get("length_budget") if isinstance(plan_discovery.get("length_budget"), dict) else {})
        budget_pptx = int(discovery_budget.get("pptx")) if str(discovery_budget.get("pptx") or "").isdigit() else None
        if is_proposal_skill and budget_pptx:
            n_slides_guidance = f"{max(10, min(budget_pptx, 16))} slides"
        elif is_proposal_skill:
            n_slides_guidance = "12–14 slides"
        elif n_steps <= 3:
            n_slides_guidance = "6 slides"
        elif n_steps <= 6:
            n_slides_guidance = "7–8 slides"
        else:
            n_slides_guidance = "8–10 slides"

        # ── Storyline spine (Pillar A): planned, arc-anchored slide sequence ──
        # Authored once per run by the planning-tier model and shared with DOCX.
        _target_slides = max(8, min(14, n_steps + 4))
        _spine_block = _storyline_spine_block(ctx, pm, plan_discovery, _target_slides)
        if _spine_block:
            sb = _SkillBuild(
                system=sb.system + "\n\n" + _spine_block,
                temperature=sb.temperature,
                max_rounds=sb.max_rounds,
            )

        # ── Inject enriched context metrics (Phase 1 fix) ──────────────────────
        enrichment = ctx.enrichment
        analytics = getattr(enrichment, "process_analytics", None) if enrichment else None
        steps_count = analytics.steps_count if analytics else n_steps
        roles_count = analytics.roles_count if analytics else len(set(s.get("role") or s.get("owner") for s in pm.get("steps", []) if isinstance(s, dict)))
        analytics.decision_points if analytics else len(pm.get("decisions", []) or [])
        systems_count = len(pm.get("systems", [])) if isinstance(pm.get("systems"), list) else 3

        # Extract risks and value drivers from enrichment
        risk_profile = getattr(enrichment, "risk_profile", None) if enrichment else None
        risk_profile.risks if risk_profile else pm.get("risks", [])
        getattr(enrichment, "value_drivers", []) if enrichment else pm.get("improvement_opportunities", [])

        # Build data injection for key slides
        data_for_slide_2 = (
            f"\nDATA FOR SLIDE 2 (stat_cards) — MUST POPULATE WITH THESE METRICS:\n"
            f"- Card 1: stat=\"{steps_count}\", label=\"Process Steps\", "
            f"description=\"End-to-end workflow from initiation to completion\"\n"
            f"- Card 2: stat=\"{roles_count}\", label=\"Key Roles\", "
            f"description=\"Departments and stakeholders involved in execution\"\n"
            f"- Card 3: stat=\"{systems_count}\", label=\"System Touchpoints\", "
            f"description=\"Applications and tools required for automation\"\n"
        )

        extracted_metrics = pm.get("metrics") or []
        if extracted_metrics and isinstance(extracted_metrics, list):
            metric_hints = "\n".join(
                f"  - stat=\"{m.get('stat', '')}\", label=\"{m.get('label', '')}\", "
                f"source=\"{m.get('source', 'inferred from context')}\""
                for m in extracted_metrics[:3]
                if isinstance(m, dict) and m.get("stat") and m.get("label")
            )
            if metric_hints:
                data_for_slide_7 = (
                    f"\nDATA FOR SLIDE 7 (stat_cards) — use these extracted metrics:\n"
                    f"{metric_hints}\n"
                    "Each card MUST have stat, label, and description. "
                    "Cite source inline using the source field provided.\n"
                )
            else:
                data_for_slide_7 = (
                    "\nDATA FOR SLIDE 7 (stat_cards) — derive 3 metrics from the ProcessModel "
                    "(cycle time, error rate, control points, SLA, or volume counts). "
                    "Each card needs stat, label, description. Omit a card entirely if no quantifiable value is available — never use placeholder text like [TBC].\n"
                )
        else:
            data_for_slide_7 = (
                "\nDATA FOR SLIDE 7 (stat_cards) — derive 3 metrics from the ProcessModel "
                "(cycle time, error rate, control points, SLA, or volume counts). "
                "Each card needs stat, label, description. Omit a card entirely if no quantifiable value is available — never use placeholder text like [TBC].\n"
            )

        deck_outline_for_title = (ctx.plan_payload or {}).get("deck_outline_preview") if isinstance(ctx.plan_payload, dict) else None
        presentation_title = _resolve_presentation_title(
            pm,
            {"user_intent_original": ctx.user_intent_original},
            discovery=plan_discovery if isinstance(plan_discovery, dict) else None,
            deck_outline=deck_outline_for_title if isinstance(deck_outline_for_title, dict) else None,
        )

        # ── Skill-aware slide sequence ──────────────────────────────────────
        # If the primary skill defines a slide_sequence (e.g., proposal skills
        # have a different structure than process documentation), use it.
        # This allows each domain skill to control the slide ordering via
        # SKILL.md configuration rather than hardcoded Python.

        # ── Shared slide schema (used by both skill-aware and fallback paths) ──
        # Detect editorial theme context for vocabulary block.
        _editorial_theme = False
        try:
            _branding_ctx = getattr(ctx, "branding", None)
            if _branding_ctx:
                _dt = str(getattr(_branding_ctx, "deck_theme", "") or "").lower()
                if not _dt:
                    from src.core.config import settings as _s
                    _dt = "editorial" if getattr(_s, "pptx_editorial_theme_enabled", False) else "classic"
                _editorial_theme = (_dt == "editorial")
        except Exception as exc:
            _LOG.warning("%s: suppressed error: %s", 'run_pptx_agent', exc)

        _slide_schema = (
            "Each slide object schema (omit fields that are null):\n"
            "  title         string — ≤10 words (required)\n"
            "  slide_type    string — one of: title | bullets | stat_cards | column_cards |\n"
            "                         stack_layers | table | chart | section_divider |\n"
            "                         big_number | process_flow"
            + (" | split_panel | lanes | workstream_cards | tower_cards |\n"
               "                         roadmap_matrix | swimlane_timeline | flagship_cards" if _editorial_theme else "")
            + " (required)\n"
            "  subtitle      string | null — eyebrow/section label (ALL-CAPS, ≤5 words)\n"
            "  kicker        string | null — italic sub-headline below title (≤20 words)\n"
            "  section_number string | null — 2-digit section index (e.g. \"02\")\n"
            "  emphasis      string | null — substring of title to render in primary color\n"
            "  status_legend bool | null — show status legend (workstream_cards / tower_cards)\n"
            "  synthesis_band {label: string, text: string, right_label?: string, right_text?: string} | null\n"
            "                — full-width dark takeaway band; use ≤1 per 3 slides\n"
            "  bullets       string[] | null — each ≤15 words; for slide_type=\"bullets\"\n"
            "  badges        string[] | null — short phrases for title slide pills (slide_type=\"title\" only)\n"
            "  stat_cards    [{stat: string, label: string, description: string, fill: \"dark\"|\"mid_dark\"|\"gray\"}] | null\n"
            "                — stat: short metric (e.g. \"3–5\"); label: 2–4 word title;\n"
            "                  description: 1 sentence of context (≤25 words, tells the reader *why* it matters)\n"
            "  column_cards  [{heading: string, accent: \"green\"|\"dark\"|\"gray\"|\"mid_dark\"|\"mid\"|\"dark_green\", body: string}] | null\n"
            "                — 2–4 cards (3 is the typical framework width); body ≤40 words;\n"
            "                  heading must directly name the pillar described in body — never use a\n"
            "                  heading that labels a different theme than what body actually says\n"
            "  stack_layers  [{label: string, description: string, fill: \"green\"|\"dark\"|\"mid_dark\"|\"gray\"|\"mid\"|\"dark_green\"}] | null\n"
            "                — 3–6 rows; label ≤3 words; description ≤20 words\n"
            "  footer_note   string | null — single-line summary band at slide bottom (use sparingly)\n"
            "  table         {headers: string[], rows: string[][], x: 0.28, y: 1.0, w: 9.44, h: 4.3} | null\n"
            "  chart         {type: \"bar\"|\"line\"|\"pie\"|\"column\"|\"area\"|\"doughnut\"|\"column_stacked\"|\"percent_stacked\"|\"bar_stacked\",\n"
            "                 categories: string[] (3-8), series: [{name: string, values: number[]}],\n"
            "                 subtitle: string (cite source ≤15 words)} | null\n"
            "                — use when trend shape, ranking, or composition is the story\n"
            "  big_number    {stat: string, label: string, context?: string, fill: \"dark\"|\"green\"|\"mid_dark\"} | null\n"
            "                — renders stat at 80pt; use for ONE dominant KPI; at most once per deck\n"
            "  process_flow  {steps: [{label: string ≤4 words, description: string ≤12 words,\n"
            "                          fill: \"green\"|\"dark\"|\"mid_dark\"|\"dark_green\"|\"mid\", icon?: string}]} | null\n"
            "                — horizontal arrow chain for ordered steps; 2–5 steps required\n"
            + (
            "  split_panel   items: [{label: string, body: string}] — 2–5 numbered items;\n"
            "                dark left panel shows the key assertion, right shows numbered detail\n"
            "  lanes         lanes: [{label: string, items: [string]}] — 2–4 parallel swim lanes;\n"
            "                each lane has a labelled column chip + 2–5 numbered items\n"
            "  workstream_cards  workstream_cards: [{heading: string, owner: string|null, body: string,\n"
            "                    status: \"live\"|\"in_build\"|\"planned\"|\"partner\"|null}] — 3–6 cards;\n"
            "                    set status_legend: true when statuses are mixed\n"
            "  tower_cards   tower_cards: [{heading: string, items: [{text: string, status?: string}|string],\n"
            "                takeaway?: string}] — 3–5 towers; teal header + item list + optional takeaway strip\n"
            "  roadmap_matrix  roadmap_matrix: {periods: [string], tracks: [{label: string,\n"
            "                  cells: [{label: string, status: \"live\"|\"in_build\"|\"planned\"|\"partner\"|null}]}]}\n"
            "                  — quarter×workstream grid; ≤8 periods, ≤6 tracks\n"
            "  swimlane_timeline  swimlane_timeline: {periods: [string], lanes: [{label: string,\n"
            "                     bars: [{start: int, end: int, label: string, status?: string}]}]}\n"
            "                     — Gantt; start/end are 0-based period indices\n"
            "  flagship_cards  flagship_cards: [{heading: string, body: string,\n"
            "                  kpis?: [{label: string, value: string}], client?: string}] — 2–3 cards\n"
            if _editorial_theme else ""
            )
            + "\nRules:\n"
            "  - title and slide_type are required on every slide.\n"
            "  - stat_cards: include only cards where a real quantifiable value exists; omit cards with no data rather than using placeholder text. Aim for 3 but 1 or 2 is acceptable.\n"
            "  - column_cards must have 2–4 items.\n"
            "  - Do not mix bullets + table on the same slide.\n"
            + ("  - emphasis: use to highlight 1–3 key words in the title — must be a verbatim substring.\n"
               "  - status discipline: live=currently active; in_build=in development; planned=on roadmap; partner=third-party led.\n"
               "  - synthesis_band: 1 band per major section break maximum; short assertions only.\n"
               if _editorial_theme else "")
            + "  - Return ONLY valid JSON: {\"slides\": [...]}\n\n"
        )

        skill_slide_sequence = primary.get("slide_sequence") if primary else None
        if isinstance(skill_slide_sequence, list) and skill_slide_sequence:
            slide_mandate_lines = [f"{i}. {step}" for i, step in enumerate(skill_slide_sequence, 1)]
            slide_mandate = "\n".join(slide_mandate_lines)
            user_core = (
                f"Create a {n_slides_guidance} executive presentation grounded in the ProcessModel AND any excerpts "
                "below (user instruction, assembled context, prior narrative/document drafts).\n"
                f"Use {company_name} visual conventions: varied slide types, not just bullets.\n"
                f"Refer to the delivery firm as '{company_name}' throughout — never use generic 'the firm'.\n"
                f"Presentation title (use exactly): \"{presentation_title}\"\n"
                + data_for_slide_2 + data_for_slide_7 + "\n"
                f"Slide ordering mandate (follow this sequence):\n{slide_mandate}\n\n"
                + _slide_schema
            )
        else:
            # Default sequence (proposal-aware when discovery is available)
            arc = str(plan_discovery.get("narrative_arc") or "").strip().lower()
            proposal_mandate = {
                "scqa": (
                    "1. slide_type=\"title\" — tagline = one-sentence deck thesis; badges = 3 quantified stakes (e.g., FTE count, annual spend, cycle time)\n"
                    "2. slide_type=\"big_number\" or \"stat_cards\" — Situation/Complication: MUST quantify the cost of status quo "
                    "in economic or competitive terms (e.g., '40% of capacity wasted on manual work', "
                    "'peers automate at 1/10th your cost per transaction'); NO generic current-state description\n"
                    "3. slide_type=\"column_cards\" or \"bullets\" — Key Question: frame as the board decision the audience must make; "
                    "name the consequences of each path (transform now vs. defer); use 2–3 columns or bullets\n"
                    "4. slide_type=\"stack_layers\" (3–5 layers) — Answer/Hypothesis: show the transformation architecture "
                    "at three levels — (a) strategy/outcome, (b) platform/operating model, (c) interface/experience — "
                    "NOT a flat feature list; each layer title must be an assertion\n"
                    "5. slide_type=\"stat_cards\" or \"chart\" — Evidence & Value: 3 proof metrics with named source citation "
                    "(e.g., 'Gartner 2024', 'Peer benchmark — F500 manufacturer'); benchmarks must be source-named, not generic\n"
                    "6. slide_type=\"process_flow\" or \"stack_layers\" — Delivery Approach: show 3 deployment phases/paths "
                    "with named milestones, timeline, and a named owner role at each gate\n"
                    "7. slide_type=\"table\" or \"column_cards\" — Risks & Failure Modes: MUST name 3–5 specific failure modes "
                    "with concrete consequence (time lost, money at risk, or control gap), then the mitigation for each; "
                    "NO generic risk language like 'change management risk' — name the actual failure\n"
                    "8. slide_type=\"big_number\" or \"stat_cards\" — Proof Trace: show a worked example, case outcome, or "
                    "reference implementation with specific numbers (e.g., '$4.8M identified, 23 minutes, 85% confidence'); "
                    "this is the concrete proof the approach works — not theoretical\n"
                    "9. slide_type=\"chart\" or \"table\" — Commercial View: show investment vs. return trajectory with "
                    "payback period; include Phase 1 cost estimate\n"
                    "10. slide_type=\"bullets\" — Next Actions: exactly 3 numbered actions, each with a named owner role "
                    "(not a person name), tied to a specific date or decision gate, ≤15 words each"
                ),
                "pyramid": (
                    "1. slide_type=\"title\" — Governing thought as tagline: state the headline conclusion, not the process name\n"
                    "2. slide_type=\"big_number\" or \"stat_cards\" — Supporting argument 1: the economic cost of the problem; "
                    "quantify with a named metric (e.g., '$X wasted annually', 'Y% capacity absorbed by manual work')\n"
                    "3. slide_type=\"column_cards\" — Supporting argument 2: the three structural causes of the problem; "
                    "each column names a root cause, not a symptom\n"
                    "4. slide_type=\"stack_layers\" — Supporting argument 3: the solution architecture at strategy → platform → "
                    "operating model levels; each layer is an assertion\n"
                    "5. slide_type=\"stat_cards\" — Evidence: 3 proof metrics from named external sources\n"
                    "6. slide_type=\"chart\" or \"table\" — Proof: show trajectory or comparative data that validates the approach\n"
                    "7. slide_type=\"process_flow\" or \"stack_layers\" — Implementation roadmap: phases with milestones, owners, dates\n"
                    "8. slide_type=\"table\" — Risks & Failure Modes: 3–5 named failure modes with consequences and mitigations\n"
                    "9. slide_type=\"chart\" — Commercial View: investment vs. return; payback timeline\n"
                    "10. slide_type=\"bullets\" — Decision ask and next actions: 3 numbered items with owner roles and dates"
                ),
                "case_led": (
                    "1. slide_type=\"title\" — Client context as tagline: name the client, the industry, and the headline challenge\n"
                    "2. slide_type=\"big_number\" or \"stat_cards\" — Case for change: quantify the competitive or economic "
                    "consequence of the status quo; reframe from 'we have a problem' to 'here is what it costs you annually'\n"
                    "3. slide_type=\"column_cards\" — Target outcomes: 3 measurable outcomes the engagement will deliver "
                    "(not activities — outcomes with numbers: '60% cycle time reduction', '$50M cost removal')\n"
                    "4. slide_type=\"stack_layers\" — Proposed approach (part 1): transformation architecture at 3 levels — "
                    "strategy, platform, operating model\n"
                    "5. slide_type=\"process_flow\" or \"table\" — Proposed approach (part 2): phased delivery plan with "
                    "milestones, owners, and timelines\n"
                    "6. slide_type=\"stat_cards\" or \"chart\" — Proof points: 3 metrics from comparable engagements or "
                    "industry benchmarks with source citations\n"
                    "7. slide_type=\"table\" or \"column_cards\" — Risks & Failure Modes: 3–5 named failure modes with "
                    "concrete consequences and mitigations\n"
                    "8. slide_type=\"big_number\" or \"stat_cards\" — Proof Trace: concrete case outcome or worked example "
                    "with specific numbers; shows the approach is proven\n"
                    "9. slide_type=\"chart\" or \"table\" — Commercial view: investment vs. return; payback period\n"
                    "10. slide_type=\"bullets\" — Next actions: 3 items with named owner roles and specific dates"
                ),
                "compare": (
                    "1. Decision context\n2. Option criteria\n3-5. Option comparison\n6. Recommended option\n"
                    "7. Delivery implications\n8. Next actions"
                ),
            }.get(arc)
            user_core = (
                f"Create a {n_slides_guidance} executive presentation grounded in the ProcessModel AND any excerpts "
                "below (user instruction, assembled context, prior narrative/document drafts).\n"
                f"Use {company_name} visual conventions: varied slide types, not just bullets.\n"
                f"Refer to the delivery firm as '{company_name}' throughout — never use generic 'the firm'.\n"
                f"Presentation title (use exactly): \"{presentation_title}\"\n"
                + (data_for_slide_2 if not is_proposal_skill else "") + data_for_slide_7 + "\n"
                + (
                    f"Slide ordering mandate ({arc or 'default'}):\n{proposal_mandate}\n\n"
                    if is_proposal_skill and proposal_mandate
                    else
                    "Slide ordering mandate (follow this sequence):\n"
                    f"1. slide_type=\"title\" — title=\"{presentation_title}\", subtitle=\"Process Overview\",\n"
                    "   badges=[derive ONLY from this ProcessModel: use step count, role count, system count,\n"
                    "   or the actual names of the first 2–3 process steps/phases from the data provided —\n"
                    "   never invent generic labels like 'P2P Standardization' or 'SAP Automation' unless\n"
                    "   they appear verbatim in the process data]\n"
                    "2. slide_type=\"stat_cards\" — exactly 3 cards quantifying scale/impact metrics;\n"
                    "   derive from step count, role count, or ProcessModel.metadata; fills: dark, mid_dark, gray\n"
                    "   each card MUST have a description: 1 sentence (10–20 words) explaining the metric's significance\n"
                    "3. slide_type=\"column_cards\" OR \"process_flow\" — use column_cards for three-pillar frameworks;\n"
                    "   use process_flow when 3–5 steps are strictly ordered (process_flow.steps: 2–5 items);\n"
                    "   column_cards: accent: green, dark, gray, mid_dark, mid, or dark_green; 2–4 items (3 is typical)\n"
                    "4. slide_type=\"stack_layers\" — 3–6 rows showing workflow phases or architecture layers;\n"
                    "   fills rotate: green, mid_dark, dark, gray, mid, dark_green\n"
                    "5. slide_type=\"bullets\" — Process Overview: one bullet per role mandate\n"
                    "6. slide_type=\"table\" — Workflow Walkthrough: headers=[Step, Owner, Inputs → Outputs];\n"
                    "   one row per ProcessModel.steps entry\n"
                    "7. slide_type=\"chart\" (if time-series or benchmark data exists),\n"
                    "   OR \"big_number\" (if one metric is the headline — big_number.fill must be dark/green/mid_dark),\n"
                    "   OR \"stat_cards\" (3 parallel KPIs). NEVER use \"bullets\" for slide 7.\n"
                    "   Each card/field must have a real quantifiable value; omit if no data — never use [TBC]\n"
                    "8+ (if more slides needed): slide_type=\"bullets\", \"column_cards\", \"chart\", or \"process_flow\"\n"
                    "Final slide: slide_type=\"bullets\", title=\"Recommended Next Actions\",\n"
                    "   bullets=[exactly 3 numbered actions specific to this process, each ≤15 words]\n\n"
                )
                + _slide_schema
            )
        appendix = _shared_user_context_appendix(ctx)
        if plan_discovery:
            discovery_lines = []
            client = plan_discovery.get("client") if isinstance(plan_discovery.get("client"), dict) else {}
            outcome = plan_discovery.get("outcome") if isinstance(plan_discovery.get("outcome"), dict) else {}
            themes = plan_discovery.get("win_themes") if isinstance(plan_discovery.get("win_themes"), list) else []
            audience = str(plan_discovery.get("audience") or "").strip()
            tone = str(plan_discovery.get("tone") or "").strip()
            narrative_arc = str(plan_discovery.get("narrative_arc") or "").strip()
            if client:
                discovery_lines.append(
                    f"Client context: {client.get('name', '')} ({client.get('industry', '')})"
                )
            if outcome:
                discovery_lines.append(
                    f"Desired outcome: {outcome.get('primary', '')}; decision: {outcome.get('decision', '')}"
                )
            if audience:
                discovery_lines.append(f"Primary audience: {audience}")
            if narrative_arc:
                discovery_lines.append(f"Narrative arc: {narrative_arc}")
            if tone:
                discovery_lines.append(f"Tone: {tone}")
            if themes:
                discovery_lines.append("Win themes: " + ", ".join(str(x) for x in themes[:5]))
            # Synthesise a single thesis statement that anchors every slide title
            primary_outcome = str(outcome.get("primary") or "").strip() if outcome else ""
            first_theme = str(themes[0]).strip() if themes else ""
            if primary_outcome:
                deck_thesis = primary_outcome
                if first_theme and first_theme.lower() not in primary_outcome.lower():
                    deck_thesis = f"{primary_outcome}, anchored in {first_theme}"
                discovery_lines.insert(0,
                    f"DECK THESIS (every slide must reinforce this): \"{deck_thesis}\". "
                    "State it explicitly on slide 2 as the economic reframe — quantify the cost of the status quo "
                    "or the competitive gap in concrete numbers. "
                    "Every subsequent slide title must be a specific argument FOR this thesis, not a topic label."
                )
            if discovery_lines:
                appendix = (
                    appendix
                    + "\n\n## Discovery inputs (ground every slide in this client's reality)\n- "
                    + "\n- ".join(discovery_lines)
                    + "\nNEVER use generic placeholders like \"the client\" or \"this process\" — "
                    + "refer to the client by name and speak to the primary audience directly."
                )
        wiki_refs_list = (ctx.plan_payload or {}).get("wiki_context_refs") if isinstance(ctx.plan_payload, dict) else None
        if isinstance(wiki_refs_list, list) and wiki_refs_list:
            clean_refs = [str(r).strip() for r in wiki_refs_list if str(r).strip()]
            if clean_refs:
                appendix = (
                    appendix
                    + "\n\n## Grounded in project wiki pages\n- "
                    + "\n- ".join(clean_refs[:10])
                    + "\nWhen a slide draws on one of these sources, phrase content consistent with it "
                    + "and do not invent metrics that contradict the wiki."
                )
        user = user_core + appendix + f"{process_model_json_block(pm)}"
        visual_feedback: list[dict] = (ctx.plan_payload or {}).get("pptx_visual_feedback") or []
        if visual_feedback and isinstance(visual_feedback, list):
            hints_text = "\n".join(
                f"- Slide {h.get('slide_index', '?')}: {h.get('instruction', '')}"
                for h in visual_feedback
                if isinstance(h, dict) and h.get("instruction")
            )
            if hints_text:
                user = (
                    user
                    + f"\n\nVisual QA feedback from previous generation (must be addressed):\n{hints_text}"
                )
        pptx_narrative_fb: list[dict] = (ctx.plan_payload or {}).get("pptx_narrative_feedback") or []
        if pptx_narrative_fb and isinstance(pptx_narrative_fb, list):
            _narr_hints = "\n".join(
                f"- {h.get('instruction', '')}"
                for h in pptx_narrative_fb
                if isinstance(h, dict) and h.get("instruction")
            )
            if _narr_hints:
                user = (
                    user
                    + "\n\nNarrative coherence feedback from previous generation "
                    "(address in slide titles and story arc — tighten transitions, "
                    "eliminate topic drift, ensure every slide title asserts a specific claim):\n"
                    + _narr_hints
                )
        prior_slides_raw = (ctx.plan_payload or {}).get("prior_pptx_slides")
        prior_slides: list[dict[str, Any]] | None = None
        if isinstance(prior_slides_raw, list):
            prior_slides = [s for s in prior_slides_raw if isinstance(s, dict)]
        fix_indices = _pptx_visual_feedback_indices(visual_feedback) if visual_feedback and isinstance(visual_feedback, list) else set()
        repair_mode = bool(prior_slides and fix_indices)
        if repair_mode and prior_slides:
            # Bound the prompt: non-fixed slides are restored verbatim from the
            # prior deck by _merge_pptx_slides_repair, so only the slides being
            # fixed need full JSON — the rest are positional stubs.
            deck_for_prompt = [
                s if (i + 1) in fix_indices
                else {"slide_index": i + 1, "title": s.get("title"), "slide_type": s.get("slide_type"), "unchanged": True}
                for i, s in enumerate(prior_slides)
            ]
            user += (
                "\n\n## VISUAL QA REPAIR (targeted slides only)\n"
                f"Return JSON {{\"slides\": [...]}} with exactly {len(prior_slides)} slides "
                "in the same order as PRIOR_DECK below.\n"
                f"Replace ONLY slides at these 1-based indices: {sorted(fix_indices)} "
                "to satisfy the Visual QA feedback above.\n"
                "For all other positions, return the PRIOR_DECK stub at that position unchanged "
                "(slides marked \"unchanged\": true keep their prior content automatically).\n\n"
                "PRIOR_DECK:\n"
                + json.dumps(deck_for_prompt, ensure_ascii=False)
            )
        # ── Batched generation (when the user approved a deck outline) ──
        # We lower the threshold to 3 slides so any reasonable approved outline
        # drives generation — the old 6-slide cutoff meant short proposal decks
        # fell back to the default "Process Overview" mandate and ignored the
        # user's confirmed storyline.
        batched_slides: list[dict] | None = None
        deck_outline_raw = (ctx.plan_payload or {}).get("deck_outline_preview")
        if (
            not repair_mode
            and isinstance(deck_outline_raw, dict)
            and isinstance(deck_outline_raw.get("slides"), list)
            and len(deck_outline_raw["slides"]) >= 3
        ):
            batched_slides = _shared._generate_slides_batched(
                ctx,
                system=sb.system,
                user_core=user_core,
                appendix=appendix,
                pm=pm,
                outline=deck_outline_raw["slides"],
                temperature=sb.temperature,
                max_rounds=sb.max_rounds,
                presentation_title=presentation_title,
            )

        if batched_slides:
            # region agent log
            _session_debug_log(
                run_id=ctx.run_id,
                hypothesis_id="H5",
                location="subagents.py:run_pptx_agent:batched",
                message="PPTX slides generated via batched mode",
                data={"slide_count": len(batched_slides), "used_primary_skill_id": str(primary.get("id") or "")},
            )
            # endregion
            slide_dicts = batched_slides
            json_str = json.dumps({"slides": slide_dicts}, ensure_ascii=False)
            json_str = _shared._apply_quality_gate(ctx, "pptx", json_str, system=sb.system, temperature=sb.temperature)
            try:
                obj2 = _extract_first_json_object(json_str)
                slides2 = obj2.get("slides") if isinstance(obj2, dict) else None
                if isinstance(slides2, list) and slides2:
                    slide_dicts = [s for s in slides2 if isinstance(s, dict)] or slide_dicts
            except Exception:  # noqa: S110 — best-effort, non-fatal
                pass
            slide_dicts = _shared._run_pptx_post_processor(ctx, slide_dicts)
            slide_dicts = _critique_and_repair_pptx(ctx, slide_dicts, pm)
            slide_dicts = _normalize_pptx_slide_identities(slide_dicts)
            return AgentOutput(updates={"pptx_slides": slide_dicts})

        # ── Single-shot generation (default path) ──
        raw_json = _shared._run_subagent_tool_loop_text(ctx, agent_id="pptx", system=sb.system, user=user, temperature=sb.temperature, max_rounds=sb.max_rounds)
        obj: dict | None = None
        if raw_json:
            try:
                obj = _extract_first_json_object(raw_json)
            except Exception:
                obj = None
        if not obj:
            try:
                obj = _shared.claude_generate_json(system=sb.system, user=user, temperature=sb.temperature, max_tokens=8192)
            except Exception:
                obj = None
        slides = obj.get("slides") if isinstance(obj, dict) else None
        if isinstance(slides, list) and slides:
            slide_dicts = [s for s in slides if isinstance(s, dict)]
            if slide_dicts:
                if repair_mode and prior_slides:
                    slide_dicts = _merge_pptx_slides_repair(prior_slides, slide_dicts, fix_indices)
                json_str = json.dumps({"slides": slide_dicts}, ensure_ascii=False)
                json_str = _shared._apply_quality_gate(ctx, "pptx", json_str, system=sb.system, temperature=sb.temperature)
                try:
                    obj2 = _extract_first_json_object(json_str)
                    slides2 = obj2.get("slides") if isinstance(obj2, dict) else None
                    if isinstance(slides2, list) and slides2:
                        slide_dicts = [s for s in slides2 if isinstance(s, dict)] or slide_dicts
                except Exception:  # noqa: S110 — best-effort, non-fatal
                    pass
                slide_dicts = _shared._run_pptx_post_processor(ctx, slide_dicts)
                slide_dicts = _critique_and_repair_pptx(ctx, slide_dicts, pm)
                slide_dicts = _normalize_pptx_slide_identities(slide_dicts)
                # region agent log
                _session_debug_log(
                    run_id=ctx.run_id,
                    hypothesis_id="H5",
                    location="subagents.py:run_pptx_agent:generated",
                    message="PPTX slides generated via tool loop / model",
                    data={
                        "slide_count": len(slide_dicts),
                        "repair_mode": bool(repair_mode),
                        "used_primary_skill_id": str(primary.get("id") or ""),
                    },
                )
                # endregion
                return AgentOutput(updates={"pptx_slides": slide_dicts})

    fallback_slides = _normalize_pptx_slide_identities(_pptx_deterministic_slides(pm, _load_run_storyline(ctx)))
    # region agent log
    _session_debug_log(
        run_id=ctx.run_id,
        hypothesis_id="H5",
        location="subagents.py:run_pptx_agent:fallback",
        message="PPTX slides generated via deterministic fallback",
        data={
            "slide_count": len(fallback_slides),
            "used_primary_skill_id": str(primary.get("id") or ""),
        },
    )
    # endregion
    return AgentOutput(updates={"pptx_slides": fallback_slides})
