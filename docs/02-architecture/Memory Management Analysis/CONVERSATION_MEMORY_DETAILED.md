# Conversation Section: Complete Memory Capture, Storage & Engagement Process

## Table of Contents
1. Memory Types Captured in Conversation
2. Storage Locations & Schemas
3. Retention Policies
4. Prompt Generation at Each Step
5. Complete Engagement Process Data Flow
6. LLM Integration & Tracking
7. Data Persistence Timeline

---

## 1. Memory Types Captured in Conversation

### 1.1 User Messages (Input Memory)

**What**: Each user message sent to the conversation

**Captured Data**:
```python
{
    "user_message": "Create a sales deck for Q4",
    "timestamp": "2026-10-30T10:30:45.123+05:30",
    "user_id": "user_123",
    "conversation_id": "conv_abc",
    "project_id": "proj_xyz"
}
```

**Storage**: `ConversationMessage` table
```python
class ConversationMessage(Base):
    id: int                          # Auto-increment
    conversation_id: str             # FK
    role: str = "user"               # Role identifier
    content: str                     # Message text
    metadata_json: str = "{}"        # Optional metadata
    source_type: str | None          # Where message originated
    source_freshness_at: DateTime    # Source cache time
    created_at: DateTime             # Indexed for ordering
```

**Metadata Captured**:
```json
{
    "plan_confirmed": false,
    "plan_hash": "abc123",
    "instruction": "Create sales deck",
    "detected_intent": "proposal",
    "discovery_slots_provided": ["audience", "timeline"],
    "wiki_references": ["Best Practices"],
    "sentiment": "positive",
    "confidence_level": 0.95
}
```

---

### 1.2 Assistant Responses (Output Memory)

**What**: Each LLM response sent back to user

**Captured Data**:
```python
{
    "assistant_response": "I'll help you create a Q4 sales deck...",
    "response_type": "clarification|discovery|plan|feedback",
    "reasoning": "User needs audience and timeline before planning",
    "confidence": 0.92
}
```

**Storage**: `ConversationMessage` table (role="assistant")

**Metadata Captured**:
```json
{
    "kind": "discovery_question",
    "next_state": "discovery",
    "questions_asked": ["What is the target audience?", "When is the deadline?"],
    "context_sources": [
        "wiki:Best Practices",
        "memory:audience_preference",
        "engagement:client_brief"
    ],
    "llm_model_used": "claude-opus-5-5",
    "tokens_used": {
        "input": 2500,
        "output": 350,
        "cache_read": 1200,
        "cache_creation": 0
    },
    "response_latency_ms": 2340,
    "prompt_compression": {
        "applied": false,
        "ratio": 1.0
    }
}
```

---

### 1.3 Discovery Answers (Extractive Memory)

**What**: Parsed structured information from user messages

**Captured Data**:
```python
{
    "slot_key": "audience",
    "value": "finance team",
    "source": "chat",
    "confidence": "high",
    "question_asked": "Who is the target audience?",
    "user_response": "Finance team and C-suite execs",
    "extracted_at": "2026-10-30T10:35:12"
}
```

**Storage**: 
- **ProjectMemoryProfile** (aggregated, indexed)
- **MemoryEvent** (event log, immutable)

**Data Structure**:
```json
ProjectMemoryProfile.summary_json:
{
    "users": {
        "user_123": {
            "aggregated_slots": {
                "audience": "finance_team",
                "timeline": "Q4_2024",
                "format": "slide_deck"
            },
            "decision_outcomes": {
                "format_choice": {
                    "count": 2,
                    "avg_confidence": 0.94,
                    "last_outcome": "slide_deck"
                }
            },
            "updated_at": "2026-10-30T10:35:12"
        }
    }
}
```

---

### 1.4 Conversation State (FSM Memory)

**What**: Current conversation progress through the state machine

**Captured Data**:
```python
{
    "state": "discovery",
    "slots": {
        "audience": "finance_team",
        "timeline": "Q4_2024",
        "budget": null
    },
    "pending_questions": [
        "What is your budget?",
        "Who are the stakeholders?"
    ],
    "deliverable": {
        "template_ids": ["pptx_default"],
        "output_types": ["slide_deck"],
        "custom_formats": []
    },
    "last_router": {
        "route": "ask_discovery_question",
        "reason": "Still missing budget information",
        "skill": null,
        "context_quality": 0.72
    },
    "surfaced_wiki_refs": [
        "Best Practices for Executive Decks",
        "Q4 Planning Framework"
    ],
    "history_summary": "User requested sales deck for Q4. Target audience is finance team..."
}
```

**Storage**: Filesystem JSON
- **Path**: `workspace/{project_id}/conversation_state/{conversation_id}.json`
- **Size**: ~5-50 KB
- **Access Pattern**: Read/write on every message

---

### 1.5 Decision Outcomes (Memory Items)

**What**: Important decisions made during conversation

**Captured Data**:
```python
{
    "memory_type": "decision",
    "key": "format_decision",
    "value": "slide_deck",
    "confidence": "high",
    "source": "chat",
    "created_at": "2026-10-30T10:45:00",
    "created_by_user": "user_123",
    "created_by_project": "proj_xyz",
    "rationale": "User explicitly requested 'PowerPoint deck'",
    "impact": "Determines content skill targets and output format"
}
```

**Storage**: 
- **MemoryItem** table (persistent)
- **ProjectMemoryProfile** (indexed for quick retrieval)

---

### 1.6 Wiki & Knowledge References (Context Memory)

**What**: Project knowledge (wiki pages, leading practices) referenced during conversation

**Captured Data**:
```python
{
    "wiki_page": "Best Practices for Executive Decks",
    "url": "/wiki/best_practices",
    "referenced_in_turn": 3,
    "relevance_score": 0.92,
    "chunks_used": [
        "Keep one idea per slide",
        "Use consistent color scheme"
    ],
    "refresh_time": "2026-10-29T18:00:00",
    "is_stale": false,
    "freshness_ttl_hours": 72
}
```

**Storage**:
- **ConversationState.surfaced_wiki_refs** (conversation-specific)
- **Wiki cache** (project-wide, mtime-based invalidation)

---

## 2. Storage Locations & Complete Schema Mapping

### 2.1 Database Storage (SQLite/PostgreSQL)

#### Table: `conversations`
```
┌─────────────────────────────────────────────┐
│ CONVERSATIONS (Project-level)               │
├─────────────────────────────────────────────┤
│ id (PK)              str(64)                │
│ project_id (FK)      str(64) [indexed]      │
│ user_id (FK)         str(64) [indexed]      │
│ title                str(255)               │
│ skill_id             str(64)                │
│ created_at           DateTime               │
│ updated_at           DateTime               │
└─────────────────────────────────────────────┘

Total: 1 row per conversation thread
```

#### Table: `conversation_messages`
```
┌──────────────────────────────────────────────┐
│ CONVERSATION_MESSAGES (Append-only log)      │
├──────────────────────────────────────────────┤
│ id (PK)              Integer (auto-inc)      │
│ conversation_id (FK) str(64) [indexed]       │
│ role                 str(16): user|assistant │
│ content              Text                    │
│ metadata_json        Text                    │
│ source_type          str(32) [indexed]       │
│ source_freshness_at  DateTime [indexed]      │
│ created_at           DateTime [indexed]      │
└──────────────────────────────────────────────┘

Total: 1 row per message (unlimited growth)
Index: (conversation_id, created_at) for ordering
```

#### Table: `conversation_turns`
```
┌──────────────────────────────────────────────┐
│ CONVERSATION_TURNS (Background tasks)        │
├──────────────────────────────────────────────┤
│ id (PK)              str(64): t_{uuid16}     │
│ project_id (FK)      str(64) [indexed]       │
│ user_id (FK)         str(64) [indexed]       │
│ status               str(16): running|done   │
│ phase                str(32): queued|...     │
│ status_code          Integer                 │
│ response_json        Text                    │
│ created_at           DateTime                │
│ updated_at           DateTime                │
└──────────────────────────────────────────────┘

Total: 1 row per async message
Lifetime: Until response_json populated
```

#### Table: `memory_events`
```
┌──────────────────────────────────────────────┐
│ MEMORY_EVENTS (Immutable event stream)       │
├──────────────────────────────────────────────┤
│ id (PK)              Integer (auto-inc)      │
│ project_id (FK)      str(64) [indexed]       │
│ run_id (FK)          str(64) [indexed]       │
│ event_type           str(64)                 │
│ fingerprint          str(64) [indexed]       │
│ payload              Text (JSON)             │
│ created_at           DateTime [indexed]      │
└──────────────────────────────────────────────┘

Event Types:
- discovery_answer_recorded
- routing_decision_recorded
- memory_item_created
- memory_item_archived

Retention: 30 days (memory_events_retention_days config)
Deduplication: By fingerprint (SHA256)
```

#### Table: `project_memory_profiles`
```
┌──────────────────────────────────────────────┐
│ PROJECT_MEMORY_PROFILES (Aggregation cache)  │
├──────────────────────────────────────────────┤
│ project_id (PK)      str(64)                 │
│ summary_json         Text (JSON blob)        │
│ updated_at           DateTime                │
└──────────────────────────────────────────────┘

Contents (summary_json):
{
    "users": {
        "user_id": {
            "aggregated_slots": { ... },
            "decision_outcomes": { ... },
            "updated_at": "..."
        }
    }
}

Total: 1 row per project
Update Frequency: On each discovery/decision record
```

#### Table: `memory_items`
```
┌──────────────────────────────────────────────┐
│ MEMORY_ITEMS (Durable fact store)            │
├──────────────────────────────────────────────┤
│ id (PK)              str(64)                 │
│ project_id (FK)      str(64) [indexed]       │
│ memory_type          str(32) [indexed]       │
│ key                  str(128)                │
│ value                Text                    │
│ confidence           str(16)                 │
│ source               str(64)                 │
│ consent_state        str(16)                 │
│ principal_id         str(128) [indexed]      │
│ is_archived          Boolean                 │
│ created_at           DateTime [indexed]      │
│ updated_at           DateTime                │
└──────────────────────────────────────────────┘

Unique Constraint: (project_id, memory_type, key)
Retention: Indefinite (until archived/deleted)
```

---

### 2.2 Filesystem Storage

#### Conversation State Files
```
workspace/
├── {project_id}/
│   └── conversation_state/
│       ├── {conversation_id_1}.json    ← 1 per conversation
│       ├── {conversation_id_2}.json
│       └── ...
```

**File Structure**:
```json
{
    "schema_version": 2,
    "state": "discovery",
    "slots": { "audience": "...", "timeline": "..." },
    "deliverable": { "template_ids": [...], "output_types": [...] },
    "last_router": { "route": "...", "reason": "..." },
    "pending_questions": ["Q1", "Q2"],
    "surfaced_wiki_refs": ["Ref1", "Ref2"],
    "history_summary": "User requested..."
}
```

**Lifecycle**:
- **Created**: When first message arrives in conversation
- **Updated**: After every message processing
- **Location**: Read at start of `load_state()`, written at end of `save_state()`
- **TTL**: Indefinite (stays until conversation deleted)
- **Size**: 5-50 KB per conversation

---

### 2.3 In-Memory Storage

#### ConversationTurn Phase Tracking
```python
_LIVE_PHASE: dict[str, str] = {}
# Key: turn_id
# Value: current phase (queued, receive, understand, route, respond)
# Lifetime: Duration of async task execution (~1-30 seconds)
# Purpose: Live progress tracking for polling endpoint
```

#### BM25 Index Cache (TieredContextEngine)
```python
_parsed_cache: dict[str, tuple[float, list[dict], _BM25Index]] = {}
# Key: str(workspace_path(project_id) / "parsed_docs")
# Value: (mtime, chunks, bm25_index)
# Invalidation: When any .json file mtime changes
# Scope: Per API process (not shared across replicas)
```

#### Wiki Cache
```python
_wiki_cache: dict[str, tuple[float, list[str], _BM25Index]] = {}
# Key: str(workspace_path(project_id) / "wiki")
# Value: (mtime, chunks, bm25_index)
# TTL: 72 hours (for staleness marking, not eviction)
# Invalidation: mtime change
```

---

### 2.4 Redis Cache (Optional)

```python
cache_service.set(key, value, ttl_seconds)

Example:
    key: "context:proj_xyz:instruction_hash"
    value: {"text": "assembled context", "sources": [...]}
    ttl: 3600 (1 hour)
```

**When Used**:
- Prompt assembly results (rarely, most cacheable at prompt level)
- Aggregated profile snapshots (optional)
- Wiki rebuild events

---

## 3. Retention Policies

### 3.1 Conversation Messages (DB)

| Item | Retention | Policy | Cleanup |
|------|-----------|--------|---------|
| ConversationMessage | Indefinite | No auto-delete | Manual via DELETE API |
| User message content | Indefinite | Persisted as-is | Upon conversation delete |
| Metadata JSON | Indefinite | With message | Upon conversation delete |

**Query Pattern**:
```python
# Get last 40 messages (most recent)
select(ConversationMessage)
    .where(ConversationMessage.conversation_id == cid)
    .order_by(ConversationMessage.created_at.desc())
    .limit(40)
```

---

### 3.2 Conversation State (Filesystem)

| Item | Retention | Policy | Cleanup |
|------|-----------|--------|---------|
| State JSON file | Indefinite | Latest version only | Upon conversation delete |
| History snapshots | None | Not stored (only current) | N/A |

**Size Limit**: No hard limit, but practical ~50 KB max

---

### 3.3 Memory Events (DB)

| Item | Retention | Policy | Config |
|------|-----------|--------|--------|
| MemoryEvent rows | 30 days | Auto-delete after | `memory_events_retention_days: int = 30` |
| Fingerprint dedup | 30 days | Lookback window | Same as events |

**Query Pattern**:
```python
# Retention cleanup (runs daily)
delete(MemoryEvent).where(
    MemoryEvent.created_at < (now() - timedelta(days=30))
)
```

---

### 3.4 Conversation Source Freshness

| Item | Retention | Policy | Config |
|------|-----------|--------|---------|
| Source freshness marker | 72 hours | Marks old as [STALE] | `conversation_source_freshness_ttl_seconds: int = 259200` |
| Exclusion of stale | Dynamic | Checked per digest | `conversation_digest_exclude_stale_sources: bool = True` |

**When Applied**:
```python
# In build_conversation_digest_for_run()
freshness_map = mark_stale_sources(
    rows,
    ttl_seconds=settings.conversation_source_freshness_ttl_seconds  # 72h
)

# Mark old messages with [STALE] prefix for LLM awareness
if info and info.is_stale:
    body = f"[STALE: {age_h}h old]\n{body}"
```

---

### 3.5 Wiki Freshness (Not Retention)

| Item | Behavior | Policy | Config |
|------|----------|--------|--------|
| Wiki pages | Marked [STALE] | Prefix warning only, not deleted | `_WIKI_STALE_HOURS = 72` |
| Cache invalidation | mtime-based | Reloaded when any file changes | N/A |

**Example Output**:
```
[Wiki: Best Practices for Decks]
[STALE: 80h old]

Keep one idea per slide...
Use consistent color scheme...
```

---

## 4. Prompt Generation at Each Step

### 4.1 Discovery Phase Prompt

**When**: User message arrives during discovery state

**Prompt Assembly**:
```
SYSTEM PROMPT:
├─ Base system: "You are a conversation assistant..."
├─ Project context: CONTEXT.md (first 2,000 chars)
├─ Leading practices: LP snippets (up to 12,000 chars)
├─ Current state: ConversationState (slots, pending, history_summary)
├─ Engagement metadata: Brief, sponsor objective, scope
├─ Recent messages: Last 10-12 messages (with compaction)
└─ Memory items: Project facts/preferences (consent-filtered)

Total system prompt: ~15-20 KB (before compression)
```

**Example System Prompt**:
```markdown
# You are Sheldon, a conversation assistant for business engagements.

## Project Context
From CONTEXT.md:
[Project overview, constraints, client info...]

## Leading Practices
[Curated snippets about best practices...]

## Current Conversation State
State: discovery
Slots Collected: 
  - audience: finance_team
  - timeline: Q4_2024
Pending Questions:
  - What is the budget?
  - Who are stakeholders?

## Engagement Metadata
Brief: Sales deck for Q4 product launch...
Sponsor: VP Sales
Scope: Finance team, C-suite executives

## Recent Conversation
User: Create a sales deck for Q4
Assistant: I'll help. Let me ask some questions...
User: Finance team and C-suite are the audience

## Conversation History Summary
User requested sales deck for Q4, targeting finance team...

## Memory
Preferences: audience_type=executive, format=visual
Constraints: timeline=Q4_2024, budget_class=enterprise
```

**USER PROMPT**:
```markdown
User's Latest Message:
"Finance team and C-suite executives are the key audience"

Instructions:
1. Extract discovery answers from the message
2. Check if sufficient information to plan
3. If ready, summarize the plan and ask for confirmation
4. If not ready, ask the next most important question
```

**Metrics Tracked**:
- System prompt tokens: ~3,500
- User prompt tokens: ~500
- Total: ~4,000 tokens (before output)

---

### 4.2 Planning Phase Prompt

**When**: User confirms execution ("Let's go")

**Prompt Assembly**:
```
SYSTEM PROMPT:
├─ Planner-specific system instruction
├─ Project context (CONTEXT.md)
├─ Planner excerpt: Ranked wiki + parsed_docs (7,000 chars max)
├─ Full discovery slots
├─ Engagement metadata
├─ Output format specifications
├─ Quality requirements
└─ Earlier plan attempts (if regenerating)

Total system: ~20-30 KB
```

**Example Planner Prompt**:
```markdown
# You are the Coordinator planning content delivery.

## Project Context
[Full CONTEXT.md...]

## Knowledge Excerpt (Ranked by Relevance)
[Top wiki + document chunks, up to 7 KB...]

## Confirmed Discovery
Audience: Finance team, C-suite executives
Timeline: Q4 2024 (6 weeks)
Format: PowerPoint slide deck
Budget: Enterprise class
Geography: North America
Tone: Executive brief
Primary message: Product differentiation

## Content Skill Targets
Slide 1 - Title/Positioning (PPTX specialist)
Slide 2 - Market Context (PPTX specialist)
Slide 3 - Solution Overview (PPTX specialist)
...

## Quality Requirements
- Evidence-backed claims (with sources)
- Consistent visual language
- Actionable next steps
- Deck outline agreed by user

## Output Format
Generate a detailed plan including:
1. Slide-by-slide outline with titles and key points
2. Visual elements per slide
3. Data/evidence sources
4. Estimated time to produce
```

**Metrics Tracked**:
- Context assembly time: ~500 ms
- Coordinator planning tokens: ~8,000-12,000
- Output tokens: ~2,000-4,000 (plan text)

---

### 4.3 Slide Negotiation Prompt

**When**: User edits slide-by-slide during slide_negotiation state

**Prompt Assembly**:
```
SYSTEM PROMPT:
├─ Slide negotiation agent instructions
├─ Current deck outline (from previous plan)
├─ Slide-level feedback from user
├─ Context on affected slides
└─ Quality gates

USER PROMPT:
"Move risk analysis to slide 5 and expand market context on slide 3"
```

**Metrics**:
- Focused, ~3-5 KB system + user
- Fast responses (~1 second)
- Tokens: ~1,000-2,000 input, ~500-1,000 output

---

## 5. Complete Engagement Process Data Flow

### 5.1 End-to-End Timeline

```
STEP 1: USER INITIATES CONVERSATION
┌─────────────────────────────────────────┐
│ POST /projects/{pid}/conversation       │
│ Body: { "title": "Sales Deck" }         │
└─────────────────────────────────────────┘
         │
         ▼
   CREATE:
   ├─ Conversation row (DB)
   │  └─ id, project_id, user_id, title, created_at
   ├─ ConversationState file (Filesystem)
   │  └─ state="new", slots={}, pending_questions=[]
   └─ EMIT METRIC: conversation_created_total


STEP 2: USER SENDS FIRST MESSAGE
┌─────────────────────────────────────────┐
│ POST /projects/{pid}/conversation/      │
│      messages                           │
│ Body: {                                 │
│   "content": "Create a sales deck...",  │
│   "background": true                    │
│ }                                       │
└─────────────────────────────────────────┘
         │
         ▼
   CREATE:
   ├─ ConversationTurn row (DB)
   │  └─ id=t_{uuid16}, status=running, phase=queued
   ├─ ConversationMessage (will be added later)
   └─ SUBMIT to ThreadPoolExecutor (worker thread)
   
   RETURN IMMEDIATELY:
   └─ { "turn_id": "t_...", "status": "running", "phase": "queued" }


STEP 3: WORKER THREAD - MESSAGE PROCESSING
┌─────────────────────────────────────────┐
│ Thread: _answer_turn()                  │
│ Input: turn_id, pid, user_id, work()   │
└─────────────────────────────────────────┘
         │
         ├─ UPDATE _LIVE_PHASE[turn_id] = "receive"
         │
         ├─→ PHASE: "receive"
         │    └─ load_state(conversation)
         │       └─ Read: workspace/{project_id}/conversation_state/{conv_id}.json
         │
         ├─→ PHASE: "understand"
         │    └─ _extract_discovery_answers()
         │       ├─ Parse message for slots: { "audience": "...", "timeline": "..." }
         │       └─ Store results in state.slots
         │
         ├─→ PERSIST DISCOVERY:
         │    └─ record_discovery_answer(session, project_id, slot_key, value)
         │       ├─ Load ProjectMemoryProfile with lock (SELECT FOR UPDATE)
         │       ├─ Update: .summary_json["users"][user_id]["aggregated_slots"][key]
         │       ├─ Append MemoryEvent (fingerprint dedup)
         │       ├─ Save ProjectMemoryProfile back
         │       └─ EMIT METRIC: memory_events_written_total
         │
         ├─→ PHASE: "route"
         │    ├─ route_turn(state, context)
         │    │  └─ Decide: "ask_discovery_question" OR "generate_plan"
         │    ├─ record_routing_decision()
         │    │  └─ Append MemoryEvent with decision outcome
         │    └─ UPDATE state.last_router
         │
         ├─→ ASSEMBLE CONTEXT (if asking question):
         │    ├─ Tier 0: CONTEXT.md
         │    ├─ Tier 1: LP snippets
         │    ├─ Tier 2: BM25 ranked docs (mtime-cached)
         │    ├─ Tier 3: Conversation digest (compacted)
         │    └─ Total: ≤32,000 chars (ContextBundle)
         │
         ├─→ CHECK TOKEN BUDGET:
         │    ├─ estimate_prompt_tokens(system, user)
         │    ├─ Check: prompt + output tokens vs. remaining budget
         │    └─ If over budget: compress_prompt_for_budget()
         │       └─ Apply 5-tier compression
         │       └─ EMIT METRIC: prompt_compression_applied_total
         │
         ├─→ PHASE: "respond"
         │    ├─ Call LLM (claude API)
         │    │  ├─ System prompt: [cached with cache_control: ephemeral]
         │    │  ├─ User prompt: "User's message + instructions"
         │    │  └─ Parameters: model, temperature=0.2, max_tokens=4096
         │    │
         │    ├─ LLM Response:
         │    │  ├─ response.content: String answer
         │    │  ├─ response.usage.input_tokens
         │    │  ├─ response.usage.output_tokens
         │    │  ├─ response.usage.cache_read_input_tokens (from prompt cache)
         │    │  └─ response.usage.cache_creation_input_tokens
         │    │
         │    └─ Charge tokens:
         │       └─ _RunTokenUsage.charge(
         │            input_tokens=...,
         │            output_tokens=...,
         │            cache_read_tokens=...,
         │            cache_creation_tokens=...
         │       )
         │       └─ EMIT METRIC: llm_call_tokens_total
         │
         ├─→ PERSIST RESPONSE:
         │    ├─ _persist_clarification_message() OR
         │    ├─ _persist_assistant_plan_message()
         │    │
         │    └─ CREATE ConversationMessage:
         │       └─ conversation_id: conv.id
         │       └─ role: "assistant"
         │       └─ content: LLM response
         │       └─ metadata_json: {
         │            "response_type": "discovery_question",
         │            "questions_asked": [...],
         │            "context_sources": [...],
         │            "llm_model_used": "...",
         │            "tokens_used": {...},
         │            "response_latency_ms": ...
         │          }
         │
         ├─→ UPDATE CONVERSATION STATE:
         │    ├─ state.state = "discovery" (or next state)
         │    ├─ state.pending_questions = ["Q1", "Q2"]
         │    └─ save_state(conversation, state)
         │       └─ Write: workspace/{project_id}/conversation_state/{conv_id}.json
         │       └─ EMIT METRIC: conversation_state_saved_total
         │
         └─→ FINALIZE:
             ├─ db.commit()
             ├─ _update_turn(turn_id, status="done", response_json=json.dumps(response))
             │  └─ Update ConversationTurn.response_json in DB
             ├─ Cleanup: _LIVE_PHASE.pop(turn_id, None)
             └─ EMIT METRIC: conversation_turn_completed_total


STEP 4: CLIENT POLLING FOR COMPLETION
┌─────────────────────────────────────────┐
│ GET /projects/{pid}/conversation/       │
│     turns/{turn_id}                     │
└─────────────────────────────────────────┘
         │
         ▼
   RESPONSE OPTIONS:
   
   a) WHILE RUNNING (status="running"):
      ├─ phase = _LIVE_PHASE.get(turn_id, "queued")
      ├─ RETURN {
      │   "status": "running",
      │   "phase": "understand",
      │   "phase_label": "Working out what you told me...",
      │   "turn_id": "t_..."
      │ }
      └─ Client waits 500ms, polls again
   
   b) WHEN COMPLETE (status="done"):
      ├─ RETURN {
      │   "status": "done",
      │   "phase": "respond",
      │   "phase_label": "Writing the reply",
      │   "response": {
      │     "content": "Assistant's answer...",
      │     "messages": [...],
      │     "next_state": "discovery"
      │   },
      │   "turn_id": "t_..."
      │ }
      └─ Client renders response
   
   c) IF STALE (running >15 min):
      └─ RETURN {
          "status": "failed",
          "status_code": 503,
          "response": {
            "detail": "The reply was interrupted. Please send again."
          }
        }


STEP 5: CONVERSATION CONTINUES...
User sends more messages → Loop back to STEP 2
State progresses: new → exploring → discovery → ...


STEP 6: USER CONFIRMS EXECUTION ("Let's go")
┌─────────────────────────────────────────┐
│ POST /projects/{pid}/conversation/      │
│     confirm                             │
│ Body: { "conversation_id": "...", ... } │
└─────────────────────────────────────────┘
         │
         ▼
   PERSIST CONFIRMATION:
   ├─ ConversationMessage (role="user"):
   │  └─ content: "Confirmed plan"
   │  └─ metadata_json: {
   │      "plan_confirmed": true,
   │      "plan_hash": "abc123",
   │      "instruction": "Create sales deck",
   │      "template_output_types": ["pptx_default"],
   │      "custom_output_types": [],
   │      "discovery": {...},
   │      "confirmed_at": "2026-10-30T..."
   │    }
   │
   ├─ UPDATE ConversationState:
   │  └─ state = "confirming" → "done"
   │
   ├─ CREATE RUN:
   │  ├─ Run table row
   │  │  └─ id, project_id, instruction, plan_payload, status="approved"
   │  └─ RunEvent: "run_created"
   │
   ├─ ENQUEUE EXECUTION:
   │  └─ Redis/Local queue → enqueue_run_execution()
   │
   └─ RETURN:
      └─ { "run_id": "run_123", "status": "approved" }


STEP 7: RUN EXECUTION (Separate from Conversation)
See: /docs/02-architecture/RUN_EXECUTION_FLOW.md
```

---

## 6. LLM Integration & Tracking

### 6.1 Token Usage Tracking

**At Each LLM Call**:
```python
# Before call:
check_budget(system, user, needed_output_tokens=4096)
  └─ Returns: fits_in_budget, {
       'prompt_tokens': int,
       'output_tokens': int,
       'total_tokens_needed': int,
       'remaining_budget': int,
       'compression_needed_tokens': int
     }

# After call:
_RunTokenUsage.charge(
    input_tokens=usage.input_tokens,
    output_tokens=usage.output_tokens,
    cache_read_tokens=usage.cache_read_input_tokens,
    cache_creation_tokens=usage.cache_creation_input_tokens
)

# Metrics:
├─ llm_call_total (counter)
├─ llm_tokens_input_total (counter)
├─ llm_tokens_output_total (counter)
├─ llm_tokens_cache_read_total (counter)
├─ llm_tokens_cache_creation_total (counter)
├─ llm_cost_usd_total (gauge)
└─ llm_call_latency_ms (histogram)
```

---

### 6.2 Model Routing Strategy

| Phase | Model | Purpose | Max Tokens | Thinking |
|-------|-------|---------|-----------|----------|
| Discovery | claude-haiku-4-5 | Quick classification | 4,096 | No |
| Discovery | claude-opus-5-5 | Complex routing | 4,096 | Optional |
| Planning | claude-opus-5-5 | Plan generation | 8,192 | ~6,000 budget |
| Critique | claude-sonnet-5-5 | Quality review | 4,096 | No |

**Config Parameters**:
```python
anthropic_claude_model: str = "claude-haiku-4-5"              # Default
anthropic_planning_model: str = "claude-opus-4-8"             # Planning only
anthropic_critique_model: str = "claude-sonnet-4-6"           # QA only
anthropic_max_tokens_per_run: int = 50000                     # Budget
anthropic_thinking_budget_tokens: int = 8000                  # Extended thinking
```

---

### 6.3 Prompt Caching Strategy

**System Prompt Caching**:
```python
# Wrapped with cache_control
system_with_cache = [
    {
        "type": "text",
        "text": system_prompt,
        "cache_control": {"type": "ephemeral"}  # TTL varies
    }
]

# Cost: On first use (cache creation), subsequent uses (cache read)
# Savings: ~10% cost on cache read vs. regular input

Example costs:
- First call: 2,500 input tokens + 500 cache_creation tokens
- 2nd call (same prompt): 2,500 cache_read tokens (0.1x cost)
- 3rd call (same prompt): 2,500 cache_read tokens (0.1x cost)
```

---

## 7. Data Persistence Timeline

### 7.1 Synchronous (Immediate) Persistence

| Item | Storage | Timing | Trigger |
|------|---------|--------|---------|
| ConversationMessage | DB | Immediate | After LLM response |
| ConversationState | Filesystem | Immediate | save_state() call |
| ConversationTurn response | DB | After completion | _update_turn() |
| MemoryEvent | DB | Immediate | record_discovery_answer() |
| ProjectMemoryProfile | DB | Immediate | _save_profile() |

**Transaction Example**:
```python
# Single transaction
with session.begin():
    # 1. Add message
    session.add(ConversationMessage(...))
    
    # 2. Update profile
    session.add(ProjectMemoryProfile(...))
    
    # 3. Record event
    session.add(MemoryEvent(...))
    
    session.flush()  # Ensure foreign keys resolve
```

---

### 7.2 Asynchronous Persistence

| Item | Storage | Timing | Trigger |
|------|---------|--------|---------|
| Wiki rebuild events | Filesystem | Background | Ingest completion |
| Memory event cleanup | DB | Nightly | Cron job |
| Conversation archival | Filesystem | Manual | Admin command |

---

### 7.3 Caching & Invalidation

| Item | Cache | Invalidation | TTL |
|------|-------|--------------|-----|
| BM25 index (docs) | Memory | mtime change | None (mtime-based) |
| Wiki index | Memory | mtime change | None (mtime-based) |
| Wiki staleness | Timestamp | File age | 72 hours |
| Prompt assembly | Redis | Manual/TTL | 1 hour |
| Context bundle | None | N/A | Per-call |

---

## 8. Sample Data Snapshot

### 8.1 Conversation After 3 Messages

```python
# Database State
conversations:
  {
    "id": "conv_abc123",
    "project_id": "proj_xyz",
    "user_id": "user_123",
    "title": "Q4 Sales Deck",
    "skill_id": None,
    "created_at": "2026-10-30T10:00:00",
    "updated_at": "2026-10-30T10:08:45"
  }

conversation_messages:
  [
    {
      "id": 1,
      "conversation_id": "conv_abc123",
      "role": "user",
      "content": "Create a sales deck for Q4",
      "metadata_json": "{}",
      "created_at": "2026-10-30T10:00:15"
    },
    {
      "id": 2,
      "conversation_id": "conv_abc123",
      "role": "assistant",
      "content": "I'll help you create a Q4 sales deck. Let me ask a few questions to understand your needs...",
      "metadata_json": "{\"response_type\": \"discovery_question\", \"questions_asked\": [\"Who is the target audience?\"], \"tokens_used\": {\"input\": 2500, \"output\": 350}}",
      "created_at": "2026-10-30T10:00:45"
    },
    {
      "id": 3,
      "conversation_id": "conv_abc123",
      "role": "user",
      "content": "Finance team and C-suite executives",
      "metadata_json": "{}",
      "created_at": "2026-10-30T10:02:30"
    },
    {
      "id": 4,
      "conversation_id": "conv_abc123",
      "role": "assistant",
      "content": "Great, targeting finance and C-suite. What's the timeline for this deck?",
      "metadata_json": "{\"response_type\": \"discovery_question\", \"questions_asked\": [\"When do you need this?\"], \"tokens_used\": {\"input\": 2800, \"output\": 280}}",
      "created_at": "2026-10-30T10:03:00"
    },
    {
      "id": 5,
      "conversation_id": "conv_abc123",
      "role": "user",
      "content": "End of Q3, so about 6 weeks",
      "metadata_json": "{}",
      "created_at": "2026-10-30T10:04:15"
    },
    {
      "id": 6,
      "conversation_id": "conv_abc123",
      "role": "assistant",
      "content": "Perfect! I have enough info to propose a plan. Here's what I recommend...",
      "metadata_json": "{\"response_type\": \"plan_proposal\", \"plan_hash\": \"abc123def456\", \"tokens_used\": {\"input\": 3200, \"output\": 1200}}",
      "created_at": "2026-10-30T10:05:00"
    }
  ]

# Filesystem State
workspace/proj_xyz/conversation_state/conv_abc123.json:
  {
    "schema_version": 2,
    "state": "plan_proposed",
    "slots": {
      "audience": "finance_team,c_suite",
      "timeline": "6_weeks",
      "budget": null
    },
    "deliverable": {
      "template_ids": ["pptx_default"],
      "output_types": ["slide_deck"]
    },
    "last_router": {
      "route": "generate_plan",
      "reason": "Sufficient discovery info collected",
      "skill": null
    },
    "pending_questions": [],
    "surfaced_wiki_refs": ["Q4 Planning Framework", "Executive Deck Best Practices"],
    "history_summary": "User requested Q4 sales deck for finance team with 6-week timeline. Plan generated and awaiting confirmation."
  }

# Memory State
project_memory_profiles:
  {
    "project_id": "proj_xyz",
    "summary_json": {
      "users": {
        "user_123": {
          "aggregated_slots": {
            "audience": "finance_team,c_suite",
            "timeline": "6_weeks"
          },
          "decision_outcomes": {
            "format_choice": {
              "count": 1,
              "avg_confidence": 0.95,
              "last_outcome": "slide_deck"
            }
          },
          "updated_at": "2026-10-30T10:05:00"
        }
      }
    },
    "updated_at": "2026-10-30T10:05:00"
  }

memory_events:
  [
    {
      "id": 1,
      "project_id": "proj_xyz",
      "run_id": "run_123",
      "event_type": "discovery_answer_recorded",
      "fingerprint": "sha256(proj_xyz|run_123|discovery_answer|...)",
      "payload": "{\"slot_key\": \"audience\", \"value\": \"finance_team,c_suite\", \"confidence\": \"high\"}",
      "created_at": "2026-10-30T10:02:30"
    },
    {
      "id": 2,
      "project_id": "proj_xyz",
      "run_id": "run_123",
      "event_type": "discovery_answer_recorded",
      "fingerprint": "sha256(proj_xyz|run_123|discovery_answer|...)",
      "payload": "{\"slot_key\": \"timeline\", \"value\": \"6_weeks\", \"confidence\": \"high\"}",
      "created_at": "2026-10-30T10:04:15"
    }
  ]
```

---

## Summary

### Memory Captured During Conversation
1. **User messages** → ConversationMessage (DB)
2. **Assistant responses** → ConversationMessage + metadata (DB)
3. **Discovery answers** → ProjectMemoryProfile + MemoryEvent (DB) + ConversationState (Filesystem)
4. **Routing decisions** → MemoryEvent (DB) + ConversationState (Filesystem)
5. **State machine progress** → ConversationState (Filesystem)
6. **Context used** → metadata_json on each message (DB)

### Storage Locations
- **Database**: All messages, events, memory profiles, memory items
- **Filesystem**: Conversation state (JSON), wiki, parsed docs, run artifacts
- **Memory**: BM25 indices, phase tracking, conversation digest cache
- **Redis (Optional)**: Conversation snapshots, context cache

### Retention
- **ConversationMessage**: Indefinite
- **MemoryEvent**: 30 days (configurable)
- **ConversationState**: Indefinite
- **Memory Items**: Indefinite (unless archived)
- **Source freshness**: Marked [STALE] after 72 hours (not deleted)

### Engagement Flow
User → Message → Parse → Route → Generate Context → LLM Call → Persist → Store Metrics → Return

All persisted immediately within a single transaction.
