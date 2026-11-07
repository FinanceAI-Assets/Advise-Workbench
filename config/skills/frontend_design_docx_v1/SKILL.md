---
id: frontend_design_docx_v1
domain: Design System
display_name: Frontend Design (DOCX) Specialist
output_types:
- docx
version: 1.0.0
description: Applies distinctive, production-grade frontend-inspired aesthetics (typography,
  hierarchy, spacing) to DOCX-ready markdown content.
use_when: the user wants a docx artifact that feels visually intentional and well-structured
  (frontend-inspired design language), not generic layouts
tools:
- retrieve_context
- qa_validator
workflow_steps:
- Pick a bold aesthetic direction and define the typographic hierarchy
- Outline the DOCX sections with concise, readable headings
- Draft markdown content with spacing and bullet structure
- Self-check for generic filler and formatting that converts cleanly to DOCX
feedback_loop:
- Review structure and hierarchy
- Tighten wording and spacing
- Remove generic phrasing
- Finalize for DOCX conversion
freedom_level: medium
quality_thresholds:
  docx: 0.88
acceptance_checks:
- Clear typographic/section hierarchy using markdown headings
- Concise bullet/paragraph structure with readable whitespace
- No HTML/CSS/React code or fenced code blocks
- No generic AI aesthetic patterns; choices feel intentional
default_representation: docx
companion_files: []
source_url: https://github.com/anthropics/skills/tree/main/skills/frontend-design
sample_instruction: Create a DOCX executive memo with a distinctive, refined visual
  hierarchy (headings + bullets + spacing) using a cohesive aesthetic direction, while
  keeping output as plain markdown.
custom: false
---

# DOCX Consulting Standard (markdown output)

Output is plain markdown that the platform converts to a branded Word document (Deloitte palette, Calibri).
No HTML, CSS, code fences or commentary. Do not choose fonts, colours or effects: the theme owns them.

## Structure (answer first)
1. `# Title` — specific, names the subject and the decision (not "Report").
2. **Executive summary** — 5 lines max: situation, finding, recommendation, ask. Numbers included.
3. Numbered sections `## 1. Heading`. Headings are statements of the finding where possible.
4. **Recommendations and next steps** — table: Action | Owner | By when.
5. **Appendix** — assumptions, sources, glossary.

## Writing rules
- One idea per paragraph. Paragraphs ≤4 sentences. Lead with the conclusion, then the evidence.
- Bullets for parallel items only; ≤7 per list; ≤20 words each. Prefer a table when comparing.
- Tables: header row, ≤7 columns, ≤8 words per cell, units in the header.
- Callouts: start a line with `> **Key insight:**` or `> **Risk:**`. Max 2 per page.
- Every number carries a source or "estimated": `(Source: Baseline metrics memo, FY25)`.
- Numbered steps for procedures; each step starts with a verb and names the owner.
- Define each acronym once. Consistent terms, no synonyms for the same thing.

## Forbidden
"TBD", "TODO", "N/A", "Lorem", "[...]", empty sections, internal headings (ObjectiveNow, WhatChanged).
If data is missing, state the gap in one sentence under Assumptions and proceed.

## Checklist
Summary stands alone? Every section answers a question the reader has? Numbers sourced? Owners and dates on actions?
