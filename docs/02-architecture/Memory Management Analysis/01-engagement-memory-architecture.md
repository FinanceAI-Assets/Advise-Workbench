# Memory Architecture of Engagement Section

## Executive Summary

The Advise Workbench engagement section implements a multi-layered memory architecture that integrates engagement metadata, conversation state, memory events, and user preferences into a cohesive knowledge system. The architecture supports background processing of conversations, consent-aware memory retrieval, and event-driven state management.

---

## 1. Engagement Metadata Layer

### **EngagementMeta Model** (`src/core/db/models.py` lines 66-97)

The `EngagementMeta` table is a side-car metadata table attached to each `Project`. It captures engagement-specific information that would be too project-specific to fit in the base `Project` model.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | String(64) | Primary key |
| `project_id` | Foreign Key | Links to Project (1:1 relationship) |
| `code` | String(32) | Engagement identifier (e.g., "ENG-001") |
| `type` | String(64) | Engagement classification (e.g., "SOW", "Project") |
| `stage` | String(32) | Engagement progress stage (e.g., "Discovery", "Execution") |
| `progress` | Integer | Progress percentage (0-100) |
| `client_org` | String(255) | Client organization name |
| `brief` | Text | Executive summary |
| `sponsor_objective` | Text | Primary objective for sponsor |
| `scope` | Text | What's included/excluded |
| `success_measures` | Text | Success criteria (semicolon/comma-separated) |
| `start_date` | String(32) | ISO date or custom format |
| `target_close` | String(32) | Target completion date |
| `classification` | String(64) | Data/content classification |
| `retention_days` | Integer | Data retention policy |
| `status` | String(16) | Current status (active\|closed\|archived) |
| `next_task` | Text | Next action item |
| `due_date` | String(32) | Next task deadline |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last modification timestamp |

**Database Index:**
```sql
CREATE INDEX ix_engagement_meta_project_id ON engagement_meta(project_id);
```

### **Integration Points**

#### 1. Discovery Slot Pre-filling (`_engagement_context.py`)

```python
def engagement_discovery(db: Session, project_id: str) -> dict:
    """Extract discovery slots from engagement brief."""
    # Returns: {"client": {"name": "..."}, "outcome": {"primary": "..."}, "win_themes": [...]}
```

This function maps `EngagementMeta` fields to discovery slots so the conversation doesn't re-ask for information already captured:
- `client_org` → `discovery.client.name`
- `sponsor_objective` or `brief` → `discovery.outcome.primary`
- `success_measures` (split) → `discovery.win_themes` (up to 3)

#### 2. Context Provision (`_engagement_context.py`)

```python
def engagement_brief_text(db: Session, project_id: str) -> str:
    """Format engagement brief as context block for LLM."""
    # Returns formatted block like:
    # [EngagementBrief]
    # Engagement: ProjectName (ENG-001)
    # Client: Acme Corp
    # Brief: ...
    # Success measures: ...
```

This provides LLM-readable context during conversation, ensuring responses are grounded in the engagement's declared objectives.

---

## 2. Conversation Execution Layer

### **Conversation Models** (`src/core/db/models.py`)

#### **Conversation** (lines 326-336)
Represents a conversation session or thread.

```python
class Conversation:
    id: String(64)  # Primary key
    project_id: String(64)  # FK to projects
    user_id: String(64)  # FK to users
    title: String(255)  # e.g., "Creative Studio"
    skill_id: String(64) | None  # Associated skill context
    created_at: DateTime
    updated_at: DateTime
```

**Indexes:**
- `project_id` (lookup by project)
- `user_id` (lookup by user)

#### **ConversationMessage** (lines 338-354)
Individual messages within a conversation.

```python
class ConversationMessage:
    id: Integer  # Primary key (auto-increment)
    conversation_id: String(64)  # FK to conversations
    role: String(16)  # "user" | "assistant"
    content: String(Text)  # Message body
    metadata_json: String(Text)  # {"tool_calls": [...], "citations": [...]}
    source_type: String(32) | None  # e.g., "wiki", "discovery"
    source_freshness_at: DateTime | None  # When source was last updated
    created_at: DateTime
```

**Indexes:**
- `conversation_id` (lookup messages in conversation)
- `created_at` (chronological ordering)

#### **ConversationTurn** (lines 356-371)
For **background/asynchronous** message processing.

```python
class ConversationTurn:
    id: String(64)  # Primary key: t_{uuid.hex[:16]}
    project_id: String(64)  # FK
    user_id: String(64)  # FK
    status: String(16)  # "running" | "done" | "failed"
    phase: String(32)  # Current phase
    status_code: Integer  # HTTP status (200, 400, 500)
    response_json: String(Text)  # Full response payload
    created_at: DateTime
    updated_at: DateTime
```

**Indexes:**
- `project_id` + `user_id` (lookup user's turns)

---

### **Background Turn Processing** (`src/app/api/projects/conversation_turns.py`)

The application supports **long-running conversation messages** via background workers.

#### **Flow**

```
Client: POST /projects/{pid}/conversation/messages?background=true
         → Returns immediately: {"turn_id": "t_abc123", "status": "running", "phase": "queued"}

Client: Poll GET /projects/{pid}/conversation/turns/{turn_id}
         → While status != "done":
           {"status": "running", "phase": "understand", "phase_label": "Working out what you have told me so far"}
         → When done:
           {"status": "done", "response": {"decisions": [...], "messages": [...]}}
```

#### **Phase Progression**

```
queued → receive → understand → route → respond
```

User-friendly labels (PHASE_LABELS):
- `queued`: "Starting"
- `receive`: "Reading your message"
- `understand`: "Working out what you have told me so far"
- `route`: "Checking the project knowledge and deciding the next step"
- `respond`: "Writing the reply"

#### **Implementation Details**

**Workers:**
```python
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="conversation-turn")
```

**Live Phase Tracking (in-memory):**
```python
_LIVE_PHASE: dict[str, str] = {}  # turn_id → phase_name
```

This in-memory dict tracks phases on the current API process. When polling reaches a different API process, it falls back to the phase stored in the database at work start.

**Stale Detection:**
- Turns running > 15 minutes (`_STALE_AFTER = timedelta(minutes=15)`) are marked failed with status 503
- Allows recovery if worker thread crashes or server restarts

**Transaction Model:**
- Each worker gets its own `SessionLocal()` instance
- ConversationTurn created with status=running in main request
- Worker updates the same row with final status, phase, and response_json
- Progress callback updates `_LIVE_PHASE` in-memory for polling

---

## 3. Memory Persistence Layer

### **Memory Models**

#### **MemoryEvent** (`src/core/db/models.py` lines 295-305)

Event records from conversation and runs, used for profile aggregation.

```python
class MemoryEvent:
    id: Integer  # Primary key (auto-increment)
    project_id: String(64)  # FK (indexed)
    run_id: String(64)  # FK (indexed) - ties to latest run
    event_type: String(64)  # e.g., "discovery_answer_recorded", "routing_decision_recorded"
    fingerprint: String(64)  # SHA256(project_id|run_id|event_type|payload) for deduplication
    payload: String(Text)  # JSON event data
    created_at: DateTime  # (indexed)
```

**Indexes:**
- `project_id`
- `run_id`
- `fingerprint` (deduplication lookup)
- `created_at` (retention cleanup)

**Retention Policy:**
- Default: `MEMORY_EVENTS_RETENTION_DAYS = 30`
- Pruned automatically via background job
- Counter: `memory_events_pruned_total`

#### **ProjectMemoryProfile** (`src/core/db/models.py` lines 307-313)

Aggregated summary of all memory for a project.

```python
class ProjectMemoryProfile:
    project_id: String(64)  # Primary key, FK
    summary_json: String(Text)  # Aggregated profile structure
    updated_at: DateTime
```

**Structure of `summary_json`:**
```json
{
  "users": {
    "user-id-1": {
      "aggregated_slots": {
        "client": {"name": "Acme Corp"},
        "outcome": {"primary": "Streamline processes"},
        "win_themes": ["Efficiency", "Cost reduction"]
      },
      "decision_outcomes": {
        "output_format": "pptx",
        "doc_style": "executive"
      },
      "updated_at": "2026-10-28T14:30:00Z"
    }
  }
}
```

#### **MemoryItem** (`src/core/db/models.py` lines 373-392)

User-curated knowledge items stored in project memory.

```python
class MemoryItem:
    id: String(64)  # Primary key
    project_id: String(64)  # FK (indexed)
    memory_type: String(32)  # "preference" | "constraint" | "decision" | "fact"
    key: String(128)  # Knowledge key
    value: String(Text)  # Knowledge value
    confidence: String(16)  # "low" | "medium" | "high"
    source: String(64)  # "chat" | "document" | "system"
    consent_state: String(16)  # "allowed" | "blocked" | etc (indexed)
    principal_id: String(128) | None  # DPDP principal for consent checks (indexed)
    is_archived: Boolean  # Soft delete flag
    created_at: DateTime  # (indexed)
    updated_at: DateTime
```

**Unique Constraint:**
```sql
UNIQUE(project_id, memory_type, key)
```

#### **UserProjectPreference** (`src/core/db/models.py` lines 315-324)

Per-user, per-project personalization.

```python
class UserProjectPreference:
    user_id: String(64)  # Primary key (FK)
    project_id: String(64)  # Primary key (FK)
    preferences_json: String(Text)  # {"context_lines": ["...", "..."], ...}
    updated_at: DateTime
```

---

### **Memory Event Recording** (`src/memory/long_term/memory_event_service.py`)

#### **Discovery Answer Recording**

```python
def record_discovery_answer(
    session: Session,
    *,
    project_id: str,
    user_id: str,
    slot_key: str,
    value: Any,
) -> None:
    """Record a discovery slot answer and update ProjectMemoryProfile."""
```

**Steps:**
1. Load `ProjectMemoryProfile` with row-level lock (`SELECT FOR UPDATE`)
2. Normalize user block: `summary.users[user_id]` → ensure dicts exist
3. Update `aggregated_slots[slot_key] = value`
4. Save profile back to DB
5. Append deduplication-safe event: `MemoryEvent(event_type="discovery_answer_recorded", ...)`

**Deduplication:**
```python
fingerprint = sha256(f"{project_id}|{run_id}|event_type|{canonical_json}".encode()).hexdigest()
# Skip if fingerprint already exists
```

**Concurrency Safety:**
- Row-level locks on `ProjectMemoryProfile` (PostgreSQL `SELECT FOR UPDATE`)
- Fingerprint-based idempotency
- Prevents lost-update race when multiple coordinators run in parallel

#### **Routing Decision Recording**

```python
def record_routing_decision(
    session: Session,
    *,
    project_id: str,
    user_id: str,
    decision_type: str,  # e.g., "output_format", "doc_style"
    confidence: float,
    value: Any,
) -> None:
    """Record routing decision and update profile."""
```

Similar pattern to `record_discovery_answer`, but populates `decision_outcomes[decision_type]`.

#### **Profile Aggregation**

```python
def get_aggregated_profile(
    session: Session,
    *,
    project_id: str,
) -> dict[str, Any]:
    """Load ProjectMemoryProfile summary."""
```

Returns the current aggregated state for use in context assembly.

---

## 4. Context Assembly Pipeline

### **Memory Compaction (v2)** (`src/memory/short_term/context_compaction.py`)

The coordinator assembles context for the LLM from multiple sources:

```
Input Sources:
├─ MemoryEvent rows (last 30 days, respecting retention)
├─ ProjectMemoryProfile (aggregated discovery & decisions)
├─ MemoryItem rows (if MEMORY_V2_RETRIEVAL_ENABLED=true)
├─ EngagementMeta (via engagement_brief_text)
├─ UserProjectPreference (context_lines)
└─ ConversationHistory (recent messages)

     ↓ (apply consent filtering, character budgeting)

Output:
└─ assembled_context (up to MEMORY_COMPACTION_CHAR_CAP = 32000 chars)
```

### **Consent-Aware Filtering** (`src/memory/long_term/memory_consent.py`)

```python
def memory_item_allowed_for_use(
    session: Session,
    project_id: str,
    item: MemoryItem,
    *,
    respect_consent: bool,
    enforce_consent_ledger: bool = False,
) -> tuple[bool, str]:
    """Check if MemoryItem can be used in context."""
```

**Checks (in order):**
1. **Consent State**: If `item.consent_state` not in ("allowed", ""), skip if `respect_consent=True`
2. **Consent Ledger**: If `enforce_consent_ledger=True` and `item.principal_id` set:
   - Query `ConsentLedger` for `(project_id, principal_id)`
   - Require latest row with `granted=True`
   - Skip if not found or revoked

**Returns:**
- `(True, "")` — Use the item
- `(False, "consent_field")` — Blocked by consent_state
- `(False, "consent_ledger")` — Blocked by ledger check

### **Long-Term Items Merge** (`src/memory/long_term/memory_context.py`)

```python
def merge_long_term_items_into_profile(
    profile_payload: dict[str, Any],
    long_term_rows: list[Any],
    *,
    respect_consent: bool,
    session: Session | None = None,
    project_id: str | None = None,
    enforce_consent_ledger: bool = False,
) -> tuple[int, int, int]:
    """Merge MemoryItem rows into coordinator profile."""
```

**Output Format:**
```json
{
  "long_term_items": [
    "preference:style=detailed",
    "constraint:budget=$100k",
    "decision:format=pptx",
    "fact:org_size=500"
  ]
}
```

Returns counts: `(injected, consent_skipped, ledger_skipped)`

---

## 5. Consent & Data Protection

### **ConsentLedger** (`src/core/db/models.py` lines 266-280)

Tracks data subject consent decisions.

```python
class ConsentLedger:
    id: String(64)
    project_id: String(64)  # FK (indexed)
    principal_id: String(128)  # Data subject ID (indexed)
    purpose: String(255)  # e.g., "use_in_llm_context"
    granted: Boolean  # True = allowed, False = denied
    revoked_at: DateTime | None
    granted_by: String(255)  # Who approved
    run_id: String(64) | None  # Audit link
    created_at: DateTime
```

**Index:**
```sql
CREATE INDEX ix_consent_ledger_project_principal ON consent_ledger(project_id, principal_id);
```

### **Configuration**

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEMORY_RESPECT_CONSENT_IN_CONTEXT` | `true` | Skip items with `consent_state` not in (allowed, "") |
| `MEMORY_ENFORCE_CONSENT_LEDGER` | `false` | Require ConsentLedger row for `principal_id` holders |

When both are enabled:
1. Filter by `consent_state` field
2. Additionally check `ConsentLedger` for any items with `principal_id` set
3. Both checks must pass

---

## 6. Conversation State Persistence

### **ConversationState** (`src/memory/short_term/conversation_state.py`)

Persistent state file per conversation: `{workspace}/{project_id}/conversation_state/{conversation_id}.json`

```json
{
  "state": "discovery",
  "slots": {
    "client": {"name": "Acme Corp"},
    "outcome": {"primary": "Streamline ops"}
  },
  "deliverable": "sop",
  "last_router": "output_format_router",
  "pending_questions": ["success_measures"],
  "history_summary": "User described ops pain points...",
  "updated_at": "2026-10-28T14:30:00Z"
}
```

**State Machine:**
```
new → exploring → discovery → storyline_building
    → slide_negotiation → structure_agreed → ready_to_plan
    → plan_proposed → confirming → done
```

**Functions:**
- `load_state(conversation_id, project_workspace)` → dict or {}
- `save_state(state, conversation_id, project_workspace)` → None
- `stamp_router(state, router_name)` → None (update last_router field)

---

## 7. Configuration & Retention Policies

### **Memory Configuration** (`.env`)

```bash
# Memory compaction and retrieval
MEMORY_COMPACTION_V1_ENABLED=true               # Use assemble_v2
MEMORY_V2_RETRIEVAL_ENABLED=true                # Load MemoryItem rows
MEMORY_COMPACTION_CHAR_CAP=32000                # Budget in chars

# Consent and DPDP
MEMORY_RESPECT_CONSENT_IN_CONTEXT=true          # Check consent_state
MEMORY_ENFORCE_CONSENT_LEDGER=false             # Require ConsentLedger row
MEMORY_EVENTS_RETENTION_DAYS=30                 # Prune old events

# Batch operations
MEMORY_BATCH_CREATE_ENABLED=true                # Enable /api/memory/{pid}/batch
```

### **Startup Validation**

If `MEMORY_COMPACTION_V1_ENABLED=true` but `MEMORY_V2_RETRIEVAL_ENABLED=false`:
- API logs warning: `advise_workbench.config`
- Memory events and `ProjectMemoryProfile` still apply
- But MemoryItem rows are not loaded

---

## 8. Event Streaming & Audit Trail

### **Run Events** (`src/core/db/models.py` lines 182-197)

```python
class RunEvent:
    id: Integer  # Primary key (auto-increment)
    run_id: String(64)  # FK (indexed)
    event_type: String(64)  # Event type
    payload: String(Text)  # JSON payload
    created_at: DateTime  # (indexed)
```

**Canonical Envelope (v1):**
```json
{
  "schema_version": "run-events-v1",
  "event_type": "discovery_answer_recorded",
  "phase": "conversation",
  "ts_ms": 1698567000000,
  "run_id": "run-123",
  "payload": {
    "user_id": "user-456",
    "slot_key": "client",
    "value": "Acme Corp"
  }
}
```

**Strict Contract:**
- Enforced when `EVENT_CONTRACT_STRICT=true`
- Legacy payload flattening disabled
- All events must conform to canonical envelope

---

## 9. Data Flow Diagram

```
Engagement Creation
    ↓
Create Project
Create EngagementMeta (client, brief, scope, success_measures, etc.)
Create Membership
    ↓
    ├─ User starts Conversation
    │   └─ Conversation created
    │
    ├─ User sends ConversationMessage
    │   ├─ Load engagement_discovery() → pre-fill slots
    │   ├─ Load engagement_brief_text() → context
    │   ├─ Call LLM with assembled_context
    │   │   ├─ MemoryEvent rows (30-day retention)
    │   │   ├─ ProjectMemoryProfile.summary_json
    │   │   ├─ MemoryItem rows (consent-aware)
    │   │   ├─ UserProjectPreference.context_lines
    │   │   └─ ConversationHistory
    │   │
    │   ├─ Process response:
    │   │   ├─ record_discovery_answer() → MemoryEvent + ProjectMemoryProfile
    │   │   ├─ record_routing_decision() → MemoryEvent + ProjectMemoryProfile
    │   │   └─ save_state() → ConversationState JSON
    │   │
    │   └─ Return to client
    │
    └─ (Optional background mode)
        └─ ConversationTurn created
            └─ Worker thread handles message
                └─ Poll GET /turns/{turn_id} for progress
```

---

## 10. API Endpoints Reference

### **Memory API** (`/api/memory/{pid}`)

```
GET  /api/memory/{pid}                          # List memory items
POST /api/memory/{pid}                          # Create memory item
PUT  /api/memory/{pid}/{item_id}                # Update item
DELETE /api/memory/{pid}/{item_id}              # Delete item (archive)
POST /api/memory/{pid}/batch                    # Batch create (when enabled)

GET  /api/projects/{pid}/me/preferences         # Get user preferences
PATCH /api/projects/{pid}/me/preferences        # Update preferences

GET  /api/projects/{pid}/admin/team-personalization  # List all (Owner only)
```

### **Conversation API** (`/api/projects/{pid}/conversation`)

```
GET  /conversation                              # Get metadata
POST /messages                                  # Send message (with ?background=true)
POST /decisions                                 # Submit decisions
POST /confirm                                   # Confirm plan
DELETE /                                        # Clear history

GET  /turns/{turn_id}                           # Poll background turn
```

---

## 11. Key Integration Points

### **For New Features**

1. **Store engagement context**: Add fields to `EngagementMeta`
2. **Use in discovery**: Map new fields via `engagement_discovery()`
3. **Surface to LLM**: Include in `engagement_brief_text()`
4. **Remember decisions**: Call `record_discovery_answer()` or `record_routing_decision()`
5. **Consent handling**: Check `MEMORY_RESPECT_CONSENT_IN_CONTEXT` and `MEMORY_ENFORCE_CONSENT_LEDGER`

### **For Memory-Aware Features**

1. **Create MemoryItem** in `/api/memory/{pid}` with type, key, value
2. **Optional principal_id** if DPDP consent tracking needed
3. **Optional consent_state** if consent field blocking needed
4. **Add context_lines** to `UserProjectPreference` for per-user customization
5. **Call `get_aggregated_profile()`** to load current state for personalization

---

## 12. Performance Considerations

### **Concurrency**

- Row-level locks on `ProjectMemoryProfile` prevent lost updates
- Fingerprint-based event deduplication prevents duplicates
- ThreadPoolExecutor (8 workers) limits concurrent background turns

### **Caching**

- `_LIVE_PHASE` in-memory dict avoids DB reads during polling
- Stale phase detection (15 min) recovers from worker failures
- Redis-based cache fallback when `REDIS_URL` set

### **Retention**

- MemoryEvent: 30-day default (configurable)
- ConversationTurn: Kept indefinitely (audit trail)
- Pruning runs via background job triggered at startup

---

## Summary

The engagement memory architecture in Advise Workbench is a sophisticated system that:

1. **Captures engagement context** via `EngagementMeta` to inform all downstream work
2. **Manages conversations** with background processing for long-running replies
3. **Records decisions** as immutable events with fingerprint-based deduplication
4. **Aggregates knowledge** in `ProjectMemoryProfile` for LLM context
5. **Stores explicit memory** in `MemoryItem` with consent and DPDP support
6. **Personalizes** per user with `UserProjectPreference` and per-project settings
7. **Maintains audit trail** via `MemoryEvent` with configurable retention
8. **Ensures concurrency safety** with row-level locks and transactional guarantees

This design enables rich, context-aware conversations that improve over time and respect user privacy constraints.
