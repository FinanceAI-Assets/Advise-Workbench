# Complete Skills Section: Data Capture, Storage, Retention & Memory

**Version:** 2.0 (Complete & Verified)  
**Date:** 2026-10-30  
**Status:** Comprehensive analysis with all data types, storage locations, and lifecycle details

---

## Executive Summary

The skills section captures data across **4 storage layers**, **8+ data types**, with **multiple retention policies** and **real-time event tracking**. This document details:

- **What data is captured** at each execution step
- **Where it's stored** (database, filesystem, cache, memory)
- **How long it's retained** (indefinite to 7-365 days)
- **How prompts are handled** at each stage
- **How LLM calls are tracked** with token/cost accounting
- **How processes are monitored** via event stream

---

## Part 1: All Data Types Captured in Skills Section

### 1.1 Skill Metadata (Definition & Registration)

**Type:** Configuration  
**Captured:** When skill is loaded/registered  
**Source:** SKILL.md files or skill_registry.json

```yaml
# Location: config/skills/{skill_name}/SKILL.md or workspace/{project_id}/custom_skills/{skill_name}/SKILL.md
---
id: "skill_sop_generator"                    # Unique identifier
domain: "content"                            # Domain: content|analysis|visualization|discovery
display_name: "SOP Generator"                # Human-readable name
version: "1.0"                               # Version for tracking
description: "Generates SOPs from process models"
output_types:                                # What this skill produces
  - "docx"
  - "pdf"
tools:                                       # Tools invoked by this skill
  - "wiki_qa"
  - "process_extraction"
  - "narrative_feedback"
prompt_instructions: |                       # SYSTEM PROMPT (inline in SKILL.md)
  You are an expert SOP writer...
  [1-5 KB of instructions]
sample_instruction: "Generate a 5-step SOP for..."  # User example
custom: false                                # true = user-defined, false = built-in
quality_thresholds:                          # Quality gates specific to this skill
  min_completeness_score: 0.85
  requires_evidence_gate: true
  requires_visual_qa: true
branding_override:                           # Optional: override branding
  primary_color: "#E8007C"
  deck_theme: "editorial"
companion_files:                             # Related templates/files
  - "./templates/sop_template.docx"
  - "./resources/best_practices.md"
_skill_md_path: "/path/to/SKILL.md"         # Internal: file location
```

**Storage Locations:**
- **Built-in Skills:** `config/skills/{skill_name}/SKILL.md` (git-tracked)
- **Custom Skills:** `workspace/{project_id}/custom_skills/{skill_name}/SKILL.md` (project-specific)
- **Legacy Format:** `config/skill_registry.json` (fallback, deprecated)

**Size:** 10-50 KB per skill  
**In-Memory Load:** 
- `load_builtin_skills()` → parsed YAML list
- `load_custom_skills_from_workspace()` → per-project parsed list
- `_merged_skill_registry(project_id)` → combined list (~10-20 KB)

**Retention:** Indefinite (versioned in git / workspace)

---

### 1.2 Run Initiation Data

**Type:** Run metadata  
**Captured:** When user submits run  
**Storage:** `Run` table (PostgreSQL/SQLite)

```json
{
    "id": "run_abc123def456",                # Unique run ID
    "project_id": "proj_xyz789",
    "status": "queued",                      # queued|running|review_ready|done|failed
    "instruction": "Generate SOP for onboarding process with all steps documented",
    "output_types": ["docx", "pdf"],         # Requested output formats
    "plan_payload": {                        # Full execution plan (JSON)
        "phase": "discovery",
        "selected_skills": [
            {
                "id": "skill_sop_generator",
                "version": "1.0",
                "context": "Process model: onboarding_flow"
            }
        ],
        "enrichment": {
            "wiki_links": ["onboarding", "process"],
            "context_sources": ["previous_runs", "wiki"]
        },
        "win_themes": ["clarity", "completeness"],
        "target_slides": 8
    },
    "created_by": "user@example.com",
    "created_at": "2026-10-30T14:30:00Z",
    "approved_by": null,                     # Set after human review
    "approved_at": null,
    "error_message": null,                   # Set if failed
    "pause_requested": false,
    "resume_requested": false,
    "abort_requested": false
}
```

**Database Schema (Run table):**
```sql
CREATE TABLE runs (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(id),
    status VARCHAR(32) NOT NULL DEFAULT "queued",
    output_types TEXT NOT NULL,              -- JSON: ["docx", "pdf"]
    instruction TEXT NOT NULL,               -- User input (unlimited size)
    plan_payload TEXT NOT NULL,              -- JSON execution plan
    approved_by VARCHAR(64) REFERENCES users(id),
    approved_at DATETIME,
    created_at DATETIME NOT NULL,
    created_by VARCHAR(255),                 -- Email or user ID
    error_message TEXT,
    pause_requested BOOLEAN DEFAULT FALSE,
    resume_requested BOOLEAN DEFAULT FALSE,
    abort_requested BOOLEAN DEFAULT FALSE,
    
    -- Token & Cost Tracking (populated at completion)
    tokens_input INTEGER,
    tokens_output INTEGER,
    tokens_cache_read INTEGER,
    tokens_cache_creation INTEGER,
    cost_usd FLOAT,
    
    -- Prompt Tracking (populated at completion)
    prompts_used TEXT,                      -- JSON: [{"name": "...", "version": "..."}]
    
    -- Indexing
    INDEX ix_runs_project_created_at (project_id, created_at),
    INDEX ix_runs_status (status)
);
```

**Size:** 50-200 KB per row  
**Retention:** Indefinite (audit trail, may be archived)

---

### 1.3 Run Events (Main Audit Trail)

**Type:** Event stream  
**Captured:** Throughout execution  
**Storage:** `RunEvent` table

**Database Schema:**
```sql
CREATE TABLE run_events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(64) NOT NULL REFERENCES runs(id),
    event_type VARCHAR(64) NOT NULL,        -- See event types below
    payload TEXT NOT NULL,                  -- JSON event-specific data
    created_at DATETIME NOT NULL,
    INDEX ix_run_events_run_id (run_id),
    INDEX ix_run_events_type (event_type)
);
```

**Complete Event Types Captured:**

#### Lifecycle Events
```json
{
    "event_type": "step",
    "payload": {
        "status": "execution_enqueued",      // Queued for execution
        "backend": "redis"                   // or "local"
    }
}
```

```json
{
    "event_type": "step",
    "payload": {
        "status": "execution_started"
    }
}
```

#### Skill Selection & Loading
```json
{
    "event_type": "skill_selection",
    "payload": {
        "selected_skill_id": "skill_sop_generator",
        "version": "1.0",
        "reason": "Best match for SOP generation"
    }
}
```

#### Prompt Events
```json
{
    "event_type": "prompt.loaded",
    "payload": {
        "prompt_name": "docx_sop_user",
        "prompt_version": "1.0",
        "template_variables_rendered": {
            "process_model": "onboarding_flow",
            "context": "Customer acquisition"
        }
    }
}
```

#### Token Budget Events
```json
{
    "event_type": "token_budget_check",
    "payload": {
        "prompt_tokens_estimated": 9200,
        "output_tokens_needed": 4096,
        "total_tokens_needed": 13396,
        "remaining_budget": 50000,
        "safety_margin_tokens": 100,
        "fits_in_budget": true
    }
}
```

#### LLM Call Events (Critical)
```json
{
    "event_type": "llm_called",
    "payload": {
        "model": "claude-opus-5-5",
        "system_prompt_chars": 4200,
        "user_prompt_chars": 8500,
        "context_chars": 32000,
        "total_input_chars": 44700,
        
        "tokens": {
            "input_tokens": 9200,
            "output_tokens": 4100,
            "cache_read_input_tokens": 500,        // Prompt cache hits
            "cache_creation_input_tokens": 200,    // New cache entries
            "total_tokens": 14000
        },
        
        "parameters": {
            "temperature": 0.2,
            "max_tokens": 4096,
            "top_p": 1.0
        },
        
        "instruction_key": "skill_sop",
        "stop_reason": "end_turn",
        "latency_ms": 3250,
        "timestamp": "2026-10-30T14:31:10Z",
        
        "cost": {
            "input_cost_usd": 0.46,
            "output_cost_usd": 0.12,
            "cache_read_saving_usd": 0.01,       // 10% cheaper than normal input
            "total_cost_usd": 0.57
        }
    }
}
```

#### Skill Execution Events
```json
{
    "event_type": "agent_tool_round",
    "payload": {
        "skill_id": "skill_sop_generator",
        "status": "completed",
        "execution_time_ms": 4500,
        "output_type": "docx",
        "output_size_bytes": 125400
    }
}
```

#### Quality & Evaluation Events
```json
{
    "event_type": "qa_report",
    "payload": {
        "output_type": "docx",
        "completeness_score": 0.92,
        "design_score": 0.88,
        "structure_score": 0.95,
        "overall_score": 0.92,
        "quality_flags": [
            {
                "severity": "warning",
                "message": "missing_section_risks_and_mitigation",
                "suggestion": "Add risks section to improve completeness"
            }
        ],
        "evidence_gate": {
            "passed": true,
            "unsubstantiated_claims": 0
        }
    }
}
```

```json
{
    "event_type": "visual_qa_report",
    "payload": {
        "artifact_type": "docx",
        "visual_feedback": [
            {
                "severity": "info",
                "message": "Consider adding process diagram",
                "page": 5,
                "confidence": 0.85
            }
        ],
        "design_review_confidence": 0.85
    }
}
```

#### Guardrail Events
```json
{
    "event_type": "guardrail_event",
    "payload": {
        "gate_name": "evidence_gate",
        "status": "passed",
        "unsubstantiated_claims": 0,
        "blocked_content": [],
        "policy_violations": 0
    }
}
```

#### Approval Events
```json
{
    "event_type": "approval_submitted",
    "payload": {
        "approved_by": "user@example.com",
        "timestamp": "2026-10-30T14:45:00Z",
        "status": "approved",
        "notes": "Ready for client delivery"
    }
}
```

#### Retry Events
```json
{
    "event_type": "retry_requested",
    "payload": {
        "reason": "quality_below_threshold",
        "current_score": 0.78,
        "target_score": 0.85,
        "round": 1,
        "max_rounds": 2,
        "feedback": [...]
    }
}
```

#### Memory Events
```json
{
    "event_type": "memory_persisted",
    "payload": {
        "memory_type": "skill_execution",
        "fingerprint": "sha256_hash",
        "deuplicated": false
    }
}
```

**Size Per Event:** 500 B - 50 KB depending on type  
**Total Per Run:** 50-500 events, 1-10 MB aggregate  
**Retention:** Indefinite (immutable audit trail)

---

### 1.4 Task Execution Data (RunTask)

**Type:** Task-level output & metadata  
**Captured:** For each discrete task  
**Storage:** `RunTask` table

```sql
CREATE TABLE run_tasks (
    id VARCHAR(64) PRIMARY KEY,              -- Task ID (e.g., "skill_sop_gen")
    run_id VARCHAR(64) PRIMARY KEY NOT NULL, -- Foreign key to runs
    project_id VARCHAR(64) NOT NULL,
    
    -- Metadata
    title TEXT NOT NULL,                     -- Human-readable task name
    description TEXT,
    phase VARCHAR(16) NOT NULL DEFAULT "act", -- act|sense|plan
    status VARCHAR(16) NOT NULL DEFAULT "queued", -- queued|running|completed|failed
    
    -- Execution Timing
    started_at DATETIME,
    completed_at DATETIME,
    duration_ms INTEGER,
    estimated_duration_sec INTEGER,
    
    -- Dependencies & Relationships
    depends_on_json TEXT NOT NULL DEFAULT "[]", -- JSON: ["task_id", "task_id"]
    swarm_team_id VARCHAR(64),                   -- If part of swarm
    assigned_teammate_id VARCHAR(64),             -- Which teammate executed
    
    -- Execution Details
    skills_used_json TEXT NOT NULL DEFAULT "[]", -- JSON: [{"id": "...", "version": "...", "invoked_count": 1}]
    tools_invoked_json TEXT NOT NULL DEFAULT "[]", -- JSON: [{"name": "wiki_qa", "call_count": 3}]
    
    -- *** CRITICAL: Skill Output Storage ***
    output_json TEXT NOT NULL DEFAULT "{}",      -- JSON: Complete skill output
    
    -- Status & Control
    blocked_reason TEXT,
    requires_approval BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    
    -- Audit
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    
    INDEX ix_run_tasks_run_phase (run_id, phase),
    INDEX ix_run_tasks_run_status (run_id, status)
);
```

**Example Skill Output (output_json field):**

```json
{
    "docx_data": {
        "title": "Onboarding SOP",
        "sections": [
            {
                "heading": "Purpose",
                "heading_level": 1,
                "paragraphs": [
                    {
                        "text": "This SOP documents the complete onboarding process...",
                        "style": "normal"
                    }
                ],
                "figures": [
                    {
                        "type": "table",
                        "data": {...},
                        "caption": "Onboarding Timeline"
                    }
                ]
            },
            {
                "heading": "Procedure",
                "heading_level": 1,
                "paragraphs": [...]
            }
        ],
        "front_matter": {
            "title": "Onboarding SOP",
            "author": "Advise Workbench",
            "date": "2026-10-30",
            "classification": "Internal Use Only"
        },
        "metadata": {
            "page_count": 12,
            "word_count": 8500,
            "section_count": 8,
            "figure_count": 3
        }
    }
}
```

**Size:** 80-500 KB per task (in output_json column)  
**Retention:** Indefinite (queryable for audit/rerun)

**Query to Retrieve Skill Output:**
```sql
SELECT output_json FROM run_tasks 
WHERE run_id = 'run_abc123' AND id = 'skill_sop_gen';
-- Returns: JSON string, ~80-500 KB
```

---

### 1.5 Token & Cost Tracking

**Type:** Aggregated metrics  
**Captured:** After each LLM call, aggregated at run completion  
**Storage:** `Run` table fields + `RunEvent` detailed records

**Stored in Run table:**
```json
{
    "run_id": "run_abc123",
    "tokens_input": 45000,                   // Total input tokens for run
    "tokens_output": 12500,                  // Total output tokens for run
    "tokens_cache_read": 2300,               // Cache hits (cheaper)
    "tokens_cache_creation": 1200,           // New cache entries
    "cost_usd": 2.45                         // Calculated total cost
}
```

**Calculation:**
```python
# Per token pricing (Opus model)
RATE_INPUT_PER_1M = 3.00  # $3 per million input tokens
RATE_OUTPUT_PER_1M = 15.00  # $15 per million output tokens
RATE_CACHE_READ_PER_1M = 0.30  # $0.30 per million cached input tokens (90% discount)
RATE_CACHE_CREATE_PER_1M = 3.75  # $3.75 per million tokens cached (25% premium)

# Calculation
input_cost = (tokens_input + tokens_cache_creation) * (RATE_INPUT_PER_1M / 1_000_000)
output_cost = tokens_output * (RATE_OUTPUT_PER_1M / 1_000_000)
cache_read_benefit = tokens_cache_read * (RATE_CACHE_READ_PER_1M / 1_000_000)

total_cost_usd = input_cost + output_cost - cache_read_benefit
```

**Example Calculation:**
```
Input: 45000 tokens × $3/1M = $0.135
Output: 12500 tokens × $15/1M = $0.1875
Cache creation: 1200 × $3.75/1M = $0.0045
Cache read: 2300 × $0.30/1M = $0.00069

Total: $0.3277 ≈ $0.33
```

**Retention:** Indefinite (billing/audit)

---

### 1.6 Prompt Data (Captured & Tracked)

**Type:** Prompt metadata  
**Captured:** When prompts are loaded/rendered  
**Storage:** Filesystem + In-Memory Context + Database

#### Location 1: Prompts Directory (YAML files)

**File:** `config/prompts/{prompt_name}.yaml`

```yaml
name: docx_sop_user
version: "1.0"
description: "User prompt for SOP document generation with process model context"

system: |
  You are an expert business process and procedures documentation specialist...
  [3-5 KB of system instructions]
  
user: |
  Based on the following process model, generate a comprehensive Standard Operating Procedure.
  
  Process Model:
  ${process_model}
  
  Additional Context:
  ${context}
  
  Requirements:
  - Clear, step-by-step procedure
  - Roles and responsibilities defined
  - Success criteria for each step
```

**Prompt Registry Files:** ~45+ YAML files in `config/prompts/`
- `docx_sop_user.yaml` — SOP generation
- `docx_narrative_user.yaml` — Executive briefing
- `pdf_sop_user.yaml` — PDF version
- `narrative_arc_recommender.yaml` — Storyline selection
- `storyline_spine_builder_user.yaml` — Slide structure
- `qa_review.yaml` — Quality assessment
- ... and 40+ others

#### Location 2: In-Memory Context Variable

**Tracking Prompts Used:**

```python
# src/prompts/registry.py
_prompts_used_context: ContextVar[set[tuple[str, str]]] = ContextVar(
    "prompts_used", 
    default=set()
)

# During execution, each prompt loaded adds to context:
# _prompts_used_context.get() → {
#     ("docx_sop_user", "1.0"),
#     ("narrative_arc_recommender", "2.1"),
#     ("qa_review", "1.0")
# }
```

#### Location 3: Database Persistence

**Stored in Run table at completion:**

```sql
-- Column: Run.prompts_used (TEXT/JSON)
UPDATE runs SET prompts_used = '[
    {"name": "docx_sop_user", "version": "1.0"},
    {"name": "qa_review", "version": "1.0"}
]' WHERE id = 'run_abc123';

-- Query to retrieve:
SELECT prompts_used FROM runs WHERE id = 'run_abc123';
```

#### Location 4: Event Log (For Detailed Tracking)

Each prompt load also recorded in RunEvent:

```json
{
    "event_type": "prompt.loaded",
    "payload": {
        "prompt_name": "docx_sop_user",
        "prompt_version": "1.0",
        "variables_provided": {
            "process_model": "onboarding_flow",
            "context": "Customer acquisition"
        },
        "system_prompt_chars": 4200,
        "user_prompt_chars_rendered": 8500,
        "timestamp": "2026-10-30T14:31:05Z"
    }
}
```

**Retention:**
- YAML files: Indefinite (version controlled in git)
- Context variable: Request lifetime
- Database record: Indefinite (audit)
- Event: Indefinite (audit)

---

### 1.7 Branding Configuration Data

**Type:** Design system & styling  
**Captured:** When run renders deliverables  
**Storage:** Database + Cache + In-Memory

#### Database (ProjectBrand table):

```sql
CREATE TABLE project_brands (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) UNIQUE NOT NULL REFERENCES projects(id),
    
    -- Color Palette
    primary_color VARCHAR(16),               -- e.g., "#86BC25" (Deloitte green)
    secondary_color VARCHAR(16),             -- e.g., "#E8007C"
    accent_light VARCHAR(16),                -- e.g., "#EBF5D3"
    accent_dark VARCHAR(16),                 -- e.g., "#5A8A00"
    
    -- Typography
    font_family VARCHAR(64),                 -- e.g., "Calibri"
    font_size_base INT,                      -- e.g., 11 (points)
    
    -- Assets
    logo_url VARCHAR(1024),                  -- HTTPS URL to company logo
    
    -- Metadata
    company_name VARCHAR(255),               -- e.g., "Deloitte"
    footer_text VARCHAR(255),                -- e.g., "Deloitte."
    custom_footer_text VARCHAR(255),         -- Optional custom footer
    
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    
    INDEX ix_project_brands_project (project_id)
);
```

#### In-Memory Representation (BrandingContext):

```python
@dataclass
class BrandingContext:
    level: BrandingLevel                    # DELOITTE_DEFAULT | PROJECT_CUSTOM | RUNTIME_OVERRIDE
    primary_color: str                      # "#86BC25"
    palette: ColorPalette                   # Full color object
    font_family: str                        # "Calibri"
    font_size_base: int                     # 11
    logo_url: str | None                    # "https://..."
    company_name: str                       # "Deloitte"
    custom_footer_text: str | None          # Custom footer
    deck_theme: str                         # "classic" or "editorial"
```

#### Cache Storage (Redis):

```python
# Key pattern
branding_key = f"branding:project:{project_id}"
# Value: JSON of BrandingContext
# TTL: 86400 seconds (24 hours)

# Logo image cache (separate)
logo_key = f"logo:url:{hash(logo_url)}"
# Value: Image bytes (PNG/JPG)
# TTL: 3600 seconds (1 hour)
```

**Resolution Hierarchy (Priority):**
1. Runtime Override (API params) — Highest priority
2. Skill Override (from payload)
3. ProjectBrand (from DB)
4. Ingested Design System (CSS/tokens)
5. Deloitte Default (code constant) — Lowest priority

**Retention:**
- Database: Indefinite (actively maintained)
- Redis: 24h (branding), 1h (logo)
- In-Memory: Request lifetime

---

### 1.8 Memory Events (Long-term Learning)

**Type:** Skill execution snapshots  
**Captured:** After run completion (optional, if memory integration enabled)  
**Storage:** `MemoryEvent` table

```sql
CREATE TABLE memory_events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(id),
    run_id VARCHAR(64) NOT NULL REFERENCES runs(id),
    event_type VARCHAR(64) NOT NULL,        -- skill_execution|decision|discovery
    fingerprint VARCHAR(64),                -- SHA256 for deduplication
    payload TEXT NOT NULL,                  -- JSON event data
    created_at DATETIME NOT NULL,
    INDEX ix_memory_project_run (project_id, run_id)
);
```

**Example Memory Event:**

```json
{
    "project_id": "proj_xyz789",
    "run_id": "run_abc123",
    "event_type": "skill_execution",
    "fingerprint": "sha256_hash_of_canonical_payload",
    "payload": {
        "skill_id": "skill_sop_generator",
        "input_instruction": "Generate SOP for onboarding process",
        "output_summary": "Generated 12-page SOP with 8 sections",
        "quality_score": 0.92,
        "tokens_used": 45000,
        "execution_time_sec": 4.5,
        "decision_rationale": "Selected SOP skill based on user instruction",
        "insights": [
            "Process clarity improved with visual diagrams",
            "Onboarding steps now clearly defined"
        ]
    }
}
```

**Deduplication:** Via SHA256 fingerprint of canonical (sorted, sanitized) payload  
**Retention:** Indefinite (learning record)

---

## Part 2: Storage Locations & Detailed Architecture

### Storage Layer 1: PostgreSQL/SQLite Database

**Tables & Approximate Sizes:**

```
Table            | Rows/Run  | Bytes/Row    | Total/Run      | Retention
─────────────────┼──────────┼──────────────┼────────────────┼───────────
runs             | 1        | 200 KB       | 200 KB         | Indefinite
run_tasks        | 5-20     | 200 KB       | 1-4 MB         | Indefinite
run_events       | 50-500   | 5-50 KB      | 250 KB-25 MB   | Indefinite
memory_events    | 10-50    | 5-20 KB      | 50-1000 KB     | Indefinite
─────────────────┴──────────┴──────────────┴────────────────┴───────────
Total per run:                                ~2-30 MB       Indefinite
```

**Critical Queries:**

```sql
-- Get complete run
SELECT * FROM runs WHERE id = 'run_abc123';

-- Get all tasks with outputs
SELECT id, status, output_json, skills_used_json FROM run_tasks 
WHERE run_id = 'run_abc123';

-- Get all events in order
SELECT event_type, payload, created_at FROM run_events
WHERE run_id = 'run_abc123' ORDER BY created_at ASC;

-- Get LLM calls only
SELECT payload FROM run_events
WHERE run_id = 'run_abc123' AND event_type = 'llm_called';

-- Get QA reports
SELECT payload FROM run_events
WHERE run_id = 'run_abc123' AND event_type IN ('qa_report', 'visual_qa_report');

-- Get prompts used
SELECT prompts_used FROM runs WHERE id = 'run_abc123';
```

---

### Storage Layer 2: Filesystem (Artifacts & Workspace)

**Directory Structure:**

```
workspace/
└─ {project_id}/
   ├─ runs/
   │  └─ {run_id}/
   │     ├─ artifacts/
   │     │  ├─ deck_001.pptx                 (2-50 MB, binary OOXML)
   │     │  ├─ deck.html                     (3-15 MB, self-contained HTML)
   │     │  ├─ deck.pdf                      (2-25 MB, PDF rendering)
   │     │  ├─ report_001.docx               (1-15 MB, binary OOXML)
   │     │  ├─ report.pdf                    (1-20 MB, PDF)
   │     │  ├─ dashboard_001.xlsx            (1-5 MB, binary OOXML)
   │     │  ├─ process_map.svg               (100 KB - 1 MB, vector)
   │     │  ├─ process_map.pdf               (2-10 MB, rasterized)
   │     │  ├─ handoff_bundle.zip            (20-100 MB, packaged delivery)
   │     │  │
   │     │  ├─ metadata.json                 (1-5 KB, artifact manifest)
   │     │  ├─ pptx_integrity.json           (500 B, SHA256 hashes)
   │     │  ├─ pptx_render_signals.json      (2 KB, pending content)
   │     │  ├─ pptx_visual_feedback.json     (5-10 KB, design feedback)
   │     │  ├─ qa_report_pptx.json           (2-10 KB, quality signals)
   │     │  ├─ qa_report_docx.json           (2-10 KB)
   │     │  ├─ qa_report_xlsx.json           (2-5 KB)
   │     │  └─ .manifest                     (500 B, inventory)
   │     │
   │     └─ intermediate/ (debug/optional)
   │        ├─ pptx_data.json                (50-150 KB)
   │        ├─ docx_data.json                (80-200 KB)
   │        └─ xlsx_data.json                (20-80 KB)
   │
   ├─ custom_skills/
   │  └─ {skill_id}/
   │     ├─ SKILL.md                         (10-50 KB, skill definition)
   │     └─ versions/
   │        ├─ v1.0.json                     (optional JSON version)
   │        └─ v2.0.json
   │
   ├─ wiki/
   │  └─ [Knowledge base files indexed for RAG]
   │
   └─ source_docs/
      ├─ tokens.json                         (optional design system)
      ├─ tokens.css
      └─ tailwind.config.ts
```

**Retention Policies:**

```python
# From EngagementMeta.retention_days
retention_days: int | None

# Cleanup scheduled job:
# DELETE workspace/{project_id}/runs/{run_id}/artifacts/*
# WHERE created_at < NOW() - INTERVAL {retention_days} DAY

# Common Values:
# - 7 days: Draft artifacts (quick review)
# - 30 days: Standard (typical project lifecycle)
# - 90 days: Extended (compliance review)
# - 365 days: Long-term (audit trail)
# - NULL: Indefinite (never delete)
```

---

### Storage Layer 3: Redis Cache

**Cache Patterns & TTLs:**

```python
# Branding context
branding_key = f"branding:project:{project_id}"
cache_service.set(branding_key, branding_dict, ttl_seconds=86400)  # 24h

# Logo image
logo_key = f"logo:url:{hash(logo_url)}"
cache_service.set(logo_key, image_bytes, ttl_seconds=3600)  # 1h

# Token accumulator (per-run, session lifetime)
tokens_key = f"run:tokens:{run_id}"
cache_service.set(tokens_key, usage_snapshot, ttl_seconds=None)

# Skill registry (RECOMMENDED but NOT IMPLEMENTED)
skills_key = f"skills:registry:{project_id}"
cache_service.set(skills_key, skills_list, ttl_seconds=3600)  # 1h

# Prompt cache (LRU in-memory, not Redis)
# LRU cache (@lru_cache maxsize=256) in src/prompts/registry.py
```

**Fallback:** If Redis unavailable, uses in-memory dict with TTL expiration

---

### Storage Layer 4: In-Memory (Request Lifetime)

**Object Allocation During Skill Execution Request:**

```
REQUEST START
│
├─ Skill registry lookup           [10-20 KB]
├─ Prompt loading (LRU cache)      [10-50 KB]
├─ Process model context           [50-200 KB]
├─ Branding context                [5-10 KB]
└─ Subtotal: ~75-290 KB

LLM CALL PHASE
├─ Prompt in memory                [15-50 KB]
└─ Subtotal: ~90-340 KB

RENDERING PHASE (if immediate)
├─ Create Presentation object      [50-100 KB base]
├─ Add slides, shapes, text        [100-200 KB]
├─ Logo image (from cache/fetch)   [2-5 MB]
├─ Payload dict (output)           [80-500 KB]
└─ Subtotal: ~2.3-5.8 MB

WRITE TO DISK
├─ prs.save() writes binary        [2-50 MB on disk]
├─ Presentation released (GC)
└─ Subtotal: File I/O only

POST-EXECUTION
├─ GC: skill_dict                  ✓
├─ Keep: prompts (LRU cache)       ✓
├─ GC: branding_context            ✓
├─ GC: payload_dict                ✓
├─ GC: presentation_object         ✓
└─ PEAK MEMORY RETURNED: ~5.8 MB max
```

**Thread Safety:** Uses `ContextVar` for thread-safe context propagation in async tasks

---

## Part 3: Complete Retention Policies

| Data Type | Storage | TTL/Retention | Policy | Managed By |
|-----------|---------|-----------|--------|-----------|
| **Run metadata** | Database | Indefinite | Never deleted | Manual archive |
| **Run tasks** | Database | Indefinite | Never deleted | Audit trail |
| **Run events** | Database | Indefinite | Immutable | Event log |
| **Memory events** | Database | Indefinite | Deduplicated | Learning system |
| **LLM call details** | RunEvent | Indefinite | Billing audit | Accounting |
| **Token usage** | Run table | Indefinite | Billing audit | Accounting |
| **Cost calculation** | Run table | Indefinite | Billing audit | Accounting |
| **Artifacts (.pptx/.docx)** | Filesystem | 7-365d or NULL | Per-project policy | Scheduled cleanup |
| **QA reports** | Filesystem | 7-365d or NULL | Per-project policy | Scheduled cleanup |
| **Export formats (.html/.pdf)** | Filesystem | 7-365d or NULL | Per-project policy | Scheduled cleanup |
| **Integrity manifests** | Filesystem | 7-365d or NULL | Per-project policy | Scheduled cleanup |
| **Prompts (YAML)** | Filesystem | Indefinite | Version controlled | Git |
| **Skill definitions** | Filesystem | Indefinite | Version controlled | Git |
| **Logo cache** | Redis | 1 hour | Automatic eviction | Redis TTL |
| **Branding cache** | Redis | 24 hours | Automatic eviction | Redis TTL |
| **Prompts (LRU)** | Memory | App lifetime | Max 256 entries | LRU eviction |
| **Skill registry** | Memory | Request lifetime | Reloaded per request | GC after request |

---

## Part 4: Prompt Storage at Every Step (Detailed)

### Step 1: Skill Registration Phase
**Where:** `config/skills/{name}/SKILL.md` or custom workspace  
**What Stored:**
```yaml
prompt_instructions: |
  [System prompt embedded in frontmatter]
  [1-5 KB of text]
```

### Step 2: Prompt Registry (YAML Externalization)
**Where:** `config/prompts/{prompt_name}.yaml`  
**What Stored:**
```yaml
name: docx_sop_user
version: "1.0"
system: "[System prompt]"
user: "[User template with ${variables}]"
```

### Step 3: Runtime Prompt Loading
**Where:** In-memory (request scope)  
**What Happens:**
```python
# Load via LRU cache
prompt = get_prompt("docx_sop_user")  # Cached

# Track usage
_record_prompt_used("docx_sop_user", "1.0")  # In ContextVar

# Render with runtime variables
user_prompt = prompt.render_user(
    process_model="onboarding_flow",
    context="Customer acquisition"
)

# System prompt (unchanged)
system_prompt = prompt.render_system()
```

### Step 4: LLM Call
**Where:** Sent to Claude API  
**What's Tracked:**
```json
{
    "event_type": "llm_called",
    "payload": {
        "system_prompt_chars": 4200,
        "user_prompt_chars": 8500,
        "model": "claude-opus-5-5"
    }
}
```

### Step 5: Prompts Used Recording
**Where:** In-memory ContextVar → Database at completion  
**What's Stored:**
```json
{
    "run_id": "run_abc123",
    "prompts_used": [
        {"name": "docx_sop_user", "version": "1.0"},
        {"name": "qa_review", "version": "1.0"}
    ]
}
```

---

## Part 5: LLM Call Tracking (Complete)

### Per-Call Tracking

```json
{
    "call_id": "uuid",
    "timestamp": "ISO-8601",
    "model": "claude-opus-5-5",
    
    "prompts": {
        "system_prompt_chars": 4200,
        "user_prompt_chars": 8500,
        "context_chars": 32000
    },
    
    "tokens": {
        "input_tokens": 9200,
        "output_tokens": 4100,
        "cache_read_input_tokens": 500,
        "cache_creation_input_tokens": 200,
        "total_tokens": 14000
    },
    
    "cost": {
        "input_cost_usd": 0.46,
        "cache_read_benefit_usd": -0.01,
        "output_cost_usd": 0.12,
        "total_cost_usd": 0.57
    },
    
    "performance": {
        "latency_ms": 3250,
        "time_to_first_token_ms": 450
    }
}
```

### Aggregation at Run Completion

```python
# Sum all LLM calls in run
total_tokens_input = sum(call['tokens']['input_tokens'] for call in all_llm_calls)
total_tokens_output = sum(call['tokens']['output_tokens'] for call in all_llm_calls)
total_tokens_cache_read = sum(call['tokens']['cache_read_input_tokens'] for call in all_llm_calls)
total_tokens_cache_creation = sum(call['tokens']['cache_creation_input_tokens'] for call in all_llm_calls)

# Calculate total cost
total_cost_usd = sum(call['cost']['total_cost_usd'] for call in all_llm_calls)

# Store in Run table
run.tokens_input = total_tokens_input
run.tokens_output = total_tokens_output
run.tokens_cache_read = total_tokens_cache_read
run.tokens_cache_creation = total_tokens_cache_creation
run.cost_usd = total_cost_usd

session.commit()
```

---

## Part 6: Token Budget Tracking

### Token Budget System

**In-Memory Tracking (ContextVar):**

```python
_remaining: ContextVar[int | None] = ContextVar(
    "run_llm_budget_remaining", 
    default=None
)

_active_usage: ContextVar[_RunTokenUsage | None] = ContextVar(
    "run_active_usage", 
    default=None
)
```

**Budget Checking Before LLM Call:**

```python
class TokenBudgetChecker:
    CHARS_PER_TOKEN = 3.5
    SAFETY_MARGIN_TOKENS = 100
    
    @staticmethod
    def check_budget(system: str, user: str, needed_output=4096):
        # Estimate tokens
        system_tokens = len(system) / 3.5
        user_tokens = len(user) / 3.5
        overhead = 100
        prompt_tokens = system_tokens + user_tokens + overhead
        
        total_needed = prompt_tokens + needed_output + SAFETY_MARGIN
        remaining = get_remaining_token_budget()
        
        fits = total_needed <= remaining
        
        return fits, {
            'prompt_tokens': prompt_tokens,
            'output_tokens': needed_output,
            'total_needed': total_needed,
            'remaining': remaining,
            'compression_needed': max(0, total_needed - remaining)
        }
```

**Budget Enforcement Event:**

```json
{
    "event_type": "token_budget_check",
    "payload": {
        "prompt_tokens_estimated": 9300,
        "output_tokens_needed": 4096,
        "safety_margin_tokens": 100,
        "total_tokens_needed": 13496,
        "remaining_budget": 50000,
        "fits_in_budget": true,
        "compression_applied": false
    }
}
```

---

## Part 7: Approval Workflow & Data Capture

### Approval Request Trigger

**When Captured:** Run completes and requires human review

```json
{
    "run_id": "run_abc123",
    "requires_approval": true,
    "status": "review_ready",
    "artifacts": [
        "deck_001.pptx",
        "report_001.docx"
    ]
}
```

### Approval Event

```json
{
    "event_type": "approval_submitted",
    "payload": {
        "approved_by": "reviewer@example.com",
        "decision": "approved",
        "timestamp": "2026-10-30T14:45:00Z",
        "notes": "Ready for client delivery",
        "quality_score_at_approval": 0.92
    }
}
```

### Storage

```sql
UPDATE runs SET
    approved_by = 'user@example.com',
    approved_at = '2026-10-30T14:45:00Z',
    status = 'done'
WHERE id = 'run_abc123';
```

---

## Part 8: Hook Execution Tracking

**Table:** `HookExecution`

```sql
CREATE TABLE hook_executions (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(64) NOT NULL REFERENCES runs(id),
    hook_point VARCHAR(64) NOT NULL,       -- before_generation|after_generation
    hook_name VARCHAR(128) NOT NULL,        -- Custom hook identifier
    hook_exec_id VARCHAR(64) NOT NULL,      -- SHA256 for idempotency
    idempotency_key VARCHAR(128),
    outcome VARCHAR(16) NOT NULL DEFAULT "OK", -- OK|ERROR|SKIPPED
    created_at DATETIME NOT NULL,
    INDEX ix_hook_exec_run (run_id),
    INDEX ix_hook_exec_idem (run_id, idempotency_key)
);
```

**Captured Data:**
- Hook point (lifecycle stage)
- Hook name (identifier)
- Outcome (success/failure/skip)
- Idempotency tracking (prevent duplicates)

---

## Summary Table: Complete Data Mapping

| Data Category | Data Type | Captured Where | Stored Where | Size | Retention | Query |
|---|---|---|---|---|---|---|
| **EXECUTION** | Run metadata | Run start | Run table | 50-200 KB | Indefinite | `SELECT * FROM runs WHERE id=?` |
| | Instruction | User input | Run.instruction | 1-10 KB | Indefinite | |
| | Plan | Generated | Run.plan_payload | 20-100 KB | Indefinite | |
| **SKILLS** | Skill meta | Load time | Memory only | 5-10 KB | Request lifetime | `load_builtin_skills()` |
| | Registry | Load time | Memory only | 10-20 KB | Request lifetime | `_merged_skill_registry()` |
| | Output | LLM output | RunTask.output_json | 80-500 KB | Indefinite | `SELECT output_json FROM run_tasks WHERE run_id=?` |
| **PROMPTS** | Definitions | File system | YAML files | 1-5 KB ea | Indefinite | `config/prompts/{name}.yaml` |
| | Usage tracking | Execution | ContextVar + Run.prompts_used | 500B-5KB | Indefinite | `SELECT prompts_used FROM runs WHERE id=?` |
| **LLM** | API calls | Each call | RunEvent | 1-5 KB ea | Indefinite | Event query |
| | Token count | Per call | RunEvent + Run aggregate | <1 KB | Indefinite | Run.tokens_* |
| | Cost | Per call | RunEvent + Run.cost_usd | <1 KB | Indefinite | `SELECT cost_usd FROM runs WHERE id=?` |
| **EVENTS** | Lifecycle | During run | RunEvent (event_type=step) | 500B ea | Indefinite | Event query |
| | Quality | After render | RunEvent (event_type=qa_report) | 2-10 KB | Indefinite | Event query |
| | Guardrails | Policy check | RunEvent (event_type=guardrail) | 1-5 KB | Indefinite | Event query |
| | Approval | Human review | RunEvent + Run.approved_* | 1-5 KB | Indefinite | Event query |
| **DELIVERABLES** | Artifact files | Render | Filesystem `/artifacts/` | 2-50 MB | 7-365d/NULL | `ls workspace/../artifacts/` |
| | QA reports | Quality check | Filesystem + RunEvent | 2-10 KB | 7-365d/NULL | JSON files + Event query |
| | Metadata | After render | `/artifacts/metadata.json` | 1-5 KB | 7-365d/NULL | JSON file |
| **MEMORY** | Skill execution | Run complete | MemoryEvent | 1-10 KB | Indefinite | `SELECT * FROM memory_events WHERE run_id=?` |
| | Decision records | Throughout | MemoryEvent | 1-5 KB | Indefinite | Memory query |
| **BUDGET** | Token budget | Pre-call check | Event + ContextVar | <1 KB | Request lifetime | Event query |
| | Token usage | Post-call | ContextVar → Run | <1 KB | Indefinite | `SELECT tokens_* FROM runs WHERE id=?` |

---

## Quick Reference Queries

```sql
-- Complete run execution history
SELECT 
    r.id, r.status, r.created_at,
    r.tokens_input, r.tokens_output, r.cost_usd,
    r.prompts_used
FROM runs r WHERE r.id = 'run_abc123';

-- All skill outputs
SELECT id, status, output_json 
FROM run_tasks WHERE run_id = 'run_abc123';

-- All events in order
SELECT event_type, payload, created_at 
FROM run_events WHERE run_id = 'run_abc123'
ORDER BY created_at ASC;

-- LLM calls with token details
SELECT payload->'$.tokens' as tokens, payload->'$.cost' as cost
FROM run_events 
WHERE run_id = 'run_abc123' AND event_type = 'llm_called';

-- Quality reports
SELECT payload 
FROM run_events 
WHERE run_id = 'run_abc123' 
  AND event_type IN ('qa_report', 'visual_qa_report');

-- Memory insights from this run
SELECT payload 
FROM memory_events 
WHERE run_id = 'run_abc123'
ORDER BY created_at DESC;

-- Branding used in run
SELECT * 
FROM project_brands 
WHERE project_id = (SELECT project_id FROM runs WHERE id = 'run_abc123');
```

---

**End of Comprehensive Document**

*This document covers ALL data captured, stored, and retained in the skills section with complete details on storage locations, retention policies, prompt handling, LLM tracking, process monitoring, memory management, and query references.*
