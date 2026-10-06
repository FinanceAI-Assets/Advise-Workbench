# Memory, context and prompts

Where each of the three is managed after the 2026-10-06 change, and what is still inline.

## Memory

| Kind | What it holds | Where it lives | Managed by |
|---|---|---|---|
| Run state (short-term) | The working variables of a run attempt | LangGraph checkpoints (`src/workflows/checkpoint.py`: SQLite file or PostgreSQL), deleted when the attempt ends | The run graph: a checkpoint after every phase |
| Conversation digest (short-term) | The conversation so far, compacted to a character budget | Built per run from the conversation messages | The run graph's `context` node (`_phase_context`) |
| Conversation state | State name, slots, pending questions | The conversation row | The conversation graph's phases |
| Long-term memory | Artifact summaries, the project memory profile, memory items with consent, the user's learning count | Application tables (`MemoryEvent`, `ProjectMemoryProfile`, `MemoryItem`, `UserProjectPreference`) | Written by the run graph's `remember` node (`_phase_remember`); read by the coordinator's context assembly |

Long-term memory stays in the application's own tables, not in a LangGraph Store. Those tables carry the consent rules (`memory_consent.py`), the retention policy and the `/api/memory` endpoints the UI uses; a LangGraph Store would need all three rebuilt on top of it.

## Context

| Step | Where | What it does |
|---|---|---|
| Run context | `context` node | Run settings, the plan, the conversation digest; the result (`init_state`) is checkpointed, so a restart during generation does not assemble it again |
| Retrieval for the coordinator | `TieredContextEngine.assemble_v2` (`src/memory/retrieval.py`), called inside the coordinator | Project documents, project wiki and memory items, ranked and fitted to a character budget |
| Leading practices | The retrieval graph in `leading-practice-rag.md` | Passages from the library |
| Compaction | `src/memory/short_term/context_compaction.py`, `src/llm/token_budgets.py` | Tiered trimming when a budget is exceeded |

The `context` phase is traced as `run.phase.context`.

## Prompts

`src/prompts/registry.py`, files in `config/prompts/<name>.yaml`:

```yaml
name: guardrail_gate
version: 1
description: Judge one guardrail (pass or fail) for a run's deliverables (src/guardrails/gates.py).
system: |-
  You are a strict compliance guardrail evaluator. Return strict JSON only.
user: |-
  Evaluate ONLY guardrail ${gate_key} for the following consulting deliverables. ...
  ${outputs}
```

```python
prompt = get_prompt("guardrail_gate")
claude_generate_json(system=prompt.render_system(), user=prompt.render_user(gate_key=key, outputs=outputs))
```

- Variables are written `${name}`. Rendering raises an error when one is missing.
- Raise `version` when the wording changes. The name and version of a rendered prompt are put on the current trace span (`prompt.name`, `prompt.version`), so a change in output quality can be matched to a prompt change in OpenObserve.
- A literal dollar sign in a prompt file is written `$$`.

### In the registry

| Prompt | Used by |
|---|---|
| `lp_rag_answer` | Leading Practice answer (`src/memory/knowledge/lp_rag.py`) |
| `qa_review` | Run QA review (`src/evaluation/qa.py`) |
| `guardrail_gate` | Guardrail gates (`src/guardrails/gates.py`) |
| `rubric_critique` | Rubric critique evaluator (`src/evaluation/evaluators.py`) |

The three moved prompts render the same text as the inline versions they replaced (checked character for character).

### Still inline

About 60 model call sites in about 35 files still build their prompts in code. The largest groups:

| Area | Files |
|---|---|
| Sheldon's conversation | `src/app/api/projects/conversation.py`, `_discovery.py`, `src/workflows/task_router/conversation_router.py`, `src/agents/conversation/` |
| Document agents | `src/agents/specialists/` (their system prompts are assembled from the skill files in `config/skills/`) |
| Visual and deliverable QA | `src/evaluation/visual_qa.py`, `deliverable_quality.py`, `quality_framework.py` |
| Wiki | `src/memory/knowledge/wiki_*.py` |
| Planner, extraction, repair | `src/agents/planner_agent.py`, `process_extraction.py`, `src/agents/repair/` |

Move them one at a time: create the YAML file, replace the inline text with `get_prompt(...)`, and compare the rendered text with the old one before removing it.

## Not done

- Long-term memory recall is not yet its own graph node (it happens inside the coordinator).
- No LangGraph Store.
- Most prompts are still inline (list above).
