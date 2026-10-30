# Conversation Memory Management Architecture

## Overview

The application uses a **layered approach** combining database persistence, filesystem-based short-term state, and in-memory tracking for background execution. This document describes how conversations, memory, and state management work together.

---

## 1. Database Layer (Core Persistence)

### Entity Relationships

```
Conversation (1)
    ├── ConversationMessage (many) — individual messages
    ├── ConversationTurn (many) — background task tracking
    └── Related to Project & User (FK relationships)
```

### Conversation Model

**Location**: `src/core/db/models.py:326`

Metadata container for a conversation thread.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | String(64) | Primary key, unique conversation identifier |
| `project_id` | FK → Project | Links to project context |
| `user_id` | FK → User | Links to message author |
| `title` | String(255) | Conversation title (default: "Creative Studio") |
| `skill_id` | String(64) | Optional linked skill |
| `created_at` | DateTime | Timestamp of conversation creation |
| `updated_at` | DateTime | Last update timestamp |

### ConversationMessage Model

**Location**: `src/core/db/models.py:338`

Individual messages within a conversation.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | Integer | Auto-increment primary key |
| `conversation_id` | FK → Conversation | Links to conversation (indexed) |
| `role` | String(16) | "user" or "assistant" |
| `content` | Text | Message body |
| `metadata_json` | Text | Optional message metadata (default: "{}") |
| `source_type` | String(32) | Knowledge source type (wiki, run_output, etc.) (indexed) |
| `source_freshness_at` | DateTime | When source was last refreshed (indexed) |
| `created_at` | DateTime | Message timestamp (indexed) |

**Indexes**: 
- `conversation_id` — fast message retrieval per conversation
- `source_type` — track knowledge source freshness
- `created_at` — chronological ordering

### ConversationTurn Model

**Location**: `src/core/db/models.py:356`

Tracks background execution of async message processing. Enables long-running LLM responses without blocking HTTP requests.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | String(64) | Primary key (format: `t_<uuid_hex[:16]>`) |
| `project_id` | FK → Project | Project context (indexed) |
| `user_id` | FK → User | User who initiated (indexed) |
| `status` | String(16) | "running" \| "done" \| "failed" (default: "running") |
| `phase` | String(32) | Current execution phase (default: "queued") |
| `status_code` | Integer | HTTP status code (default: 200) |
| `response_json` | Text | Result payload (default: "{}") |
| `created_at` | DateTime | Turn start time |
| `updated_at` | DateTime | Last status update |

**Indexes**: 
- `project_id` — find turns per project
- `user_id` — find turns per user

---

## 2. Short-Term Memory (Filesystem-Based State Machine)

### Storage Location

```
workspace/{project_id}/conversation_state/{conversation_id}.json
```

Each conversation has its own JSON file on disk containing the active conversation state.

### ConversationState Model

**Location**: `src/memory/short_term/conversation_state.py:29`

Serialized state machine for a conversation. Drives the conversation flow through well-defined states.

```python
@dataclass
class ConversationState:
    schema_version: int              # Schema versioning for migrations
    state: str                       # Current FSM state (see state diagram)
    slots: dict[str, Any]           # Discovery answers collected
    deliverable: dict[str, Any]     # Current work item metadata
    last_router: dict[str, Any]     # Last routing decision metadata
    pending_questions: list[str]    # Questions still to be asked
    surfaced_wiki_refs: list[str]   # Knowledge base references shown
    history_summary: str            # Compact conversation summary
```

### State Machine Diagram

```
new
  ↓
exploring ← (initial discovery, vague intent detected)
  ↓
discovery ← (collecting required information via questions)
  ├─→ storyline_building ← (proposal identified, narrative required)
  │     ↓
  │   slide_negotiation ← (iterating slides one-by-one)
  │     ↓
  │   structure_agreed ← (all slides confirmed)
  │     ↓
  ├─→ ready_to_plan ← (sufficient context, preparing execution plan)
  │     ↓
  │   plan_proposed ← (plan shown to user for approval)
  │     ↓
  │   confirming ← (user confirms execution)
  │     ↓
  │   done ← (execution complete or abandoned)
  │
  └─→ done ← (insufficient interest, user aborted)
```

**Allowed States**:
- `new` — conversation initialized
- `exploring` — understanding user intent
- `discovery` — gathering required information
- `storyline_building` — narrative options proposed
- `slide_negotiation` — slide-by-slide refinement
- `structure_agreed` — all structural decisions confirmed
- `ready_to_plan` — generating execution plan
- `plan_proposed` — plan awaiting approval
- `confirming` — user confirming execution
- `done` — conversation concluded

### Field Definitions

| Field | Type | Purpose |
|-------|------|---------|
| `state` | String | Current FSM state (one of allowed states) |
| `slots` | Dict | Discovery answers, e.g., `{"audience": "finance team", "timeline": "Q4", "format": "slide deck"}` |
| `deliverable` | Dict | Current work item: `{"template_ids": [...], "output_types": [...], ...}` |
| `pending_questions` | List[String] | Questions still needed to advance state |
| `last_router` | Dict | Last routing decision: `{"route": "...", "skill": "...", "reason": "..."}` |
| `surfaced_wiki_refs` | List[String] | Wiki page titles referenced in conversation |
| `history_summary` | String | Compact 1-2 paragraph summary for token efficiency |

### State Transition Logic

State advances based on:

1. **Discovery Completeness** — `_has_sufficient_discovery()`
   - Checks if all required slots are populated
   - Examples: audience, timeline, tone, scope

2. **Intent Detection** — `_is_proposal_instruction()`
   - Regex patterns for proposal keywords ("create", "design", "make", "build")
   - Deliverable detection ("deck", "document", "email")
   - Execute-now signals ("right away", "immediately", "let's go")

3. **Routing Decisions** — `route_turn()`
   - Determines next action: ask question, show options, generate plan, execute
   - Updates `last_router` with decision metadata

### Load and Save Functions

**Load state** — `load_state(conv)`
```python
def load_state(conv: Conversation) -> ConversationState:
    # Reads JSON from disk
    # Returns default_state() if file missing or invalid
    # Schema version validation for migration safety
```

**Save state** — `save_state(conv, state)`
```python
def save_state(conv: Conversation, state: ConversationState) -> None:
    # Writes state.to_json() to workspace path
    # Atomic write to prevent corruption
    # No database transaction needed (filesystem is independent)
```

---

## 3. Long-Term Memory (Database-Backed Persistence)

### MemoryEvent Model

**Location**: `src/core/db/models.py:295`

Immutable event stream recording discoveries, decisions, and insights.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | Integer | Auto-increment primary key |
| `project_id` | FK → Project | Project context (indexed) |
| `run_id` | FK → Run | Associated run (indexed) |
| `event_type` | String(64) | Event classification: "discovery_answer", "routing_decision", etc. |
| `fingerprint` | String(64) | Deduplication key (indexed) |
| `payload` | Text | Event details as JSON |
| `created_at` | DateTime | Event timestamp (indexed) |

**Purpose**: Build an immutable audit trail and knowledge base. Events feed into memory aggregation.

**Example Payloads**:
```json
{
  "event_type": "discovery_answer",
  "fingerprint": "sha256(project_id + 'audience' + 'marketing team')",
  "payload": {
    "question": "Who is the audience?",
    "answer": "marketing team",
    "confidence": "high",
    "source": "chat"
  }
}
```

### MemoryItem Model

**Location**: `src/core/db/models.py:373`

Durable facts extracted from events. Queryable knowledge store per project.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | String(64) | Primary key |
| `project_id` | FK → Project | Project scope (indexed) |
| `memory_type` | String(32) | "preference" \| "constraint" \| "decision" \| "fact" (indexed) |
| `key` | String(128) | Identifier within type (e.g., "audience_preference") |
| `value` | Text | Content (e.g., "finance team") |
| `confidence` | String(16) | "high" \| "medium" \| "low" |
| `source` | String(64) | Where learned (e.g., "chat", "wiki", "run_output") |
| `consent_state` | String(16) | "allowed" \| "restricted" \| "revoked" |
| `principal_id` | String(128) | DPDP principal for consent tracking (indexed) |
| `is_archived` | Boolean | Soft-delete flag (default: false) |
| `created_at` | DateTime | Creation time (indexed) |
| `updated_at` | DateTime | Last modification |

**Unique Constraint**: (`project_id`, `memory_type`, `key`) — only one fact per type+key per project.

**Example Rows**:
```
memory_type=preference, key=audience_preference, value=finance_team
memory_type=constraint, key=timeline_constraint, value=Q4_2024
memory_type=decision, key=deck_format_decision, value=16x9_slides
memory_type=fact, key=company_size, value=500_employees
```

### ProjectMemoryProfile Model

**Location**: `src/core/db/models.py:307`

Aggregated summary of all MemoryItems and MemoryEvents for quick retrieval.

| Column | Type | Purpose |
|--------|------|---------|
| `project_id` | PK → Project | Project context |
| `summary_json` | Text | Indexed dict of all memory items (default: "{}") |
| `updated_at` | DateTime | Last aggregation time |

**Updated by**: `get_aggregated_profile()`

**Format**:
```json
{
  "preferences": [
    { "key": "audience_preference", "value": "finance_team", "confidence": "high" },
    { "key": "tone_preference", "value": "executive_brief", "confidence": "medium" }
  ],
  "constraints": [
    { "key": "timeline_constraint", "value": "Q4_2024", "confidence": "high" },
    { "key": "budget_constraint", "value": "under_$50k", "confidence": "medium" }
  ],
  "decisions": [
    { "key": "format_decision", "value": "slide_deck", "confidence": "high" }
  ],
  "facts": [...]
}
```

---

## 4. Background Execution (ConversationTurn Processing)

### Overview

Long-running LLM responses are processed asynchronously to prevent HTTP request timeouts. The frontend polls for completion.

**Location**: `src/app/api/projects/conversation_turns.py`

### Thread Pool

```python
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="conversation-turn")
_LIVE_PHASE: dict[str, str] = {}  # In-memory phase tracking
_STALE_AFTER = timedelta(minutes=15)  # Timeout detection
```

**Design rationale**:
- Max 8 concurrent background tasks (prevents thread explosion)
- In-memory phase dict avoids database writes during polling (SQLite locking issue)
- Stale turn detection: if running >15 min, worker lost (server restart, crash, etc.)

### Execution Phases

Human-readable progress states shown to the frontend.

| Phase | Label | Meaning |
|-------|-------|---------|
| `queued` | "Starting" | Turn created, waiting for worker thread |
| `receive` | "Reading your message" | Parsing user input |
| `understand` | "Working out what you have told me so far" | Extracting discovery answers from history |
| `route` | "Checking the project knowledge and deciding the next step" | Routing to appropriate handler |
| `respond` | "Writing the reply" | LLM generating response |

### Function: `start_turn()`

```python
def start_turn(pid: str, body: ConversationMessageRequest, user: User, db: Session) -> dict:
    """Answer a chat message in the background."""
    
    # 1. Validate input
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content must not be empty")
    
    # 2. Check authorization
    require_project_role(pid, {"Owner", "Editor", "Viewer"}, user, db)
    
    # 3. Create turn record
    turn = ConversationTurn(
        id=f"t_{uuid.uuid4().hex[:16]}", 
        project_id=pid, 
        user_id=user.id
    )
    db.add(turn)
    db.commit()  # Persist turn BEFORE submitting work
    
    # 4. Submit work to thread pool
    _EXECUTOR.submit(
        _answer_turn, 
        turn.id, 
        pid, 
        user.id, 
        lambda session, who, on_phase: _post_project_conversation_message_impl(...)
    )
    
    # 5. Return immediately
    return {
        "turn_id": turn.id,
        "status": "running",
        "phase": "queued",
        "phase_label": PHASE_LABELS["queued"]
    }
```

### Function: `_answer_turn()`

Runs in worker thread.

```python
def _answer_turn(turn_id: str, pid: str, user_id: str, work: Work) -> None:
    """Execute work in background and persist result."""
    
    db = SessionLocal()  # New session for this thread
    try:
        user = db.get(User, user_id)
        
        # Execute work with phase callback
        response = work(
            db, 
            user, 
            lambda name: _LIVE_PHASE.__setitem__(turn_id, name)
        )
        
        db.commit()
        
        # Persist success
        _update_turn(
            turn_id,
            status="done",
            phase=_LIVE_PHASE.get(turn_id, "queued"),
            response_json=json.dumps(response, default=str)
        )
        
    except HTTPException as exc:
        db.rollback()
        _update_turn(
            turn_id,
            status="failed",
            status_code=exc.status_code,
            response_json=json.dumps({"detail": exc.detail}, default=str)
        )
        
    except Exception as exc:
        db.rollback()
        _LOG.exception("conversation_turn_failed project=%s turn=%s", pid, turn_id)
        _update_turn(
            turn_id,
            status="failed",
            status_code=500,
            response_json=json.dumps({
                "detail": f"conversation_message_failed: {type(exc).__name__}: {str(exc)[:300]}"
            })
        )
        
    finally:
        db.close()
        _LIVE_PHASE.pop(turn_id, None)  # Cleanup phase tracking
```

### Function: `get_project_conversation_turn()` (Polling Endpoint)

```python
@router.get("/{pid}/conversation/turns/{turn_id}")
def get_project_conversation_turn(
    pid: str,
    turn_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Poll for turn status and result."""
    
    # 1. Authorization
    require_project_role(pid, {"Owner", "Editor", "Viewer"}, user, db)
    
    # 2. Lookup turn
    turn = db.get(ConversationTurn, turn_id)
    if turn is None or turn.project_id != pid or turn.user_id != user.id:
        raise HTTPException(status_code=404, detail="turn not found")
    
    # 3. Determine phase (live or persisted)
    phase = _LIVE_PHASE.get(turn.id, turn.phase) if turn.status == "running" else turn.phase
    
    out = {
        "turn_id": turn.id,
        "status": turn.status,
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase),
    }
    
    # 4. Detect stale turns
    if turn.status == "running" and ist_now() - turn.created_at > _STALE_AFTER:
        out.update(
            status="failed",
            status_code=503,
            response={"detail": "The reply was interrupted. Please send the message again."}
        )
    
    # 5. Return response if complete
    elif turn.status != "running":
        out.update(
            status_code=turn.status_code,
            response=json.loads(turn.response_json or "{}")
        )
    
    return out
```

---

## 5. Data Flow: User Message to Response

### HTTP Request Flow

```
1. POST /{pid}/conversation/messages?background=true
   ├─ Body: { "content": "Create a sales deck for Q4" }
   └─ Returns immediately with turn_id

2. [ASYNC IN WORKER THREAD]
   ├─ _answer_turn() fetches user from database
   ├─ Calls work() with phase callback
   │  └─ work = _post_project_conversation_message_impl()
   ├─ Phase callback: lambda name: _LIVE_PHASE[turn_id] = name
   └─ Phase progression: queued → receive → understand → route → respond

3. _post_project_conversation_message_impl():
   ├─ load_state(conversation) — read FSM state from disk
   ├─ Callback: on_phase("receive")
   ├─ _extract_discovery_answers() — parse user's message for slots
   ├─ Callback: on_phase("understand")
   ├─ route_turn(state, context) — decide next action
   ├─ record_discovery_answer() — append MemoryEvent
   ├─ record_routing_decision() — append MemoryEvent
   ├─ save_state(conversation, state) — flush to disk
   ├─ Callback: on_phase("route")
   ├─ [Optionally] _generate_and_execute_plan() — if ready
   ├─ Callback: on_phase("respond")
   └─ Return response dict

4. _answer_turn() persists:
   └─ _update_turn(turn_id, status="done", response_json=...)

5. [FRONTEND POLLING]
   └─ GET /{pid}/conversation/turns/{turn_id}
      ├─ If running: phase from _LIVE_PHASE
      ├─ If done: response from database
      └─ Display progress + response
```

### State Management During Message Processing

```
Before:
  conversation_state/{conv_id}.json:
    {
      "state": "discovery",
      "slots": { "audience": "finance team" },
      "pending_questions": ["What timeline?", "What format?"]
    }

During:
  In worker thread:
  1. Load state → ConversationState object
  2. Extract "Q4 timeline" from message
  3. Update state.slots["timeline"] = "Q4"
  4. Check _has_sufficient_discovery() → still pending "format"
  5. Update state.pending_questions = ["What format?"]
  6. Save state → persists to disk

After:
  conversation_state/{conv_id}.json:
    {
      "state": "discovery",
      "slots": { "audience": "finance team", "timeline": "Q4" },
      "pending_questions": ["What format?"]
    }
```

---

## 6. Memory Retrieval for LLM Context

### TieredContextEngine

**Location**: `src/memory/retrieval.py`

Assembles multi-source context for the LLM, respecting token limits and consent.

**Retrieval Order** (most to least recent):

1. **Recent Messages** — Last N conversation messages (most recent first)
   - Provides immediate context
   - Respects message freshness for source_type

2. **Conversation State** — Current FSM state from disk
   - Pending questions: what still needs asking
   - Slots: collected discoveries
   - History summary: compact arc summary

3. **Project Memory Items** — Filtered MemoryItems
   - Scope: only current project
   - Filters:
     - Exclude archived items (`is_archived = false`)
     - Respect consent ledger (DPDP compliance)
   - Sorted by: confidence, recency

4. **Engagement Metadata** — Client/sponsor info from EngagementMeta
   - Code, type, stage, brief, sponsor objective
   - Scope, success measures

5. **Wiki References** — Knowledge base context
   - Surfaced wiki pages from `state.surfaced_wiki_refs`
   - Hyperlinks within conversation

6. **History Summary** — Fallback compression
   - Used when token budget exceeded
   - One-paragraph summary of conversation arc

### Consent Enforcement

Memory items respect DPDP Data Protection and Privacy (India's data law):

```python
# Check consent before including MemoryItem in context
if item.principal_id:
    consent = check_consent_ledger(project_id, principal_id, "use_in_context")
    if not consent or consent.revoked_at:
        skip_item()
```

---

## 7. Key Design Patterns

### Pattern: Dual-Store Memory

| Storage | Type | Purpose |
|---------|------|---------|
| **Filesystem** | Short-term state machine | Fast read/write without database locking; conversation-local |
| **Database** | Long-term events + items | Durable, searchable, aggregatable across conversations |

**Rationale**: 
- Filesystem avoids SQLite locking during conversation polling
- Database provides audit trail and cross-conversation knowledge
- Separation of concerns: runtime state ≠ durable facts

### Pattern: Fingerprinting for Deduplication

```python
MemoryEvent.fingerprint = sha256(project_id + event_type + key)
```

Prevents duplicate discoveries (e.g., "audience: finance" recorded twice).

### Pattern: Soft Delete for DPDP Compliance

```python
MemoryItem.is_archived = True  # Instead of DELETE
MemoryItem.principal_id = "subject_001"  # Track data subject
```

Allows erasure requests without breaking referential integrity.

### Pattern: In-Memory Phase Tracking

```python
_LIVE_PHASE: dict[str, str] = {}  # { turn_id: phase_name }
```

Avoids database writes during polling; cleaned up on turn completion.

### Pattern: FSM-Driven State

```python
state.state ∈ {new, exploring, discovery, ..., done}
state.pending_questions ← required_discovery_missing_slots(state)
transition ← based on intent detection + discovery completeness
```

Enforces valid conversation flows; prevents invalid state combinations.

---

## 8. API Endpoints

### Conversation Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/{pid}/conversation` | Create new conversation |
| `GET` | `/{pid}/conversations` | List project conversations |
| `GET` | `/{pid}/conversation/{conv_id}` | Get conversation details |
| `DELETE` | `/{pid}/conversation/{conv_id}` | Delete conversation |

### Message Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/{pid}/conversation/messages` | Send message (sync or async with `?background=true`) |
| `GET` | `/{pid}/conversation/messages/{conv_id}` | Fetch conversation messages |
| `GET` | `/{pid}/conversation/turns/{turn_id}` | Poll background task status |

### Discovery & Routing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/{pid}/conversation/discovery-answers` | Submit discovery answers |
| `POST` | `/{pid}/conversation/outline-updates` | Slide negotiation updates |
| `POST` | `/{pid}/conversation/confirm` | Confirm plan/decision |

---

## 9. Common Operations

### Loading a Conversation

```python
from src.core.db.session import SessionLocal
from src.core.db.models import Conversation
from src.memory.short_term.conversation_state import load_state

db = SessionLocal()
conv = db.query(Conversation).filter_by(id="conv_123").first()
state = load_state(conv)

print(f"State: {state.state}")
print(f"Pending: {state.pending_questions}")
print(f"Slots: {state.slots}")
```

### Updating Conversation State

```python
from src.memory.short_term.conversation_state import save_state

state.slots["audience"] = "finance_team"
state.pending_questions.remove("What is the audience?")
save_state(conv, state)
```

### Recording a Discovery

```python
from src.memory.long_term.memory_event_service import record_discovery_answer

record_discovery_answer(
    project_id=conv.project_id,
    run_id=None,
    question="Who is the audience?",
    answer="finance_team",
    confidence="high"
)
```

### Querying Project Memory

```python
from src.memory.long_term.memory_event_service import get_aggregated_profile

profile = get_aggregated_profile(project_id="proj_123")
preferences = profile.get("preferences", [])
constraints = profile.get("constraints", [])
```

---

## 10. Testing Considerations

### Mock ConversationTurn Processing

```python
# In tests, you may want to bypass threading
from unittest.mock import patch

with patch("src.app.api.projects.conversation_turns._EXECUTOR.submit") as mock_submit:
    # Mock synchronously executes work immediately
    mock_submit.side_effect = lambda f, *args, **kw: f(*args, **kw)
    
    # Test conversation endpoint
    response = client.post(f"/{pid}/conversation/messages", json={"content": "..."})
    assert response.status_code == 200
```

### Integration Test Setup

```python
# tests/integration/conftest.py sets JWT_SECRET automatically
pytest  # Runs integration suite with real DB

# Unit tests use sqlite in-memory or mocks
pytest tests/unit/
```

---

## 11. Performance Considerations

| Consideration | Impact | Mitigation |
|---------------|--------|-----------|
| Filesystem I/O (state save) | ~10-50ms per turn | Async write in background; don't block response |
| Database writes (MemoryEvent) | ~5-20ms per event | Batch events; use connection pooling |
| LLM latency | 1-30s per response | ThreadPoolExecutor prevents blocking; client polls |
| Memory aggregation | ~50-200ms | Cache ProjectMemoryProfile; invalidate on MemoryEvent |
| Context assembly | ~100-500ms | Token budget; compress history summary |

---

## 12. Future Enhancements

### Planned Work

1. **Persist phase tracking to Redis** — Enable turn rehydration after server restart
2. **Conversation history compression** — Auto-summarize old turns
3. **Cross-conversation memory inference** — Learn patterns across projects
4. **Async conversation archival** — Automated cleanup of old conversations
5. **Real-time collaboration** — Multiple users editing same conversation

---

## References

- **Model Definitions**: `src/core/db/models.py`
- **State Machine**: `src/memory/short_term/conversation_state.py`
- **Background Execution**: `src/app/api/projects/conversation_turns.py`
- **Message Processing**: `src/app/api/projects/conversation.py`
- **Memory Services**: `src/memory/long_term/memory_event_service.py`
- **Context Retrieval**: `src/memory/retrieval.py`
- **Intent Detection**: `src/app/api/projects/_intent.py`
- **Discovery Extraction**: `src/app/api/projects/_discovery.py`
- **Routing Logic**: `src/workflows/task_router/conversation_router.py`
