"""The consulting slide standard the deck pipeline writes to.

One place for the visual vocabulary (slide types the renderer draws well, with the fields
each one needs) and the rules that make a slide read like a Big4 deliverable. The outline
step, the slide negotiator and the deck agent all build their prompts from this module, so
a visual the renderer supports can actually be chosen and filled.
"""

from __future__ import annotations

# slide_type -> (label shown to users, the JSON fields the renderer reads)
VISUALS: dict[str, tuple[str, str]] = {
    "stat_cards": ("KPI tiles", 'stat_cards: [{stat: "18 days", label, description, icon}] — 3 tiles'),
    "column_cards": ("Column cards", "column_cards: [{heading, body (≤160 chars), icon}] — 3 or 4 cards"),
    "process_flow": ("Phased flow", "process_flow: {steps: [{label, description, icon}]} — 3 to 5 ordered steps"),
    "table": ("Comparison table", "table: {headers: [..], rows: [[..], ..]} — ≤8 rows"),
    "chart": ("Chart", "chart: {type: column|bar|line|pie|doughnut|column_stacked, categories: [..], "
                       "series: [{name, values: [numbers]}]}"),
    "big_number": ("Big-number highlight", "big_number: {stat, label, context} — at most once per deck"),
    "two_by_two": ("2x2 matrix", "x_label, y_label, quadrants: [{pos: tl|tr|bl|br, label, body}]"),
    "harvey_balls": ("Harvey-ball assessment", "columns: [criteria], rows: [{label, scores: [0-4 per criterion]}]"),
    "waterfall": ("Waterfall / bridge", "unit (\"$M\"), bars: [{label, kind: start|delta|total, delta: number}] "
                                        "— start bar, signed deltas, total bar computed"),
    "gantt": ("Gantt roadmap", "periods: [\"Weeks 1–3\", ..], tasks: [{label, lane (owner), start 0-1, end 0-1, "
                              "milestone: true for a diamond}]"),
    "benchmark_bars": ("Benchmark bars", "unit, value_label, benchmark_label, series: [{label, value, benchmark}]"),
    "heat_map": ("Heat map", "rows: [..], cols: [..], cells: [[low|med|high per col], ..]"),
    "value_chain": ("Value chain", "stages: [{label, sub}] — 4 to 6 chevrons"),
    "maturity_curve": ("Maturity journey", "stages: [names], current_index, target_index, current_label, target_label"),
    "stack_layers": ("Layered stack", "stack_layers: [{label, description}] — 3 to 6 layers"),
    "roadmap_matrix": ("Roadmap matrix", "roadmap_matrix: {periods: [..], tracks: [{label, cells: [{label, status}]}]}"),
    "bullets": ("Bullet points", "bullets: [3 to 5 points, ≤20 words each] — use sparingly"),
}

# Visuals that carry an analysis on their own; a strong deck uses several.
RICH_VISUALS = (
    "two_by_two", "harvey_balls", "waterfall", "gantt", "benchmark_bars", "heat_map", "value_chain",
    "maturity_curve", "process_flow", "chart", "roadmap_matrix",
)

ICON_HINT = (
    "Icons: stat_cards, column_cards and process_flow items take an optional `icon`, one of: "
    "users, target, shield_check, bar_chart, line_chart, pie_chart, dollar, coins, savings, clock, timer, "
    "calendar, gauge, settings, database, cloud, ai, bot, workflow, network, layers, refresh, lightbulb, "
    "handshake, globe, building, bank, factory, truck, document, check, checklist, alert, trend_up, trend_down, "
    "lock, zap, rocket, flag, search, route, milestone, scale, award, presentation, pill, health, stethoscope, "
    "lab, microscope, briefcase."
)

BIG4_RULES = """\
CONSULTING SLIDE STANDARD (Deloitte / McKinsey / BCG level):
1. ACTION TITLES. Every content slide title is a full-sentence conclusion the audience should
   accept (subject + verb + so-what, ideally with a number), ≤ 15 words. Never a topic label
   such as "Current State" or "Proof Points". Read in sequence, the titles tell the whole story.
2. ONE MESSAGE, PROVEN BY THE VISUAL. The body proves the title: data, a framework or a plan,
   never a restatement of the title. No slide carries a single sentence as its only content.
3. VISUALS OVER TEXT. Pick the visual that shows the logic: comparison → harvey_balls or table;
   prioritisation → two_by_two; size of prize / business case → waterfall; plan → gantt or
   process_flow; current vs. peers → benchmark_bars; where the pain sits → heat_map; journey →
   maturity_curve; 3 headline facts → stat_cards. Use `bullets` for at most one slide in the deck;
   a deck of 8+ slides uses at least four different rich visuals.
4. NUMBERS ARE SOURCED. Quantify wherever evidence allows and put the source in `footer_note`
   ("Source: …"). Never invent precise figures: when no source supports a number, give a range
   or a directional statement and mark it "(estimate)" or "(illustrative)".
5. SUBTITLE AS SECTION LABEL. `subtitle` is a 2–5 word section label shown above the title
   (e.g. "Executive summary", "Business case"). `takeaway` (one sentence) states the so-what under
   a figure.
6. CLIENT-SPECIFIC. Name the client's functions, systems, regulators and numbers; avoid generic
   consulting filler and internal delivery roles (no "Proposal Lead reviews…").
"""


def visual_contract() -> str:
    """The slide types with the fields each needs, for a model prompt."""
    lines = ["SLIDE TYPES AND REQUIRED FIELDS (put these fields at the top level of the slide object):"]
    lines += [f"- {name} ({label}): {fields}" for name, (label, fields) in VISUALS.items()]
    lines.append(ICON_HINT)
    return "\n".join(lines)


def outline_type_choices() -> str:
    """Comma-separated slide types an outline may use."""
    return ", ".join(["title", "section_divider", *VISUALS])


def type_labels() -> dict[str, str]:
    """slide_type -> label for showing an outline to a user."""
    return {"title": "Title slide", "section_divider": "Section divider", **{k: v[0] for k, v in VISUALS.items()}}
