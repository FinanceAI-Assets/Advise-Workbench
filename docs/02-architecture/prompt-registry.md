# Prompt Registry

All prompts in the Advise Workbench are externalized to YAML files in `config/prompts/` and loaded via `src/prompts/registry.py:get_prompt(name)`. This document indexes them by category and usage location.

## Terminology

- **System Prompt**: Sets the role and task constraints (loaded once per request).
- **User Prompt**: The actual instruction/data passed to the LLM (often templated with runtime variables).
- **Template Variable**: Placeholders like `${variable_name}` substituted at runtime via `Prompt.render_user(**vars)`.

---

## 1. Process Extraction Prompts

| Prompt Name | Type | Purpose | Used In | Template Variables |
|---|---|---|---|---|
| `extraction_process_user` | user | Core extraction schema and rules for turning text into structured process models | `src/agents/specialists/extraction_agent.py` | None (base prompt) |
| `extraction_advisory_pov_rules` | user | Advisory POV-specific extraction rules (not modeling the doc-writing process) | `src/agents/specialists/extraction_agent.py` (when archetype=`advisory_pov`) | None |

**Example Usage:**
```python
from src.prompts.registry import get_prompt

prompt = get_prompt("extraction_process_user")
user_text = prompt.render_user()

# For advisory_pov, append additional rules:
if archetype == "advisory_pov":
    rules = get_prompt("extraction_advisory_pov_rules")
    user_text += "\n\n" + rules.render_user()
```

---

## 2. DOCX Agent Prompts (Document Generation)

All DOCX deliverables use a fallback system prompt (`agent_docx_fallback.yaml`, already externalized) and a user prompt specific to document type.

| Prompt Name | Deliverable Type | Template Variables | Notes |
|---|---|---|---|
| `docx_sop_user` | SOP (Standard Operating Procedure) | `${process_model}` | 7-section structure: Purpose, Scope, Roles, Procedure, Decision Points, References |
| `docx_narrative_user` | Narrative (Executive Briefing) | `${process_model}`, `${context}` | 5-section structure focusing on business outcome & actions |
| `docx_raci_user` | RACI Matrix | `${process_model}` | RACI table with assignment rules |
| `docx_brd_user` | BRD (Business Requirements Document) | `${process_model}`, `${context}` | 7-section structure: Executive Summary → References |
| `docx_proposal_user` | Proposal | `${sections}`, `${constraints}`, `${discovery}`, `${process_model}`, `${context}` | Uses skill-based contract + discovery data |
| `docx_generic_user` | Generic Procedure | `${process_model}` | 7-section procedure document fallback |

**File:** `src/agents/specialists/docx_agent.py:run_docx_agent()`

---

## 3. PDF Agent Prompts (Report Generation)

Mirrors DOCX structure but with PDF-specific formatting constraints.

| Prompt Name | Deliverable Type | Template Variables |
|---|---|---|
| `pdf_narrative_user` | Narrative | `${process_model}`, `${context}` |
| `pdf_sop_user` | SOP | `${process_model}` |
| `pdf_proposal_user` | Proposal | `${sections}`, `${constraints}`, `${process_model}`, `${context}` |
| `pdf_generic_user` | Generic Report | `${process_model}`, `${context}` |

**File:** `src/agents/specialists/pdf_agent.py:run_pdf_agent()`

---

## 4. XLSX Agent Prompts (Spreadsheet Generation)

| Prompt Name | Type | Purpose | Template Variables |
|---|---|---|---|
| `xlsx_raci_user` | RACI Matrix | Generates RACI table for Excel/Sheets | `${accountable}`, `${process_model}` |
| `xlsx_generic_user` | Process Data Table | Activity × Owner × Inputs/Outputs/Tools/Duration/Notes | `${process_model}` |

**File:** `src/agents/specialists/xlsx_agent.py:run_xlsx_agent()`

---

## 5. Legacy / Specialist Agent Prompts

| Prompt Name | Agent | Type | Status | Template Variables |
|---|---|---|---|---|
| `sop_user` | SOP Agent | user | Legacy (retained for direct invocation in tests) | `${process_model}` |
| `raci_user` | RACI Agent | user | Legacy | `${format}` (markdown or html), `${process_model}` |

**Note:** New routing uses `run_docx_agent(deliverable="sop")` and `run_xlsx_agent(deliverable="raci")`. Legacy agents kept for backward compatibility.

**Files:** `src/agents/specialists/sop_agent.py`, `src/agents/specialists/raci_agent.py`

---

## 6. Conversation & Planning Prompts

### Storyline Builder

| Prompt Name | Component | Template Variables | Usage |
|---|---|---|---|
| `storyline_arc_recommender` | System | N/A (defines role & constraints) | Recommends narrative arc (SCQA, pyramid, etc.) |
| `storyline_arc_recommender_user` | User | `${client_name}`, `${client_industry_suffix}`, `${primary_outcome}`, `${win_themes}`, `${audience}`, `${arc_descriptions}`, `${project_context}`, `${conversation_history}` | Arc recommendation inference |
| `storyline_spine_builder` | System | `${arc_name}`, `${arc_structure}`, `${visual_vocab}`, `${numeric_visuals}` | Builds slide structure for selected arc |
| `storyline_spine_builder_user` | User | `${client_name}`, `${client_industry_suffix}`, `${primary_outcome}`, `${audience}`, `${win_themes}`, `${target_slides}`, `${process_summary}`, `${enrichment}` | Slide-by-slide spine generation |

**File:** `src/agents/conversation/storyline_builder.py`

---

## 7. Quality & Evaluation Prompts (Already Externalized)

These are already in YAML (see `config/prompts/` for full list):

- `qa_review.yaml` — Quality assurance evaluation
- `guardrail_gate.yaml` — Policy compliance check
- `rubric_critique.yaml` — Structured evaluation against rubric
- `editorial_reviewer.yaml` — Content & tone review
- `narrative_coherence_reviewer.yaml` — Arc & continuity review
- `visual_qa_reviewer.yaml` — Visual quality check
- `pptx_title_critic.yaml` — Slide title evaluation

---

## 8. Knowledge & RAG Prompts (Already Externalized)

- `lp_rag_answer.yaml` — Leading Practice retrieval & synthesis
- `wiki_qa_reviewer.yaml` — Wiki QA evaluation
- `wiki_relationship_analyzer.yaml` — Relationship extraction from wiki

---

## File Organization

```
config/prompts/
├── extraction_process_user.yaml
├── extraction_advisory_pov_rules.yaml
├── docx_*.yaml                         # 6 deliverable types
├── pdf_*.yaml                          # 4 deliverable types
├── xlsx_*.yaml                         # 2 table types
├── sop_user.yaml / raci_user.yaml      # Legacy
├── storyline_arc_recommender.yaml      # System
├── storyline_arc_recommender_user.yaml # User (dynamic)
├── storyline_spine_builder.yaml        # System
├── storyline_spine_builder_user.yaml   # User (dynamic)
├── [quality & evaluation prompts]      # 7 files
├── [knowledge & RAG prompts]           # 3 files
├── [other specialized prompts]         # Shell, swarm, etc.
└── tool_usage_policy.yaml
```

**Total:** 45+ YAML prompt files, all indexed below.

---

## Prompt Loading & Caching

**File:** `src/prompts/registry.py`

```python
def get_prompt(name: str) -> Prompt:
    """Load YAML from config/prompts/{name}.yaml using LRU cache (max 256 entries)."""
    ...

# Usage:
prompt = get_prompt("docx_sop_user")
rendered = prompt.render_user(process_model="...", context="...")
```

**Caching:** LRU cache with maxsize=256. Loaded prompts are cached for the lifetime of the request.

---

## Template Variable Conventions

- `${variable_name}` — Placeholder for runtime substitution via `string.Template`.
- Runtime values **must** be escaped for untrusted input (e.g., user-provided text).
- Template variables are documented in the YAML `description` field.

**Example:**
```yaml
name: docx_sop_user
description: User prompt for SOP with process model and optional context
user: |
  ...
  ${process_model}  # Template variable; caller provides via render_user(process_model="...")
```

---

## Verification & Testing

Equivalence tests verify that newly externalized prompts match original hardcoded versions:

**File:** `tests/unit/prompts/test_batch7_user_equivalence.py`

Tests verify:
1. YAML prompt contains expected schema structures (SOP has "## Purpose", etc.)
2. Template variables are correctly named
3. Prompts load without errors

**Run tests:**
```bash
pytest tests/unit/prompts/test_batch7_user_equivalence.py -v
```

---

## Migration Status: System vs. User Prompts

| Category | System Prompts | User Prompts | Notes |
|---|---|---|---|
| Extraction | ✅ Externalized | ✅ Externalized (NEW) | Core schemas in YAML |
| DOCX | ✅ Externalized | ✅ Externalized (NEW) | 6 deliverable types |
| PDF | ✅ Externalized | ✅ Externalized (NEW) | 4 deliverable types |
| XLSX | ✅ Externalized | ✅ Externalized (NEW) | RACI + generic |
| SOP (Legacy) | ✅ Externalized | ✅ Externalized (NEW) | Retained for backward compat |
| RACI (Legacy) | ✅ Externalized | ✅ Externalized (NEW) | Retained for backward compat |
| Storyline Arc | ✅ Externalized | ✅ Externalized (NEW) | Both system & user |
| Storyline Spine | ✅ Externalized | ✅ Externalized (NEW) | Both system & user |
| Quality Evaluation | ✅ Externalized | N/A | All system prompts |
| Knowledge/RAG | ✅ Externalized | N/A | All system prompts |

**Completeness:** All hardcoded user prompts (identified in Phase 1 exploration) have been externalized and verified.

---

## Future Enhancements

1. **Prompt Versioning:** Track prompt version changes in git/version control for A/B testing.
2. **Prompt Analytics:** Log which prompts are used and their performance metrics.
3. **Dynamic Loading:** Support loading prompts from a database or remote service.
4. **Prompt Composition:** Build complex prompts by composing smaller, reusable units.
