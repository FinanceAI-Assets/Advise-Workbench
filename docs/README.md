# Documentation index

All project documents live here, grouped by stage. Start with [SETUP.md](SETUP.md) to install and run the app,
then [07-user-guide/using-the-app.md](07-user-guide/using-the-app.md). For where the codebase is heading, see
[02-architecture/target-structure.md](02-architecture/target-structure.md).

## 00-overview

What the product is and why: briefs, competitive analysis, solution overview.

| Document | Title |
|---|---|
| [ANALYSIS_SUMMARY.txt](00-overview/ANALYSIS_SUMMARY.txt) |  |
| [COMPETITIVE_ANALYSIS.md](00-overview/COMPETITIVE_ANALYSIS.md) | Advise Workbench Competitive Analysis |
| [COMPETITIVE_DASHBOARD.html](00-overview/COMPETITIVE_DASHBOARD.html) |  |
| [EXECUTIVE_BRIEF.md](00-overview/EXECUTIVE_BRIEF.md) | Advise Workbench: Executive Brief |
| [VIVEKA Solution Introduction and Overview.pdf](00-overview/VIVEKA%20Solution%20Introduction%20and%20Overview.pdf) |  |

## 01-requirements

What it must do: requirements documents and gap analyses.

| Document | Title |
|---|---|
| [AGENT_SWARM_GUIDE_GAP_ANALYSIS.md](01-requirements/AGENT_SWARM_GUIDE_GAP_ANALYSIS.md) | Guide vs Advise Workbench codebase — architectural differences |
| [BUG_PPTX_CAPABILITY_CONTRADICTION.md](01-requirements/BUG_PPTX_CAPABILITY_CONTRADICTION.md) | Bug Analysis: PPTX Agent Capability Contradiction |
| [frontend-brd.md](01-requirements/frontend-brd.md) | Advise Workbench — Frontend Design Specification |

## 02-architecture

How it is put together: architecture, target structure, decision records.

| Document | Title |
|---|---|
| [ARCHITECTURE.md](02-architecture/ARCHITECTURE.md) | Advise Workbench — architecture |
| [adr/ADR_PPTX_CANVAS_RENDERER_SPIKE.md](02-architecture/adr/ADR_PPTX_CANVAS_RENDERER_SPIKE.md) | ADR: PPTX Canvas Renderer Strategy Spike |
| [module-map.md](02-architecture/module-map.md) | Module map |
| [target-structure.md](02-architecture/target-structure.md) | Advise-Workbench: target structure and modularisation plan |

## 03-design

Designs of individual modules.

| Document | Title |
|---|---|
| [DATABASE_TRANSACTIONS.md](03-design/DATABASE_TRANSACTIONS.md) | Database Transaction Checkpoints |
| [PHASE0_COORDINATOR_REFACTOR.md](03-design/PHASE0_COORDINATOR_REFACTOR.md) | Phase 0: Coordinator Refactor to Agentic Loop |
| [PPTX_ARTIFACT_RENDERER_IMPLEMENTATION.md](03-design/PPTX_ARTIFACT_RENDERER_IMPLEMENTATION.md) | Executive-Ready PPTX Generation Implementation |
| [TOKEN_BUDGET_IMPLEMENTATION.md](03-design/TOKEN_BUDGET_IMPLEMENTATION.md) | Token Budget & Context Compression - Implementation Guide |
| [conversation-graph.md](03-design/conversation-graph.md) | Sheldon's conversation: turn phases, graph driver and background replies |
| [financial-modules-build-plan.md](03-design/financial-modules-build-plan.md) | Financial Analysis Modules — Build Plan |
| [guided-journey-view.md](03-design/guided-journey-view.md) | Guided view: the six-step project journey |
| [langgraph-run-graph.md](03-design/langgraph-run-graph.md) | Run execution with LangGraph |
| [leading-practice-rag.md](03-design/leading-practice-rag.md) | Leading Practice library: retrieval pipeline |
| [memory-context-prompts.md](03-design/memory-context-prompts.md) | Memory, context and prompts |

## 04-development

Working on the code: integration guides and conventions.

| Document | Title |
|---|---|
| [anthropic_skills_reconciliation.md](04-development/anthropic_skills_reconciliation.md) | Anthropic skills reconciliation (mapped built-ins) |
| [frontend-integration-guide.md](04-development/frontend-integration-guide.md) | Advise Workbench — Component Integration Guide |
| [layering.md](04-development/layering.md) | Layering rules |
| [model-providers.md](04-development/model-providers.md) | Model providers |

## 05-testing

Test reports, quality evaluations, sample outputs and parity reports.

| Document | Title |
|---|---|
| [CODE_QUALITY_EVAL.md](05-testing/CODE_QUALITY_EVAL.md) | Code Quality Eval — Advise Workbench |
| [TEST_REPORT.md](05-testing/TEST_REPORT.md) | PPTX Artifact Renderer - Comprehensive Test Report |
| [TestEngagement2_Analysismodel_20260410.xlsx](05-testing/TestEngagement2_Analysismodel_20260410.xlsx) |  |
| [TestEngagement2_Executivereport_20260528.pdf](05-testing/TestEngagement2_Executivereport_20260528.pdf) |  |
| [reports/](05-testing/reports/) | PPTX canvas parity reports and visual-diff images |

## 06-deployment-operations

Running it: operations, topology, security, hardening.

| Document | Title |
|---|---|
| [CONCURRENCY_500_EXECUTION_PLAN.md](06-deployment-operations/CONCURRENCY_500_EXECUTION_PLAN.md) | 500+ Concurrent Users Execution Plan |
| [OPERATIONS.md](06-deployment-operations/OPERATIONS.md) | Operations Baseline |
| [PRODUCTION_HARDENING_PLAN_2026-04-21.md](06-deployment-operations/PRODUCTION_HARDENING_PLAN_2026-04-21.md) | Production Hardening Plan (2026-04-21) |
| [PRODUCTION_TOPOLOGY.md](06-deployment-operations/PRODUCTION_TOPOLOGY.md) | Production topology (500-user scale) |
| [SECURITY.md](06-deployment-operations/SECURITY.md) | Security operations checklist |
| [V4_HARDENING_EXECUTION_CHECKLIST.md](06-deployment-operations/V4_HARDENING_EXECUTION_CHECKLIST.md) | v4 Hardening Execution Checklist |
| [bash_tool_security.md](06-deployment-operations/bash_tool_security.md) | Bash tool (Anthropic-aligned) — security and operations |
| [observability.md](06-deployment-operations/observability.md) | Monitoring with OpenObserve |
| [scale-out.md](06-deployment-operations/scale-out.md) | Running on more than one process |
| [text_editor_tool_security.md](06-deployment-operations/text_editor_tool_security.md) | Text Editor tool security and operations |

## 07-user-guide

Using the application.

| Document | Title |
|---|---|
| [using-the-app.md](07-user-guide/using-the-app.md) | Using the app |

## 08-project-management

Plans, tickets and phase summaries.

| Document | Title |
|---|---|
| [PHASE0_COMPLETION_SUMMARY.md](08-project-management/PHASE0_COMPLETION_SUMMARY.md) | Phase 0 Completion Summary |
| [PHASE0_PROGRESS.md](08-project-management/PHASE0_PROGRESS.md) | Phase 0 Implementation Progress |
| [STEP2_PRIORITY1_IMPLEMENTATION_TICKETS.md](08-project-management/STEP2_PRIORITY1_IMPLEMENTATION_TICKETS.md) | Step 2 Priority 1 - QA / Guardrails / DPDP Hardening Tickets |

## 99-archive

Historical documents, kept unchanged for reference.

48 files. See the folder: [99-archive/](99-archive/).

## Elsewhere in the repo

- Skill documents stay with their skills: `backend/config/skills/*/SKILL.md`.
- Sample source documents and run scenarios: `data/examples/northwind-p2p/`.
- Load-test scripts: `scripts/load/README.md`.
