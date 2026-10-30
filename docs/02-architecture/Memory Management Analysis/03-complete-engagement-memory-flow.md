# Complete Memory Capture, Storage, Retention & Engagement Data Flow

## TABLE OF CONTENTS
1. [Memory Types Captured](#memory-types-captured)
2. [Storage Locations](#storage-locations)
3. [Retention Periods](#retention-periods)
4. [Prompt Storage at Each Step](#prompt-storage-at-each-step)
5. [Complete Engagement Process Flow](#complete-engagement-process-flow)
6. [Data Storage for Process & LLM](#data-storage-for-process--llm)
7. [Configuration Reference](#configuration-reference)

---

## MEMORY TYPES CAPTURED

### 1. **User Input Memory**

#### A. **Conversation Messages**
- **What**: User messages and assistant responses
- **Table**: `conversation_messages` (`src/core/db/models.py` lines 338-354)
- **Fields Stored**:
  ```
  id (int, PK auto-increment)
  conversation_id (FK)
  role ("user" | "assistant")
  content (Text - full message body)
  metadata_json (JSON - tool_calls, citations, source info)
  source_type (e.g., "wiki", "discovery")
  source_freshness_at (timestamp when source was updated)
  created_at (indexed)
  ```
- **When Captured**: After each user message is sent or assistant reply generated
- **Indexing**: `(conversation_id)`, `(created_at)`

#### B. **Discovery Answers**
- **What**: Answers to discovery questions (client, outcome, success measures)
- **Stored In**:
  1. **MemoryEvent Table** (event-sourced)
  2. **ProjectMemoryProfile** (aggregated state)
- **Discovery Slots**:
  ```
  client: {"name": "Acme Corp"}
  outcome: {"primary": "Streamline operations"}
  win_themes: ["Cost reduction", "Efficiency", "Risk mitigation"]
  scope: {"boundaries": "..."}
  success_criteria: {...}
  timeline: {"start": "...", "end": "..."}
  constraints: [{...}]
  ```
- **Recording Function**: `record_discovery_answer(session, project_id, user_id, slot_key, value)`

#### C. **Routing Decisions**
- **What**: Decisions made during conversation (output format, doc style, etc.)
- **Stored In**:
  1. **MemoryEvent Table** (event log)
  2. **ProjectMemoryProfile** (aggregated)
- **Decision Types**:
  ```
  output_format (e.g., "pptx", "docx", "sop")
  doc_style (e.g., "executive", "technical", "narrative")
  delivery_method (e.g., "email", "portal", "download")
  approval_method (e.g., "email", "portal")
  success_measures_type (e.g., "financial", "operational", "strategic")
  ```
- **Recording Function**: `record_routing_decision(session, project_id, user_id, decision_type, confidence, value)`

---

### 2. **Event-Based Memory**

#### **MemoryEvent Table** (`src/core/db/models.py` lines 295-305)

**Event Types Captured**:
```
1. discovery_answer_recorded
   Payload: {"user_id", "slot_key", "value"}
   
2. routing_decision_recorded
   Payload: {"user_id", "decision_type", "confidence", "value"}
   
3. qa_outcome
   Payload: {"check_id", "passed": bool, "issues": [...]}
   
4. qa_remediation
   Payload: {"output_type", "changes": [...]}
   
5. guardrail_outcome
   Payload: {"gate_id", "status", "violations": [...]}
   
6. user_intent_updated
   Payload: {"intent_type", "new_intent"}
   
7. artifact_summary
   Payload: {"output_type", "size_bytes", "quality_score"}
```

**Deduplication**:
```
fingerprint = SHA256(project_id|run_id|event_type|canonical_payload_json)
Events with identical fingerprints are not duplicated
```

---

### 3. **Aggregated State Memory**

#### **ProjectMemoryProfile Table** (`src/core/db/models.py` lines 307-313)

**What It Stores**:
```json
{
  "users": {
    "user-id-1": {
      "aggregated_slots": {
        "client": {"name": "...", "industry": "..."},
        "outcome": {"primary": "...", "secondary": [...]},
        "win_themes": [...],
        "timeline": {"start_date": "...", "target_close": "..."},
        "constraints": [...]
      },
      "decision_outcomes": {
        "output_format": {
          "value": "pptx",
          "count": 3,
          "avg_confidence": 0.92,
          "last_outcome": "pptx",
          "last_updated_at": "2026-10-30T14:30:00Z"
        },
        "doc_style": {
          "value": "executive",
          "count": 5,
          "avg_confidence": 0.88,
          "last_outcome": "executive",
          "last_updated_at": "2026-10-30T14:35:00Z"
        }
      },
      "updated_at": "2026-10-30T14:35:00Z"
    },
    "user-id-2": {...}
  }
}
```

**Updated When**:
1. `record_discovery_answer()` is called
2. `record_routing_decision()` is called
3. Profile aggregation runs (post-run)

---

### 4. **Persistent Knowledge Memory**

#### **MemoryItem Table** (`src/core/db/models.py` lines 373-392)

**Knowledge Types Stored**:
```
memory_type = "preference" | "constraint" | "decision" | "fact"
key (unique per project + type)
value (knowledge content)
confidence ("low" | "medium" | "high")
source ("chat" | "document" | "system")
consent_state ("allowed" | "blocked" | custom)
principal_id (optional, for DPDP consent checks)
is_archived (soft delete, not removed)
```

**Examples**:
```
Type: preference
Key: "preferred_output_style"
Value: "Executive summary with financial focus"

Type: constraint
Key: "budget_constraint"
Value: "$500K max investment over 3 years"

Type: decision
Key: "approved_vendor"
Value: "Acme Corp selected for implementation phase"

Type: fact
Key: "org_size"
Value: "500 employees, distributed across 3 regions"
```

---

### 5. **User Personalization Memory**

#### **UserProjectPreference Table** (`src/core/db/models.py` lines 315-324)

**What's Stored**:
```json
{
  "user_id": "user-123",
  "project_id": "proj-456",
  "preferences_json": {
    "context_lines": [
      "Prefers detailed technical documentation",
      "Focus on financial ROI metrics",
      "Requires compliance-first approach",
      "Abbreviate timelines, prefer concise format"
    ],
    "learning_signals": {
      "runs_completed": 15,
      "avg_output_quality": 0.89,
      "preferred_output_types": ["pptx", "sop"],
      "fast_track_indicators": ["financial_models", "process_maps"]
    }
  }
}
```

**Updated When**:
- User completes a run successfully
- User explicitly saves preferences
- System learns from feedback/outcomes

---

### 6. **Engagement-Specific Memory**

#### **EngagementMeta Table** (`src/core/db/models.py` lines 66-97)

**What's Captured**:
```
code: "ENG-2026-0428"           # Engagement identifier
type: "SOW" | "Project" | ...   # Classification
stage: "Discovery" | ...        # Progress stage
progress: 45                    # Percentage complete
client_org: "Acme Corp"
brief: "Streamline operations..."
sponsor_objective: "Reduce manual processes..."
scope: "Current state, To-be design, implementation plan"
success_measures: "30% cost reduction; 50% cycle time improvement; ..."
start_date: "2026-10-15"
target_close: "2027-02-28"
classification: "Confidential"
retention_days: 365            # Data retention period
status: "active" | "closed" | "archived"
next_task: "Board approval meeting"
due_date: "2026-11-15"
created_at, updated_at: timestamps
```

**Purpose**: Pre-fills discovery and provides context to LLM

---

### 7. **Conversation State Memory**

#### **ConversationState Files** (`workspace/{project_id}/conversation_state/`)

**Persistent JSON Format**:
```json
{
  "state": "discovery",  // FSM state
  "slots": {
    "client": {"name": "Acme Corp"},
    "outcome": {"primary": "..."},
    "win_themes": ["...", "..."]
  },
  "deliverable": "sop",
  "last_router": "output_format_router",
  "pending_questions": ["success_measures", "timeline"],
  "history_summary": "User described pain points in current manual processes...",
  "updated_at": "2026-10-30T14:30:00Z"
}
```

**States**:
```
new → exploring → discovery → storyline_building 
  → slide_negotiation → structure_agreed → ready_to_plan 
  → plan_proposed → confirming → done
```

---

### 8. **Run Execution Memory**

#### **RunEvent Table** (`src/core/db/models.py` lines 182-197)

**Events Recorded**:
```
event_type: "execution_enqueued" | "execution_started" | "coordinator_plan_generated" | ...
payload: {
  "schema_version": "run-events-v1",
  "event_type": "...",
  "phase": "planning" | "execution" | "qa" | "delivery",
  "ts_ms": 1698567000000,
  "run_id": "run-abc123",
  "payload": {...}
}
created_at: indexed for ordering
```

**Canonical Event Envelope**:
```python
{
  "schema_version": "run-events-v1",
  "event_type": str,
  "phase": str,
  "ts_ms": int,
  "run_id": str,
  "payload": dict
}
```

---

## STORAGE LOCATIONS

### **Database Storage** (Primary)

#### **Connection Configuration**
```
DATABASE_URL = "sqlite:///./advise_workbench.db"  (default)
         OR   "postgresql+psycopg://USER:PASS@HOST:5432/advise_workbench"
```

#### **Tables Overview**

| Table | Type | Purpose | Retention |
|-------|------|---------|-----------|
| `users` | Auth | User accounts | Indefinite |
| `projects` | Engagement | Project headers | Indefinite |
| `engagement_meta` | Engagement | Engagement metadata | As configured |
| `conversation` | Conversation | Chat sessions | Indefinite |
| `conversation_messages` | Conversation | Individual messages | Indefinite |
| `conversation_turns` | Conversation | Background turn processing | Indefinite |
| `memory_events` | Memory | Event log | 30 days (configurable) |
| `memory_items` | Memory | Knowledge units | Indefinite |
| `project_memory_profile` | Memory | Aggregated state | Indefinite |
| `user_project_preferences` | Personalization | Per-user preferences | Indefinite |
| `run_events` | Execution | Run event log | Indefinite (audit trail) |
| `runs` | Execution | Run metadata | Indefinite |
| `consent_ledger` | Privacy | DPDP consent records | Indefinite |
| `wiki_pages` | Knowledge | LLM-maintained wiki | Indefinite |
| `wiki_index` | Knowledge | Wiki catalog | Indefinite |
| `wiki_logs` | Audit | Wiki operation audit | Indefinite |

---

### **File System Storage** (Secondary)

#### **Workspace Directory Structure**

```
WORKSPACE_ROOT/
├── {project_id}/
│   ├── source_docs/                    # Uploaded source documents
│   │   ├── contract_2026.pdf
│   │   ├── process_flowchart.docx
│   │   └── ...
│   │
│   ├── parsed_docs/                    # Parsed chunks (JSON)
│   │   ├── {sha256_1}.json
│   │   │   └── {"chunks": [...], "filename": "...", "sha256": "..."}
│   │   ├── {sha256_2}.json
│   │   └── ...
│   │
│   ├── wiki/                           # Project wiki (markdown)
│   │   ├── index.md                    # Wiki index
│   │   ├── process_overview.md
│   │   ├── integration_points.md
│   │   ├── deployment_guide.md
│   │   └── ...
│   │
│   ├── conversation_state/             # Persistent conversation state
│   │   ├── {conversation_id_1}.json
│   │   ├── {conversation_id_2}.json
│   │   └── ...
│   │
│   ├── runs/                           # Run outputs and artifacts
│   │   ├── {run_id_1}/
│   │   │   ├── manifest.json
│   │   │   ├── narrative.md
│   │   │   ├── sop.md
│   │   │   ├── raci.html
│   │   │   ├── raci.xlsx
│   │   │   ├── output.docx
│   │   │   ├── output.pptx
│   │   │   ├── process_map.mmd
│   │   │   ├── drawio.xml
│   │   │   ├── process_model.json
│   │   │   ├── qa_report.json
│   │   │   ├── guardrail_report.json
│   │   │   ├── memory_summary.json
│   │   │   ├── compaction_snapshot.json
│   │   │   ├── artifacts_typed.json
│   │   │   ├── render_status.json
│   │   │   ├── pptx_slides.json
│   │   │   └── assembled_context.txt
│   │   ├── {run_id_2}/
│   │   └── ...
│   │
│   ├── custom_skills/                  # Custom skill definitions
│   ├── brand/                          # Branding assets
│   ├── dpdp/                           # DPDP/consent records
│   ├── CONTEXT.md                      # Tier 0 context (2000 chars)
│   └── README.md
│
├── .checkpoints/                       # LangGraph checkpoints
│   └── run_graph.sqlite
│
└── .metrics/                           # Observability snapshots
    └── metrics.json
```

**Directory Creation** (`ensure_workspace(project_id)`):
```python
base = workspace_path(project_id)
Directories created:
  - source_docs/
  - parsed_docs/
  - runs/
  - custom_skills/
  - brand/
  - dpdp/
  - .checkpoints/
  
Files created:
  - CONTEXT.md (initialized with "# Project Context\n")
  - .gitignore
  - README.md (Obsidian vault guide)
```

---

### **Redis Cache Storage** (Tertiary)

#### **Cache Key Patterns**

```
conversation:{project_id}:{user_id}
  └─ Value: {"input_tokens": N, "output_tokens": N, "cache_read": N, "cache_creation": N}
  
parsed_docs:{project_id}
  └─ Value: {"chunks": [...], "bm25_index": {...}}
  
wiki:{project_id}
  └─ Value: [chunk_strings with stale marking]
  
preference:{user_id}:{project_id}
  └─ Value: {"context_lines": [...]}
  
engagement_brief:{project_id}
  └─ Value: {"text": "[EngagementBrief]\nClient: ...\n..."}
  
token_usage:run:{run_id}
  └─ Value: {snapshot of live token counts}
```

#### **TTL Configuration**

```
Default TTL: 3600 seconds (1 hour)
File cache invalidation: mtime-based (automatic when files change)
Wiki stale marking: 72 hours (files older than this marked [STALE])
```

---

### **In-Memory Storage** (Runtime)

#### **Context Variables** (Thread-scoped)

```python
_remaining: ContextVar[int | None]              # Token budget remaining
_active_usage: ContextVar[_RunTokenUsage]       # Current run token usage
_active_project_usage: ContextVar[_RunTokenUsage]  # Project-level accumulation
_active_capture: ContextVar[_RunTokenUsage]     # Single capture context

_LIVE_PHASE: dict[str, str]                     # turn_id → current phase (ephemeral)
_LIVE_USAGE: dict[str, _RunTokenUsage]          # run_id → usage object (while executing)
_live_captures: dict[str, _RunTokenUsage]       # capture_key → usage (during operations)
```

#### **Metrics Storage**

```python
_COUNTERS: dict[str, int]                       # Counter values
_LATENCY_TOTAL_MS: dict[str, float]             # Latency sum
_LATENCY_COUNT: dict[str, int]                  # Latency count (for avg)
_GAUGES: dict[str, float]                       # Point-in-time values
_RECENT_RUNS: list[dict]                        # Last 200 run events
```

---

## RETENTION PERIODS

### **Database Retention Policies**

| Resource | Default Retention | Configuration | Notes |
|----------|------------------|---------------|----|
| **MemoryEvent** | 30 days | `MEMORY_EVENTS_RETENTION_DAYS=30` | Pruned by background job |
| **ConversationMessage** | Indefinite | None | Audit trail, never deleted |
| **RunEvent** | Indefinite | None | Critical for replay & recovery |
| **MemoryItem** | Indefinite | None | Soft-deleted with `is_archived=true` |
| **ProjectMemoryProfile** | Indefinite | None | Updated, not deleted |
| **EngagementMeta** | Configurable | `retention_days` field | Per-engagement setting |
| **ConsentLedger** | Indefinite | None | Legal/compliance requirement |

### **File System Retention**

| Location | Retention | Cleanup | Notes |
|----------|-----------|---------|-------|
| **source_docs/** | Indefinite | Manual | User responsibility |
| **parsed_docs/** | Indefinite | Manual | Regenerated on upload |
| **runs/** | Indefinite | Manual | Archives available |
| **wiki/** | Indefinite | Manual | LLM-maintained, flagged if edited |
| **conversation_state/** | Indefinite | Manual/Auto | Stale > 72h marked |
| **CONTEXT.md** | Indefinite | Manual | User-controlled |
| **.checkpoints/run_graph.sqlite** | Indefinite | Manual | LangGraph checkpoint DB |

### **Redis Cache Retention**

| Cache Key | TTL | Notes |
|-----------|-----|-------|
| `conversation:{pid}:{uid}` | 3600 sec | 1 hour, can expire earlier |
| `parsed_docs:{pid}` | Until file change | Mtime-based invalidation |
| `wiki:{pid}` | Until file change | Mtime-based, 72h stale mark |
| `preference:{uid}:{pid}` | 3600 sec | User preferences |
| `engagement_brief:{pid}` | 1800 sec | 30 minutes |
| `token_usage:run:{rid}` | Session duration | Deleted when run completes |

### **Cleanup Procedures**

#### **Memory Event Pruning** (Automatic)

```python
# Runs at startup and periodically
query: DELETE FROM memory_events WHERE created_at < NOW() - INTERVAL '{MEMORY_EVENTS_RETENTION_DAYS} days'
counter: memory_events_pruned_total (incremented)
```

#### **Conversation Compression** (On Access)

```python
# 4-tier compaction applied when conversation > char_cap
Tier 1: Drop fragments (≤24 chars)
Tier 2: Keep newest 120 messages only
Tier 3: Auto-summarize head to 1200 chars
Tier 4: Keep newest 5 messages only
```

---

## PROMPT STORAGE AT EACH STEP

### **Step 1: Engagement Creation**

**Prompts Generated & Stored**:

#### a. **Engagement Brief Prompt** (Stored in: `EngagementMeta`)
```
Formatted at: _engagement_context.py::engagement_brief_text()
Format:
[EngagementBrief]
Engagement: ProjectName (ENG-001)
Client: Acme Corp
Type: SOW
Brief: Streamline manual invoice processing...
Sponsor objective: Reduce operational costs by 30%
Scope: Current state → To-be design → Implementation roadmap
Success measures: Cost reduction (30%), Cycle time (50% faster), Error rate (<1%)
Timeline: 2026-10-15 to 2027-02-28
Classification: Confidential

Storage Location: 
  - Database: EngagementMeta.brief, sponsor_objective, scope, success_measures
  - Redis Cache: engagement_brief:{project_id} (TTL: 1800 sec)
  - Discovery Slots: Used in discovery_answer recording
```

#### b. **Discovery Prompt** (Used to pre-fill)
```
Extracted from: _engagement_context.py::engagement_discovery()
Slots pre-filled:
  {
    "client": {"name": "Acme Corp"},
    "outcome": {"primary": "Reduce manual processes..."},
    "win_themes": ["Cost reduction", "Efficiency", "Risk mitigation"]
  }

Storage Location:
  - Database: ProjectMemoryProfile.users[uid].aggregated_slots
  - Sent to LLM: Prevents re-asking already-known information
```

---

### **Step 2: Initial Conversation Message**

**What's Captured & Stored**:

#### a. **User Message**
```
Storage:
  - Table: conversation_messages
  - Fields: conversation_id, role="user", content, metadata_json, created_at

Example:
{
  "conversation_id": "conv_abc123",
  "role": "user",
  "content": "We need to streamline our accounts payable process. Reduce manual keying, improve cycle time.",
  "metadata_json": {
    "source_type": "chat",
    "source_freshness_at": "2026-10-30T14:30:00Z"
  },
  "created_at": "2026-10-30T14:30:01Z"
}
```

#### b. **System Prompt Assembled**
```
Components Assembled (in order):
1. Role definition (fixed)
2. Engagement brief (from EngagementMeta)
3. Discovery slots (from ProjectMemoryProfile)
4. Long-term items (from MemoryItem rows, consent-filtered)
5. User preferences (from UserProjectPreference.context_lines)
6. Conversation history (last N messages, compacted)
7. Wiki references (BM25-ranked from wiki/)
8. Parsed docs chunks (BM25-ranked from parsed_docs/)

Tokens Estimated: len(system) / 3.5 + 100 (overhead)

Storage: 
  - NOT stored (ephemeral, reconstructed per request)
  - BUT: component sources stored in DB tables
```

#### c. **Assistant Response**
```
Storage:
  - Table: conversation_messages
  - Fields: conversation_id, role="assistant", content, metadata_json, created_at

Example:
{
  "conversation_id": "conv_abc123",
  "role": "assistant",
  "content": "I understand. Let me map the current AP process...",
  "metadata_json": {
    "tool_calls": [{"name": "retrieve_context", "args": {...}}],
    "citations": [{"source": "wiki:process_overview"}]
  },
  "created_at": "2026-10-30T14:31:45Z"
}
```

#### d. **Discovery Answers Recorded**
```
Storage:
  1. MemoryEvent Table:
     {
       "project_id": "proj_123",
       "run_id": "run_latest",
       "event_type": "discovery_answer_recorded",
       "fingerprint": "sha256(...)",
       "payload": "{\"user_id\": \"...\", \"slot_key\": \"client\", \"value\": \"Acme Corp\"}",
       "created_at": "2026-10-30T14:31:46Z"
     }

  2. ProjectMemoryProfile Updated:
     {
       "project_id": "proj_123",
       "summary_json": {
         "users": {
           "user_123": {
             "aggregated_slots": {
               "client": {"name": "Acme Corp"},
               "outcome": {"primary": "..."}
             }
           }
         }
       }
     }
```

---

### **Step 3: Routing & Decision Making**

**Decision Prompt Storage**:

```
Decision Point: "What output format would you like?"

Routing Prompt Components:
1. User instruction summary
2. Detected intent signals
3. Available output types
4. Past successful outcomes (from ProjectMemoryProfile)
5. User preferences (from UserProjectPreference)

Storage:
  - NOT stored directly
  - User's choice stored as routing_decision MemoryEvent
  - Updated in ProjectMemoryProfile.decision_outcomes
```

**Recording Decision**:
```
record_routing_decision(
  session,
  project_id="proj_123",
  user_id="user_123",
  decision_type="output_format",
  confidence=0.92,
  value="pptx"
)

Creates MemoryEvent:
{
  "project_id": "proj_123",
  "run_id": "run_latest",
  "event_type": "routing_decision_recorded",
  "fingerprint": "sha256(...)",
  "payload": "{\"user_id\": \"...\", \"decision_type\": \"output_format\", \"confidence\": 0.92, \"value\": \"pptx\"}",
  "created_at": "..."
}

Updates ProjectMemoryProfile:
  decision_outcomes.output_format = {
    "value": "pptx",
    "count": 1,
    "avg_confidence": 0.92,
    "last_outcome": "pptx",
    "last_updated_at": "..."
  }
```

---

### **Step 4: Plan Generation**

**Coordinator Planning Prompt**:

```
Composed of:
1. LLM Role (extended thinking enabled)
2. Engagement Context (EngagementMeta)
3. Assembled Context (TieredContextEngine.assemble_v2):
     - ObjectiveNow (16% of char budget)
     - NonNegotiables (22%)
     - WhatChanged (18%)
     - Evidence (34%)
       - Wiki pages (ranked by BM25)
       - Parsed docs (ranked by BM25)
       - MemoryEvent rows (30-day window)
       - MemoryItem rows (consent-filtered)
     - KnownFailures (10%)
4. Conversation digest (TieredCompactor, 4-tier)
5. User preferences

Token Budget: 
  - Total available per run: ANTHROPIC_MAX_TOKENS_PER_RUN (default 50000)
  - Coordinator planning: ANTHROPIC_COORDINATOR_PLAN_MAX_TOKENS (default 8192)
  - Compression if needed: 5-tier compression strategy

Storage:
  - Plan NOT stored in full
  - BUT: Plan structure stored as RunEvent
  - Referenced elements stored in DB tables
```

**Plan Storage** (as RunEvent):

```
event_type: "coordinator_plan_generated"

payload: {
  "schema_version": "run-events-v1",
  "event_type": "coordinator_plan_generated",
  "phase": "planning",
  "ts_ms": 1698567000000,
  "run_id": "run_abc123",
  "payload": {
    "coordinator_plan": {
      "planned_outputs": [
        {"output_type": "narrative", "rationale": "..."},
        {"output_type": "sop", "rationale": "..."},
        {"output_type": "raci", "rationale": "..."}
      ],
      "reasoning_excerpt": "[extended thinking excerpt if used]",
      "estimated_tokens": 45000,
      "confidence": 0.89
    }
  }
}

Stored in:
  - Table: run_events
  - run_id: indexed for retrieval
  - Queried via: RunEventService.load_resume_state()
```

---

### **Step 5: Execution & Generation**

**Sub-agent Prompts**:

#### a. **Per-Agent Prompt Assembly**

```
Each agent receives:
1. Agent-specific role prompt
2. Assembled context (TieredContextEngine):
     char_budget per agent: subagent_context_*_chars
3. Output specification
4. Tool availability
5. Previous outputs (for consistency)

Storage:
  - Context assembled at runtime (ephemeral)
  - Component sources in DB tables
  - Final output stored in file system

Example (Narrative Agent):
  System Prompt Size: ~2000 tokens
  User Prompt (context): ~3000 tokens
  Output Tokens Budget: ~4000 tokens
  Max Rounds: subagent_tool_max_rounds (default 5)
  Max Total Tokens: subagent_tool_max_tokens (default 4096)
```

#### b. **Artifact Generation & Storage**

```
Output Generated:
  - narrative.md (stored in runs/{run_id}/)
  - sop.md (stored in runs/{run_id}/)
  - raci.html → raci.xlsx (Excel workbook)
  - process_map.mmd (Mermaid syntax)
  - output.docx (Word document)
  - output.pptx (PowerPoint deck)
  - output.pdf (PDF export)

Storage Locations:
  1. File System: workspace/{project_id}/runs/{run_id}/*.{ext}
  2. Database: RunEvent with "artifact_summary" event
  3. Metadata: artifacts_typed.json (catalog of all artifacts)

artifacts_typed.json Structure:
[
  {
    "output_type": "narrative",
    "representation": "markdown",
    "content_type": "text/markdown",
    "body": "markdown_file:narrative.md"
  },
  {
    "output_type": "raci",
    "representation": "xlsx",
    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "body": "binary_file:raci.xlsx"
  }
]
```

---

### **Step 6: Quality Assurance & Approval**

**QA Prompts & Results**:

```
QA Gate Checks Performed:
1. Content QA (LLM critique)
2. Format QA (structure validation)
3. Visual QA (image/PDF rendering)
4. Guardrails (policy compliance)

Storage:
  - qa_report.json (results)
  - guardrail_report.json (policy violations)
  - RunEvent: qa_outcome event
  - RunEvent: guardrail_outcome event
```

**QA Report Storage** (in runs/{run_id}/qa_report.json):

```json
{
  "run_id": "run_abc123",
  "qa_gates": [
    {
      "gate_id": "content_qa",
      "status": "passed",
      "checks": [
        {"check": "content_completeness", "passed": true, "score": 0.95},
        {"check": "tone_consistency", "passed": true, "score": 0.88}
      ]
    },
    {
      "gate_id": "format_qa",
      "status": "passed",
      "checks": [
        {"check": "structure_valid", "passed": true}
      ]
    }
  ],
  "overall_status": "passed",
  "timestamp": "2026-10-30T15:45:00Z"
}
```

---

## COMPLETE ENGAGEMENT PROCESS FLOW

### **Phase 1: Engagement Setup (Day 1)**

```
Step 1: Create Project
  Input: Project name, client, type
  Creates:
    - projects row
    - workspace/{project_id}/ directory
    - CONTEXT.md (empty)
  
Step 2: Create EngagementMeta
  Input: Client, brief, scope, success measures, timeline, classification
  Creates:
    - engagement_meta row
    - engagement_brief cached in Redis
  Storage:
    Database: engagement_meta
    File Cache: Redis engagement_brief:{project_id}
  
Step 3: Initialize Conversation
  Input: User selects skill/topic
  Creates:
    - conversation row
    - conversation_state/{conversation_id}.json (initial state: "new")
  Storage:
    Database: conversation
    File: workspace/{project_id}/conversation_state/{cid}.json
```

---

### **Phase 2: Discovery Conversation (Days 1-3)**

```
Loop: User sends message → LLM responds → Questions answered

Iteration Example:
┌─────────────────────────────────────────────────────────┐
│ User Message:                                           │
│ "We need to streamline AP processing"                   │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Storage: conversation_messages (role="user")            │
│ Fields: conversation_id, content, source_type, created_at
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ System Prompt Assembly:                                 │
│ 1. Load EngagementMeta → engagement_brief              │
│ 2. Load ProjectMemoryProfile → discovery slots         │
│ 3. Load MemoryItem rows (consent-filtered)             │
│ 4. Load UserProjectPreference.context_lines            │
│ 5. Load wiki pages (BM25 ranked)                       │
│ 6. Load parsed_docs chunks (BM25 ranked)               │
│ 7. Load last 40 conversation messages (compacted)      │
│ 8. Estimate tokens: system + user + output budget      │
│ 9. Apply compression if over budget                    │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ LLM Call:                                               │
│ - Identify discovery answers in response               │
│ - Generate next discovery question                      │
│ - Suggest options for user                             │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Storage: conversation_messages (role="assistant")       │
│ Fields: content, metadata_json (tool_calls, citations)  │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Extract & Record Discovery Answers:                     │
│ record_discovery_answer(                               │
│   project_id, user_id,                                 │
│   slot_key="client",                                   │
│   value="Acme Corp"                                    │
│ )                                                      │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Storage Created:                                        │
│ 1. MemoryEvent (discovery_answer_recorded)             │
│    Fields: project_id, run_id, event_type,            │
│    fingerprint, payload (canonical JSON)               │
│                                                        │
│ 2. ProjectMemoryProfile Updated:                       │
│    summary_json.users[uid].aggregated_slots[key]       │
│                                                        │
│ 3. ConversationState Updated:                          │
│    slots["client"] = {"name": "Acme Corp"}            │
│    updated_at timestamp                               │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Retention:                                              │
│ - MemoryEvent: 30 days (MEMORY_EVENTS_RETENTION_DAYS)  │
│ - ConversationMessage: Indefinite                      │
│ - ConversationState: Indefinite                        │
└─────────────────────────────────────────────────────────┘

Until all discovery slots filled...
```

---

### **Phase 3: Plan Generation & Approval (Day 4)**

```
Step 1: Coordinator Planning
  Input: Complete discovery + user objectives
  Process:
    1. Assemble comprehensive context (TieredContextEngine.assemble_v2)
    2. Budget: ANTHROPIC_COORDINATOR_PLAN_MAX_TOKENS (8192)
    3. Enable extended thinking: ANTHROPIC_THINKING_BUDGET_TOKENS (8000)
    4. Generate structured plan with rationale
    5. Estimate total output types needed
  
  Storage:
    - RunEvent: coordinator_plan_generated
      event.payload.coordinator_plan = {
        "planned_outputs": [...],
        "reasoning_excerpt": "[thinking excerpt]",
        "confidence": 0.89
      }
  
Step 2: Build Decision Prompts
  Input: Planned outputs
  Generate prompts for user selections:
    - "Which format? (pptx, docx, sop, process_map, raci)"
    - "Which detail level? (executive, technical, detailed)"
    - "Timeline? (2 weeks, 4 weeks, 6 weeks)"
  
  Storage:
    - Database: conversation (in decision_prompts field)
    - User's selections stored as routing_decision MemoryEvent

Step 3: User Approval
  Input: User reviews and approves plan
  Process:
    1. User submits decision answers
    2. Hash plan: SHA256(plan_json)
    3. User confirms hash match
  
  Storage:
    - Run created: status="plan_ready"
    - Selections as routing_decision MemoryEvent
    - Plan confirmed: run.plan_payload (JSON)
    - Database: run row with plan metadata
```

---

### **Phase 4: Run Execution (Days 5-7)**

```
Step 1: Create Run
  Input: Approved plan
  Creates:
    - runs row (status="plan_ready")
    - runs/{project_id}/runs/{run_id}/ directory
    - manifest.json: {"run_id", "project_id", "status", "output_types", "created_at"}
  
  Storage:
    Database: runs, run_events
    File: workspace/{project_id}/runs/{run_id}/manifest.json

Step 2: Execution Enqueue
  Event Created:
    RunEvent {
      event_type: "execution_enqueued",
      payload: {"status": "execution_enqueued", "timestamp": "..."}
    }

Step 3: Context Assembly for Each Sub-agent
  For each output type (narrative, sop, raci, etc.):
    1. Load TieredContextEngine.assemble_v2(project_id, char_cap)
    2. Budget context per agent: subagent_context_offered_chars_{agent}
    3. Send to sub-agent with tool availability
    4. Track tokens: input, output, cache_read, cache_creation
  
  Storage:
    - In-memory: _active_usage (ContextVar)
    - Live polling: _live_usage_registry[run_id]
    - Recorded: run.tokens_input, tokens_output, etc.

Step 4: Sub-agent Execution Loop
  For each sub-agent (narrative_agent, sop_agent, raci_agent, etc.):
    repeat up to subagent_tool_max_rounds:
      1. Send current state + tools
      2. Agent calls tools (retrieve_context, web_search, etc.)
      3. Record tool calls: agent_tool_round RunEvent
      4. LLM generates/refines output
      5. Check if quality meets threshold
    
    Storage:
      RunEvent: agent_tool_round
        payload.agent_id, payload.round, payload.tool_calls
      
      Sub-agent state: stored in checkpoint DB
        .checkpoints/run_graph.sqlite (LangGraph)

Step 5: QA & Guardrails
  1. Visual QA: Render PDF, check layout
  2. Content QA: LLM critique of completeness
  3. Guardrails: Policy compliance checks
  4. Address issues: Regenerate if needed
  
  Storage:
    qa_report.json: {gates, checks, status, timestamp}
    guardrail_report.json: {violations, severity, remediation}
    RunEvent: qa_outcome, guardrail_outcome

Step 6: Artifact Finalization
  1. Render all requested formats
  2. Write to filesystem
  3. Create artifacts_typed.json catalog
  4. Record render_status.json
  
  Storage:
    File: workspace/{project_id}/runs/{run_id}/
      ├── narrative.md
      ├── sop.md
      ├── raci.xlsx
      ├── output.pptx
      ├── output.docx
      ├── artifacts_typed.json
      └── render_status.json

Step 7: Run Completion
  Event Created:
    RunEvent {
      event_type: "execution_completed",
      payload: {"status": "done", "artifacts_count": 5}
    }
  
  Database Update:
    runs.status = "review_ready"
    runs.tokens_input, tokens_output (final counts)
    runs.cost_usd (calculated from tokens)
```

---

### **Phase 5: Review & Delivery (Day 8)**

```
Step 1: User Reviews Outputs
  Downloads: narrative.md, sop.md, output.pptx, etc.
  Reviews quality and completeness
  
  Storage: Users view files from workspace/{project_id}/runs/{run_id}/

Step 2: Final Approval
  User clicks "Approve & Finalize"
  
  Storage:
    runs.status = "finalized"
    RunEvent: execution_finalized

Step 3: Memory Learning
  Update ProjectMemoryProfile based on outcomes:
    - successful_outputs: increment counters
    - user_feedback: improve preferences
    - decision_patterns: identify preferences
  
  Storage:
    ProjectMemoryProfile.users[uid].learning_signals updated
    UserProjectPreference.preferences_json updated

Step 4: Artifacts Archive
  Files retained in workspace for future reference
  
  Retention:
    - workspace files: indefinite (user manages)
    - database records: indefinite (audit trail)
    - memory events: 30 days (auto-pruned)
```

---

## DATA STORAGE FOR PROCESS & LLM

### **System Prompts (Ephemeral, Reconstructed Per Request)**

```
Role Definition (fixed):
  "You are an expert business process consultant..."
  
Engagement Context (from EngagementMeta):
  "[EngagementBrief]\nClient: ...\nScope: ...\n"
  
Discovery State (from ProjectMemoryProfile):
  "Known client info: Acme Corp\nObjective: Reduce AP time by 50%\n"
  
Long-term Items (from MemoryItem, consent-filtered):
  "preference:output_style=executive_summary\n
   constraint:budget_max=$500k\n
   fact:org_size=500_employees\n"
  
User Preferences (from UserProjectPreference):
  "User notes: Prefers detailed ROI analysis, focus on financial metrics\n"
  
Conversation History (compacted via TieredCompactor):
  "[Last N messages, truncated messages, auto-summaries, compressed]\n"
  
Wiki & Source Docs (BM25-ranked):
  "[Top 5-10 most relevant chunks with source citations]\n"

Total System Prompt Size: ~2-4K tokens
Storage: NOT persisted (built fresh each request)
```

### **User Prompts (Stored in conversation_messages)**

```
Message 1: "We need to streamline our AP process"
Storage: conversation_messages.content
Metadata: source_type="chat", source_freshness_at=now

Message 2: "Annual volume is 50K invoices, 3 locations"
Storage: conversation_messages.content
Extracted Discovery: win_themes ["Reduce manual work", "Reduce errors"]

Message 3: "Please generate SOP and RACI"
Storage: conversation_messages.content
Extracted Routing: output_types ["sop", "raci"]
```

### **Generated Context (Component-Based Storage)**

```
Component 1: Engagement Brief
  Storage: EngagementMeta table + Redis cache
  
Component 2: Discovery Slots
  Storage: ProjectMemoryProfile.aggregated_slots
  
Component 3: Memory Events
  Storage: MemoryEvent table (30-day window)
  
Component 4: Memory Items
  Storage: MemoryItem table + consent checks
  
Component 5: Wiki Pages
  Storage: workspace/{project_id}/wiki/ + Redis cache
  
Component 6: Parsed Documents
  Storage: workspace/{project_id}/parsed_docs/*.json
  
Component 7: Conversation History
  Storage: conversation_messages table (compacted)
  
Component 8: User Preferences
  Storage: UserProjectPreference + context_lines
```

### **Output/Generation Storage**

```
Raw LLM Output:
  Generated by sub-agents, stored in memory
  NOT persisted directly
  
Rendered Artifacts:
  - narrative.md → workspace/.../narrative.md
  - sop.md → workspace/.../sop.md
  - raci.xlsx → workspace/.../raci.xlsx
  - output.pptx → workspace/.../output.pptx
  - output.docx → workspace/.../output.docx
  - output.pdf → workspace/.../output.pdf
  
Metadata:
  - artifacts_typed.json (catalog)
  - render_status.json (success/degraded)
  - qa_report.json (quality scores)
  - guardrail_report.json (policy violations)
```

---

## CONFIGURATION REFERENCE

### **Database Configuration**

```bash
# SQLite (default, single-process)
DATABASE_URL=sqlite:///./advise_workbench.db

# PostgreSQL (multi-process, production)
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/advise_workbench
DATABASE_POOL_SIZE=20              # Connection pool size
DATABASE_MAX_OVERFLOW=20           # Max overflow connections
DATABASE_POOL_TIMEOUT=30           # Seconds to wait for connection
DATABASE_POOL_RECYCLE=300          # Recycle connections after N seconds
```

### **Memory Configuration**

```bash
MEMORY_COMPACTION_V1_ENABLED=true
MEMORY_V2_RETRIEVAL_ENABLED=true
MEMORY_COMPACTION_CHAR_CAP=32000   # Character budget for context

MEMORY_RESPECT_CONSENT_IN_CONTEXT=true    # Check consent_state field
MEMORY_ENFORCE_CONSENT_LEDGER=false       # Require ConsentLedger for principals

MEMORY_EVENTS_RETENTION_DAYS=30    # Prune MemoryEvent after N days
MEMORY_BATCH_CREATE_ENABLED=true
```

### **Token & Budget Configuration**

```bash
ANTHROPIC_MAX_TOKENS_PER_RUN=50000                    # Per-run budget (~$2-3)
ANTHROPIC_THINKING_BUDGET_TOKENS=8000                 # Extended thinking budget
ANTHROPIC_COORDINATOR_PLAN_MAX_TOKENS=8192           # Planner max output
SUBAGENT_TOOL_MAX_TOKENS=4096                         # Per sub-agent call
SUBAGENT_TOOL_MAX_ROUNDS=5                           # Max refinement rounds
```

### **Cache Configuration**

```bash
REDIS_URL=redis://localhost:6379/0
CACHE_ALLOW_MEMORY_FALLBACK=true   # true = use in-memory if Redis down
                                    # false = fail-fast in multi-replica

# File cache invalidation (mtime-based, automatic)
# TTL defaults: 3600 sec (1 hour) for most keys
```

### **Workspace & Storage Configuration**

```bash
WORKSPACE_ROOT=./workspace          # Base directory for all projects
# Creates: {WORKSPACE_ROOT}/{project_id}/source_docs, parsed_docs, runs, wiki, etc.
```

### **Observability Configuration**

```bash
OBSERVABILITY_SNAPSHOT_PATH=/tmp/metrics.json
LANGFUSE_ENABLED=false
OPENOBSERVE_ENABLED=false
```

---

## SUMMARY TABLE: Memory Capture → Storage → Retention

| Memory Type | What's Captured | Storage Location | Table/File | Retention |
|-------------|-----------------|-----------------|-----------|-----------|
| **User Messages** | Chat text, metadata | Database | conversation_messages | Indefinite |
| **Discovery Answers** | Slot values (client, outcome, etc.) | DB + File | MemoryEvent + ProjectMemoryProfile | Event: 30 days; Profile: Indefinite |
| **Routing Decisions** | User choices (format, style, etc.) | DB + File | MemoryEvent + ProjectMemoryProfile | Event: 30 days; Profile: Indefinite |
| **Engagement Context** | Brief, scope, success measures | DB + Cache | EngagementMeta + Redis | Configurable per engagement |
| **Conversation State** | FSM state, pending questions | File | workspace/.../conversation_state/*.json | Indefinite |
| **Memory Items** | Knowledge (preference, constraint, fact) | Database | MemoryItem | Indefinite (soft-delete) |
| **User Preferences** | Context lines, learning signals | Database | UserProjectPreference | Indefinite |
| **Run Events** | Execution milestones | Database | RunEvent | Indefinite (audit trail) |
| **Assembled Context** | Components (wiki, docs, items) | ephemeral | Reconstructed per request | N/A |
| **System Prompts** | Role, context, instructions | ephemeral | Reconstructed per request | N/A |
| **Generated Artifacts** | Narrative, SOP, RACI, etc. | File | workspace/.../runs/{run_id}/ | Indefinite |
| **QA Reports** | Quality assessment results | File | workspace/.../qa_report.json | Indefinite |
| **Metrics** | Counters, latencies, gauges | In-memory + File | _COUNTERS, .metrics/metrics.json | In-memory (session); File (snapshot) |

---

## CONCLUSION

The engagement system implements a **multi-layered memory architecture**:

1. **Transactional Layer** (Database): Primary persistence with ACID guarantees
2. **Event Layer** (MemoryEvent): Immutable audit trail with 30-day retention
3. **State Layer** (ProjectMemoryProfile + ConversationState): Aggregated & cached
4. **Component Layer** (MemoryItem, UserProjectPreference): Explicit knowledge
5. **Ephemeral Layer** (System prompts): Reconstructed per request
6. **File Layer** (Workspace): Artifacts and source documents
7. **Cache Layer** (Redis + In-Memory): Performance optimization
8. **Checkpoint Layer** (LangGraph SQLite): Execution recovery

Every piece of data has a defined location, retention policy, and retrieval path, enabling:
- **Full auditability**: Every action is logged
- **Privacy compliance**: Consent-aware filtering
- **Performance**: Tiered storage with caching
- **Reliability**: Checkpoint-based recovery
- **Observability**: Comprehensive metrics
