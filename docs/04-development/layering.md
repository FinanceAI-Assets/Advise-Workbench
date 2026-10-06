# Layering rules

Which part of the backend may import which. The rule is checked by `lint-imports` (in `make lint` and in CI) from the `.importlinter` file at the repo root.

## The layers

A layer may import the layers below it, never the ones above.

| Layer (top to bottom) | Folders |
|---|---|
| Application and optional features | `src/app`, `src/extensions` |
| Run lifecycle | `src/workflows` |
| Agents | `src/agents` |
| Checks and controls | `src/evaluation`, `src/guardrails` |
| Tools | `src/tools` |
| Building blocks | `src/memory`, `src/deliverables`, `src/prompts` |
| Model access | `src/llm` |
| Foundations | `src/core` |

Folders on the same row may import each other.

## Existing exceptions

The code did not follow these layers when the rule was added. The 27 imports that break it are listed under `ignore_imports` in `.importlinter`, so the check passes today and fails on any new violation.

| From | To | Count | What would remove them |
|---|---|---|---|
| `deliverables` | `evaluation` | 8 | File builders call QA modules directly; move the QA calls to the caller |
| `agents` | `extensions` | 6 | Core agents import swarm code; load optional features through a registry |
| `agents` | `workflows` | 3 | Agents emit run events and todo snapshots; pass an event callback in |
| `workflows` | `app` | 2 | The orchestrator imports request schemas; move those schemas down |
| `tools` | `extensions` | 2 | The tool registry registers swarm tools; let the extension register itself |
| others | | 6 | One each: see `.importlinter` |

When you remove one of these imports, delete its line from `.importlinter` so it cannot come back.

## Running it

```bash
make lint          # ruff gate and lint-imports
lint-imports       # the layering check alone
```
