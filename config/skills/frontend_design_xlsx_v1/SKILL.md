---
id: frontend_design_xlsx_v1
domain: Design System
display_name: Frontend Design (XLSX) Specialist
output_types:
- xlsx
version: 1.0.0
description: Applies frontend-inspired clarity and structure to XLSX-convertible markdown
  table content.
use_when: the user wants an XLSX artifact that is clean, readable, and structured
  like a well-designed frontend table (consistent labels, minimal clutter)
tools:
- retrieve_context
- qa_validator
workflow_steps:
- Select a consistent labeling scheme for table content
- Draft a clean markdown table with our fixed column structure
- Tighten wording for scannability and readability
- Validate the markdown-table-only output contract
feedback_loop:
- Check consistency
- Remove unnecessary words
- Validate output contract
- Finalize table rows
freedom_level: low
quality_thresholds:
  xlsx: 0.88
acceptance_checks:
- Output is ONLY a markdown table (header + divider + rows)
- Consistent cell labeling and minimal clutter
- No HTML/CSS/JS and no extra commentary
- Cells are concise and readable after XLSX conversion
default_representation: xlsx
companion_files: []
source_url: https://github.com/anthropics/skills/tree/main/skills/frontend-design
sample_instruction: Create an XLSX-ready markdown table with a clean, frontend-like
  information hierarchy; output must be ONLY the markdown table.
custom: false
---

# XLSX Consulting Standard (markdown table output)

Output is markdown tables that the platform converts to a styled workbook (Deloitte green header, white bold text, Calibri).
No HTML, CSS, JS or commentary. Do not specify colours or fonts: the theme owns them.

## Sheet design
- One table per sheet. First row is the header. Sheet title as `## Sheet name` (≤31 chars, no `/ \ ? * [ ]`).
- Order of sheets: Summary → detail tables → Assumptions → Sources.
- Summary sheet: 5–8 rows of headline metrics: Metric | Value | Unit | Source.
- Header labels are specific and include units: "Cycle time (days)", "Cost (USD k)".
- One fact per cell. No merged-cell thinking, no blank spacer rows, no notes inside data cells.

## Data rules
- Numbers as plain numerics (no currency symbols or thousands separators inside the cell; unit goes in the header).
- Dates ISO `YYYY-MM-DD`. Percentages as numbers with "%" in the header.
- Status columns use a fixed vocabulary: Not started / In progress / Done / Blocked.
- RACI tables: one R and one A per row; roles in columns; values R, A, C, I only.
- Totals and ratios are formulas when the platform supports them; otherwise add a "Calculation" note on the Assumptions sheet.
- Every metric traces to a Source column or the Sources sheet.

## Forbidden
"TBD", "N/A", "TODO", empty rows, duplicate headers, placeholder rows such as "No steps extracted".
If a value is unknown, drop the row and list the gap on the Assumptions sheet.

## Checklist
Each header has units? Each row has an owner or source? No blanks? Vocabulary consistent? Summary sheet first?
