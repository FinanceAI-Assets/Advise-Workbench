# Phase 2 Implementation Guide: Externalize Remaining 22 Hardcoded Prompts

**Status**: 18 YAML files created + extraction_agent.py updated  
**Remaining**: 11 Python files to update  
**Effort**: ~30 minutes for manual updates OR run provided script

---

## Completed

✅ **Phase 2A-2D YAML Files Created** (18 files):
- `pptx_slide_schema.yaml`
- `pptx_narrative_arcs.yaml`
- `pptx_consistency_rules.yaml`
- `planner_execution_system.yaml`
- `visual_qa_slide_design.yaml`
- `extraction_system.yaml`
- `extraction_correction_retry.yaml`
- `narrative_agent_user.yaml`
- `slide_negotiator_system.yaml`
- `strategy_planner_system.yaml`
- `pptx_slide_repair.yaml`
- `pptx_slide_title_review.yaml`
- `docx_section_repair.yaml`
- `deck_outline_preview.yaml`
- `document_outline_strategy.yaml`
- `swarm_preambles.yaml`
- `agent_bash_system.yaml`
- `process_map_drawio.yaml`

✅ **extraction_agent.py**: Updated to use `extraction_system.yaml`

---

## Remaining Python Files to Update

### 1. **narrative_agent.py** (lines 36-56)

**Current**:
```python
user = (
    "Write an executive briefing note from the ProcessModel and context excerpt below.\n\n"
    ...
)
```

**Replace with**:
```python
prompt = get_prompt("narrative_agent_user")
user = prompt.render_user(
    process_model=process_model_json_block(pm),
    context=context_excerpt_block(_grounded_context_excerpt(ctx, 4000), 4000)
)
```

---

### 2. **pptx_agent.py** (3 locations)

**Location A** (lines 588-602 - system prompt additions):
Replace the system prompt concatenation with:
```python
consistency_prompt = get_prompt("pptx_consistency_rules")
system = sb.system + "\n\n" + consistency_prompt.render_user() + "\n\n" + _visual_guide_block()
```

**Location B** (lines 721-789 - slide schema):
Replace `_slide_schema = (...)` with:
```python
schema_prompt = get_prompt("pptx_slide_schema")
_slide_schema = schema_prompt.render_user(
    editorial_slide_types=" | split_panel | lanes | workstream_cards | tower_cards | roadmap_matrix | swimlane_timeline | flagship_cards" if _editorial_theme else "",
    editorial_fields="""split_panel   items: [{label: string, body: string}] — 2–5 numbered items; ...""" if _editorial_theme else "",
    editorial_rules="""- emphasis: use to highlight 1–3 key words in the title — must be a verbatim substring. ...""" if _editorial_theme else ""
)
```

**Location C** (lines 795-909 - narrative arcs & slide mandates):
Replace the entire `proposal_mandate` dict building with:
```python
arcs_prompt = get_prompt("pptx_narrative_arcs")
arc_instructions = {
    "scqa": arcs_prompt.render_user(arc_type_instructions="SCQA Arc Instructions..."),
    "pyramid": arcs_prompt.render_user(arc_type_instructions="Pyramid Arc Instructions..."),
    "case_led": arcs_prompt.render_user(arc_type_instructions="Case-Led Arc Instructions..."),
}
```

**Full Rewrite**: Consider extracting the `proposal_mandate` logic into a separate YAML or using a template-driven approach.

---

### 3. **policy.py** (2 locations)

**Location A** (lines 252-265 - deck outline):
Replace system prompt with:
```python
deck_prompt = get_prompt("deck_outline_preview")
system = deck_prompt.render_system(
    outline_types=", ".join(_outline_types()),
    target_slides=target_slides
)
```

**Location B** (lines 348-362 - document outline):
Replace system prompt with:
```python
doc_prompt = get_prompt("document_outline_strategy")
system = doc_prompt.render_system(target_pages=target_pages)
```

---

### 4. **visual_qa.py** (lines 214-236)

**Replace**:
```python
pixel_system = ("You are a slide design QA reviewer...")
pixel_user = (f"Project: {project_id}...")
```

**With**:
```python
vqa_prompt = get_prompt("visual_qa_slide_design")
pixel_system = vqa_prompt.render_system()
pixel_user = vqa_prompt.render_user(
    project_id=project_id,
    run_id=run_id
)
```

---

### 5. **slide_negotiator.py** (lines 122-130)

**Replace system prompt** with:
```python
neg_prompt = get_prompt("slide_negotiator_system")
system = neg_prompt.render_system(
    slide_types=", ".join(SLIDE_TYPE_LABELS.keys())
)
```

---

### 6. **strategy_plan.py** (lines 51-68)

**Replace system prompt** with:
```python
planner_prompt = get_prompt("strategy_planner_system")
system = planner_prompt.render_system()
```

---

### 7. **pptx_critique_repair.py** (2 locations)

**Location A** (lines 20-26 & 28-32):
Replace:
```python
_SLIDE_REPAIR_SYSTEM = ("You repair...")
_EVIDENCE_SOFT_BLOCK_DIRECTIVE = ("EVIDENCE FIX...")
```

**With**:
```python
from src.prompts.registry import get_prompt as get_repair_prompt

def _get_slide_repair_prompts():
    repair_prompt = get_repair_prompt("pptx_slide_repair")
    return {
        "system": repair_prompt.render_system(),
        "evidence_directive": repair_prompt.render_user()
    }
```

**Location B** (lines 192-196 - slide title review):
Replace user prompt with:
```python
title_prompt = get_prompt("pptx_slide_title_review")
user = title_prompt.render_user(
    titles_json=json.dumps(titles[:12], ensure_ascii=False)
)
```

---

### 8. **docx_critique_repair.py** (lines 23-29)

**Replace**:
```python
_SECTION_REPAIR_SYSTEM = ("You revise...")
```

**With**:
```python
section_prompt = get_prompt("docx_section_repair")
_SECTION_REPAIR_SYSTEM = section_prompt.render_system()
```

---

### 9. **swarm.py** (lines 34-45)

**Replace**:
```python
SWARM_WORKER_PREAMBLE = ("You are a WORKER...")
SWARM_LEAD_PREAMBLE = ("You are the LEAD...")
```

**With**:
```python
from src.prompts.registry import get_prompt

_swarm_prompts = get_prompt("swarm_preambles")
SWARM_WORKER_PREAMBLE = _swarm_prompts.render_system()  # Returns worker role text
SWARM_LEAD_PREAMBLE = _swarm_prompts.render_user()      # Returns lead role text
```

---

### 10. **agent_bash.py** (lines 69-74)

**Replace default system** with:
```python
from src.prompts.registry import get_prompt

bash_prompt = get_prompt("agent_bash_system")
default_system = bash_prompt.render_system()
```

---

### 11. **process_map_agent.py** (lines 74-80)

**Replace fallback_system** with:
```python
from src.prompts.registry import get_prompt

drawio_prompt = get_prompt("process_map_drawio")
fallback_system = drawio_prompt.render_system()
```

---

### 12. **planner_agent.py** (lines 389-417)

**Replace system prompt** with:
```python
from src.prompts.registry import get_prompt

plan_prompt = get_prompt("planner_execution_system")
system = plan_prompt.render_system() + UNTRUSTED_JSON_USER_NOTE
```

---

## Verification Steps

After all updates:

1. **Syntax Check**:
   ```bash
   python -c "from src.agents.specialists import *; from src.agents.conversation import *; print('✓ All imports OK')"
   ```

2. **Run Prompt Tests**:
   ```bash
   pytest tests/unit/prompts/test_batch7_user_equivalence.py -v
   ```

3. **Integration Test** (optional):
   ```bash
   pytest tests/integration/ -k "extraction or narrative or pptx" -v
   ```

---

## Summary

| Phase | Files | YAML Files | Status |
|-------|-------|-----------|--------|
| 1 | 7 | 17 | ✅ Complete |
| 2A | 3 | 5 | ⏳ YAML only |
| 2B | 6 | 8 | ⏳ YAML only |
| 2C | 1 | 2 | ⏳ YAML only |
| 2D | 3 | 3 | ⏳ YAML only |
| **Total** | **20** | **35** | **⏳ 50% Done** |

---

## Next Steps

1. Update remaining 11 Python files (use guide above)
2. Create equivalence tests for new prompts
3. Run full test suite
4. Commit changes

**Estimated Time**: 30-45 minutes for manual updates, or use provided script for automation.
