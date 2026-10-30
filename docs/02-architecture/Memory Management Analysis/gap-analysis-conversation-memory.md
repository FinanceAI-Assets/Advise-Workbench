# Gap Analysis: Conversation Data & Memory Management

**Purpose**: Deep-dive analysis of data and memory management in conversation section, identifying critical areas, failure scenarios, performance considerations, and operational guidelines.

---

## 1. Error Handling & Data Recovery

### 1.1 LLM Call Failures

**Scenario**: Claude API call fails mid-conversation

**Current Implementation**:
```python
# src/app/api/projects/conversation.py
try:
    response = llm_call(system, user)
    # Process response
except Exception as exc:
    _LOG.error("LLM call failed: %s", exc)
    # Fallback strategy
    return _fallback_response_for_state(state)
```

**Data Impact**:
- ConversationMessage NOT persisted (no database commit)
- ConversationState NOT updated (save_state not called)
- MemoryEvent NOT recorded
- User message IS persisted (added before LLM call)
- Turn status remains "running" until timeout (15 minutes)

**Recovery Strategy**:
```python
def _deterministic_fallback_response(state: ConversationState) -> dict:
    """Generate response without LLM when API fails."""
    if state.state == "discovery":
        # Return next logical question based on slots
        pending = state.pending_questions
        if pending:
            return {
                "response": f"I need to know: {pending[0]}",
                "kind": "fallback_discovery_question"
            }
    elif state.state == "plan_proposed":
        # Acknowledge and ask for confirmation
        return {
            "response": "Ready to execute. Please confirm to proceed.",
            "kind": "fallback_confirmation_request"
        }
    return {
        "response": "I encountered an issue. Please try again.",
        "kind": "fallback_error"
    }
```

**Data Consistency Guarantee**: User message persisted even if LLM fails → user sees their message was received

**Gap Analysis**:
- ✅ User message saved before LLM call (safe)
- ✅ Fallback response generated deterministically
- ⚠️ No retry mechanism (stale turn after 15 min)
- ⚠️ ConversationState not updated → discovery progress lost
- ❌ No data validation for fallback response

**Recommendation**: 
1. Implement exponential backoff retry (max 3 attempts)
2. Save partial state before LLM call
3. Validate fallback response structure

---

### 1.2 Database Transaction Failures

**Scenario**: Database commit fails during message persistence

**Current Implementation**:
```python
# Atomic transaction
try:
    session.add(ConversationMessage(...))        # Queue add
    session.add(ProjectMemoryProfile(...))       # Queue add
    session.add(MemoryEvent(...))                # Queue add
    session.flush()                               # Execute, detect errors
    session.commit()                              # Final commit
except Exception as exc:
    session.rollback()                            # Undo all changes
    _LOG.exception("Transaction failed: %s", exc)
    raise HTTPException(status_code=500, detail="Database error")
```

**Data Rollback Guarantee**:
- ✅ All-or-nothing semantics (ACID)
- ✅ No partial writes
- ✅ Foreign key constraints enforced
- ✅ Fingerprint deduplication checked before commit

**Failure Modes**:

| Failure | State | Recovery |
|---------|-------|----------|
| Conversation FK invalid | Aborted | Conversation already exists (validated before) |
| User FK invalid | Aborted | User authenticated (validated before) |
| Duplicate fingerprint | Aborted | OK - skip duplicate MemoryEvent |
| Disk full | Aborted | Manual intervention needed |
| Connection lost | Aborted | Retry with exponential backoff |

**Data Consistency Guarantee**:
- ConversationMessage + MemoryEvent + ProjectMemoryProfile either all commit or all rollback
- No orphaned events
- ConversationState file (separate transaction) may be out of sync if database commits but filesystem fails

**Gap Analysis**:
- ✅ Transaction-level consistency
- ✅ Foreign key integrity
- ❌ No cross-transaction consistency between DB and filesystem
- ❌ ConversationState file might diverge from database

**Recommendation**:
1. Wrap DB + filesystem saves in try/except
2. If DB succeeds but filesystem fails, log warning + persist to failsafe queue
3. Implement eventual consistency reconciliation

---

### 1.3 Filesystem Write Failures

**Scenario**: ConversationState JSON file write fails

**Current Implementation**:
```python
def save_state(conv: Conversation, state: ConversationState) -> None:
    state_path = workspace_path(conv.project_id) / "conversation_state" / f"{conv.id}.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Direct write (not atomic)
    state_path.write_text(state.to_json(), encoding="utf-8")
```

**Failure Modes**:
1. **Directory doesn't exist**: `mkdir(parents=True)` creates it (safe)
2. **No write permission**: Exception raised, not caught
3. **Disk full**: `write_text()` raises OSError, not caught
4. **Path too long**: Exception raised, not caught
5. **Concurrent write**: Last write wins (race condition)

**Data Consistency Impact**:
- If write fails: ConversationState in memory ≠ ConversationState on disk
- Next load reads stale state → discovery progress lost
- Database state (ConversationMessage) is correct
- User might be asked same questions again

**Gap Analysis**:
- ❌ No atomic writes (not using temp file + rename)
- ❌ No exception handling
- ❌ No retry mechanism
- ❌ No validation after write
- ❌ Race condition with concurrent writes

**Recommendation**:
```python
def save_state(conv: Conversation, state: ConversationState) -> None:
    state_path = workspace_path(conv.project_id) / "conversation_state" / f"{conv.id}.json"
    
    try:
        # Atomic write
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = state_path.with_suffix('.json.tmp')
        temp_path.write_text(state.to_json(), encoding='utf-8')
        temp_path.replace(state_path)  # Atomic on POSIX
        
        # Verify
        loaded = json.loads(state_path.read_text(encoding='utf-8'))
        assert loaded['schema_version'] == state.schema_version
        
    except Exception as exc:
        _LOG.error("save_state failed for %s: %s", conv.id, exc)
        # Fallback: store in Redis for eventual flush
        cache_service.set(f"conversation_state_backup:{conv.id}", state.to_json(), ttl_seconds=86400)
        raise
```

---

### 1.4 Stale Turn Detection

**Current Implementation**:
```python
_STALE_AFTER = timedelta(minutes=15)

@router.get("/{pid}/conversation/turns/{turn_id}")
def get_project_conversation_turn(...) -> dict:
    turn = db.get(ConversationTurn, turn_id)
    
    if turn.status == "running" and ist_now() - turn.created_at > _STALE_AFTER:
        return {
            "status": "failed",
            "status_code": 503,
            "response": {"detail": "The reply was interrupted. Please send the message again."}
        }
```

**Data Consistency**:
- ✅ Detects abandoned tasks
- ⚠️ Worker thread still running (cleanup via `.pop(_LIVE_PHASE)` in finally block)
- ⚠️ ConversationMessage not persisted if stale
- ❌ No data cleanup (orphaned ConversationTurn row)

**Gap Analysis**:
- ✅ Graceful timeout detection
- ❌ No cleanup of orphaned ConversationTurn rows
- ❌ No cleanup of partial _LIVE_PHASE entries
- ❌ No alert/logging of stale turns

**Recommendation**:
1. Add daily cleanup job to delete ConversationTurn rows with status="running" and age > 1 day
2. Log stale turn as warning (indicates infrastructure issue)
3. Implement circuit breaker if stale rate exceeds threshold

---

## 2. Concurrency Control & Race Conditions

### 2.1 Simultaneous Discovery Updates

**Scenario**: User sends two discovery answers rapidly

**Race Condition**:
```
Thread A: Load ProjectMemoryProfile (v1)
Thread B: Load ProjectMemoryProfile (v1)         ← Race starts
Thread A: Update slots["audience"] = "finance"
Thread B: Update slots["timeline"] = "Q4"        ← Overwrite risk
Thread A: Save ProjectMemoryProfile (v1 → v2)
Thread B: Save ProjectMemoryProfile (v1 → v2)   ← B overwrites A's changes
```

**Current Protection**:
```python
def record_discovery_answer(session, *, project_id, user_id, slot_key, value):
    # SELECT FOR UPDATE (row-level lock on PostgreSQL, table lock on SQLite)
    row, summary = _load_profile_for_update(session, project_id=project_id)
    
    # Modify
    block = _normalize_user_profile(summary, user_id)
    slots = block["aggregated_slots"]
    slots[slot_key] = value
    
    # Save
    _save_profile(session, project_id=project_id, row=row, payload=summary)
    session.flush()  # Lock released after flush
```

**Locking Behavior**:

| Database | Lock Type | Scope | Duration |
|----------|-----------|-------|----------|
| SQLite | Table lock | Entire ProjectMemoryProfile table | Until COMMIT |
| PostgreSQL | Row lock | Single ProjectMemoryProfile row | Until COMMIT |
| SQLite (WAL) | Row lock | Optimistic (MVCC) | Better concurrency |

**Data Consistency Guarantee**:
- ✅ Serializable isolation (no lost updates)
- ✅ Two rapid updates both persisted
- ⚠️ SQLite with disabled WAL has table-level lock (blocks all projects)
- ⚠️ Deadlock risk if circular dependencies

**Gap Analysis**:
- ✅ SELECT FOR UPDATE prevents lost updates
- ⚠️ No deadlock detection or timeout
- ⚠️ No metrics on lock contention
- ⚠️ SQLite performance degradation under high concurrency

**Recommendation**:
1. Enable SQLite WAL (Write-Ahead Logging) for row-level locking
2. Add lock timeout: `session.execute(text("SET lock_timeout TO '5s'"))` (PostgreSQL)
3. Monitor lock_wait_time metric
4. Implement lock timeout fallback (retry with exponential backoff)

---

### 2.2 Fingerprint Deduplication

**Scenario**: Same discovery answer sent twice

**Deduplication Strategy**:
```python
def _append_event_if_possible(session, *, project_id, event_type, payload):
    run_id = _latest_project_run_id(session, project_id=project_id)
    
    # Create canonical fingerprint
    canonical = json.dumps(payload, sort_keys=True)
    fingerprint = sha256(f"{project_id}|{run_id}|{event_type}|{canonical}".encode()).hexdigest()
    
    # Check for duplicate
    existing = session.scalar(
        select(MemoryEvent).where(
            MemoryEvent.project_id == project_id,
            MemoryEvent.run_id == run_id,
            MemoryEvent.event_type == event_type,
            MemoryEvent.fingerprint == fingerprint,
        )
    )
    
    if existing:
        metrics.increment("memory_events_deduped_total")
        return  # Skip insert
    
    session.add(MemoryEvent(..., fingerprint=fingerprint, ...))
```

**Data Consistency**:
- ✅ No duplicate discoveries recorded
- ✅ Fingerprint = SHA256(project_id | run_id | event_type | payload)
- ✅ Canonical JSON ensures consistent hashing

**Edge Cases**:

| Scenario | Input | Hash | Deduplicated |
|----------|-------|------|--------------|
| Exact duplicate | `{"slot": "audience", "value": "finance"}` twice | Same | YES ✅ |
| JSON ordering | `{"a": 1, "b": 2}` vs `{"b": 2, "a": 1}` | Same (sort_keys=True) | YES ✅ |
| Whitespace | `"finance"` vs `" finance "` | Different | NO ❌ |
| Type mismatch | `"finance"` (str) vs `finance` (var) | Different | NO ❌ |

**Gap Analysis**:
- ✅ Deduplication works for exact duplicates
- ❌ No value normalization (whitespace, case)
- ❌ No semantic deduplication (synonyms)
- ⚠️ High fingerprint collision risk if payload not canonicalized

**Recommendation**:
1. Normalize slot values before hashing:
   ```python
   normalized_value = (value or "").strip().lower()
   ```
2. Add validation: `assert isinstance(payload, dict)`
3. Document fingerprint collision detection

---

### 2.3 ConversationState File Race Conditions

**Scenario**: Concurrent load_state() and save_state()

**Current Implementation**:
```python
def load_state(conv: Conversation) -> ConversationState:
    state_path = workspace_path(conv.project_id) / "conversation_state" / f"{conv.id}.json"
    
    if not state_path.exists():
        return default_state()
    
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        # No locking!
    except Exception:
        return default_state()
```

**Race Condition**:
```
Writer:                          Reader:
1. save_state()
2. Write temp file
3. Rename (atomic)               4. read_text() ← May read partial write
                                 5. json.loads() ← May fail on invalid JSON
```

**Data Inconsistency**:
- Reader may get partial JSON
- Reader may get stale state from before rename
- Reader may get OSError if file deleted between exists() and read_text()

**Gap Analysis**:
- ❌ No file locking (no flock() or fcntl.flock())
- ❌ No read-write synchronization
- ❌ No atomic read-then-validate
- ⚠️ File rename is atomic on POSIX but not Windows

**Data Consistency Impact**:
- Low: Reader gets default_state() if JSON parse fails (safe fallback)
- Medium: Writer's changes may be missed on older state
- High: Multiple concurrent writers can create divergent states

**Recommendation**:
```python
import fcntl

def load_state(conv: Conversation) -> ConversationState:
    state_path = workspace_path(conv.project_id) / "conversation_state" / f"{conv.id}.json"
    
    if not state_path.exists():
        return default_state()
    
    try:
        # Shared lock (multiple readers, exclusive writer)
        with open(state_path, 'r') as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                payload = json.loads(f.read())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        
        # Validate
        if not isinstance(payload, dict) or payload.get('schema_version') < 1:
            return default_state()
        
        return ConversationState(...)
    except Exception as exc:
        _LOG.warning("load_state failed, returning default: %s", exc)
        return default_state()

def save_state(conv: Conversation, state: ConversationState) -> None:
    state_path = workspace_path(conv.project_id) / "conversation_state" / f"{conv.id}.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Atomic write with lock
    temp_path = state_path.with_suffix('.json.tmp')
    try:
        with open(temp_path, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(state.to_json())
                f.flush()
                os.fsync(f.fileno())  # Ensure disk write
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        
        # Atomic rename
        temp_path.replace(state_path)
    except Exception as exc:
        _LOG.error("save_state failed: %s", exc)
        raise
```

---

## 3. Data Consistency & Integrity

### 3.1 Transaction Boundaries

**Critical Transaction**: Recording user message + updating memory

```python
with session.begin():  # Start transaction
    # 1. Add user message to ConversationMessage
    user_msg = ConversationMessage(
        conversation_id=conv.id,
        role="user",
        content=content,
        metadata_json="{}"
    )
    session.add(user_msg)
    session.flush()
    
    # 2. Extract and record discovery
    slots = _extract_discovery_answers(content, state)
    for slot_key, value in slots.items():
        record_discovery_answer(
            session,
            project_id=pid,
            user_id=user.id,
            slot_key=slot_key,
            value=value
        )
        # ^ record_discovery_answer():
        #   - Loads ProjectMemoryProfile (with lock)
        #   - Updates in-memory summary
        #   - Saves ProjectMemoryProfile
        #   - Appends MemoryEvent
    
    # 3. Add assistant response
    asst_msg = ConversationMessage(
        conversation_id=conv.id,
        role="assistant",
        content=llm_response,
        metadata_json=json.dumps({"tokens_used": {...}})
    )
    session.add(asst_msg)
    
    session.commit()  # All-or-nothing
```

**Atomicity Guarantee**:
- ✅ All 3 operations commit together
- ✅ No partial writes
- ✅ Rollback on any failure

**Consistency Guarantee**:
- ✅ Foreign key constraints checked before commit
- ✅ Unique constraints (e.g., fingerprint) checked before commit
- ✅ ProjectMemoryProfile row lock ensures isolated update

**Isolation Guarantee**:
- ✅ Concurrent transactions don't see uncommitted data
- ✅ MemoryEvent fingerprint dedup checked during commit
- ⚠️ SQLite uses SERIALIZABLE by default (no dirty reads)
- ⚠️ PostgreSQL may allow READ_COMMITTED (potential dirty reads)

**Gap Analysis**:
- ✅ Good transaction design
- ⚠️ Large transaction (multiple operations) increases lock contention
- ⚠️ No explicit isolation level specified
- ⚠️ No savepoints for partial rollback

**Recommendation**:
1. Set explicit isolation level: `ALTER SESSION SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;`
2. Add transaction timeout: `session.connection().timeout = 30` seconds
3. Break into smaller transactions if needed:
   ```python
   # T1: Add message
   session.commit()
   
   # T2: Record discovery
   session.commit()
   
   # T3: Add response
   session.commit()
   ```

---

### 3.2 Foreign Key Integrity

**Schema**:
```sql
CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY,
    conversation_id STRING NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role STRING NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE memory_events (
    id INTEGER PRIMARY KEY,
    project_id STRING NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    run_id STRING NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    event_type STRING NOT NULL,
    fingerprint STRING NOT NULL,
    payload TEXT NOT NULL
);
```

**Cascading Deletes**:

| Delete | Cascade Effect |
|--------|-----------------|
| DELETE FROM conversations | ConversationMessage rows deleted |
| DELETE FROM projects | ConversationMessage, MemoryEvent, MemoryItem rows deleted |
| DELETE FROM runs | MemoryEvent rows deleted |

**Data Consistency**:
- ✅ No orphaned ConversationMessage rows
- ✅ No orphaned MemoryEvent rows
- ⚠️ Cascading deletes can be slow for large conversations
- ⚠️ No soft-delete option for audit trail

**Gap Analysis**:
- ✅ Referential integrity maintained
- ❌ No audit trail for deleted messages
- ❌ No soft-delete for compliance/recovery
- ⚠️ No constraint names (hard to debug)

**Recommendation**:
1. Add soft-delete column: `is_deleted BOOLEAN DEFAULT false`
2. Modify cascades to set soft-delete instead of hard-delete
3. Add audit table for deleted records:
   ```sql
   CREATE TABLE conversation_message_audit (
       id INTEGER PRIMARY KEY,
       message_id INTEGER,
       conversation_id STRING,
       deleted_by STRING,
       deleted_at DATETIME,
       reason STRING
   );
   ```

---

### 3.3 Schema Versioning

**Current Approach**:
```python
class ConversationState:
    schema_version: int = 2  # Hard-coded
    
def load_state(conv: Conversation) -> ConversationState:
    try:
        payload = json.loads(state_path.read_text())
        schema_version = int(payload.get("schema_version") or 2)
        
        # No migration logic!
        if schema_version < 2:
            return default_state()  # Discard old state
    except Exception:
        return default_state()
```

**Version History**:
- v1: Original schema (missing history_summary)
- v2: Added history_summary field

**Data Loss Risk**:
- ✅ v1 → v2 migration: Auto-defaults missing field to ""
- ⚠️ No v2 → v1 downgrade (breaks if older code reads new schema)
- ❌ No migration logging

**Gap Analysis**:
- ⚠️ No explicit migration function
- ❌ No backward compatibility layer
- ❌ No forward compatibility (old code can't read new schema)
- ⚠️ Silent data discard on mismatch

**Recommendation**:
```python
def migrate_conversation_state(payload: dict, from_version: int, to_version: int = _SCHEMA_VERSION) -> dict:
    """Migrate ConversationState JSON from old to new schema."""
    
    if from_version == to_version:
        return payload
    
    if from_version == 1 and to_version >= 2:
        # Add missing history_summary field
        payload.setdefault("history_summary", "")
        _LOG.info("Migrated ConversationState from v1 to v2")
    
    if from_version == 2 and to_version >= 3:
        # Example: v3 adds new field
        payload.setdefault("engagement_metadata", {})
        _LOG.info("Migrated ConversationState from v2 to v3")
    
    return payload

def load_state(conv: Conversation) -> ConversationState:
    state_path = workspace_path(conv.project_id) / "conversation_state" / f"{conv.id}.json"
    
    if not state_path.exists():
        return default_state()
    
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        schema_version = int(payload.get("schema_version") or 1)
        
        # Migrate if needed
        if schema_version < _SCHEMA_VERSION:
            payload = migrate_conversation_state(payload, schema_version, _SCHEMA_VERSION)
            # Optionally save migrated version
            state_path.write_text(json.dumps(payload), encoding="utf-8")
        
        return ConversationState(
            schema_version=_SCHEMA_VERSION,
            state=str(payload.get("state") or "new").strip().lower(),
            slots=payload.get("slots") or {},
            # ... other fields
        )
    
    except Exception as exc:
        _LOG.warning("load_state failed (schema_version=%s): %s", schema_version, exc)
        return default_state()
```

---

## 4. Memory Performance & Optimization

### 4.1 Database Indexing Strategy

**Indexes Present**:
```sql
-- conversation_messages
CREATE INDEX idx_conversation_id ON conversation_messages(conversation_id);
CREATE INDEX idx_source_type ON conversation_messages(source_type);
CREATE INDEX idx_created_at ON conversation_messages(created_at);

-- memory_events
CREATE INDEX idx_memory_project_id ON memory_events(project_id);
CREATE INDEX idx_memory_run_id ON memory_events(run_id);
CREATE INDEX idx_memory_fingerprint ON memory_events(fingerprint);

-- memory_items
CREATE INDEX idx_memory_item_project_id ON memory_items(project_id);
CREATE INDEX idx_memory_item_type ON memory_items(memory_type);
CREATE INDEX idx_memory_item_principal_id ON memory_items(principal_id);
```

**Query Analysis**:

| Query | Index Used | Est. Time | Comment |
|-------|-----------|-----------|---------|
| Get recent messages for conv | idx_conversation_id | O(log N) | Fast, returns last 40 |
| Find old messages (>72h) | idx_created_at | O(log N) | Fast, used for cleanup |
| Deduplicate MemoryEvent | idx_fingerprint | O(log N) | Fast, critical path |
| Filter by principal_id | idx_principal_id | O(log N) | Fast, consent check |
| Get all items for project | idx_project_id | O(log N) | Fast, but can return many |

**Gap Analysis**:
- ✅ Key queries indexed
- ⚠️ No composite indices (e.g., (conversation_id, created_at))
- ⚠️ No partial indices (e.g., WHERE is_archived = false)
- ❌ No index on Conversation.project_id (assumed primary access)

**Recommendation**:
```sql
-- Composite indices for common access patterns
CREATE INDEX idx_conv_messages_order 
    ON conversation_messages(conversation_id, created_at DESC);

-- Partial index for active memories
CREATE INDEX idx_memory_items_active
    ON memory_items(project_id, memory_type)
    WHERE is_archived = false;

-- Multicolumn index for consent checks
CREATE INDEX idx_memory_consent
    ON memory_items(project_id, principal_id)
    WHERE consent_state IN ('allowed', '');
```

---

### 4.2 Query Optimization

**High-Volume Query**: Get last N messages with digest
```python
# CURRENT (N+1 problem potential)
messages = session.scalars(
    select(ConversationMessage)
    .where(ConversationMessage.conversation_id == cid)
    .order_by(ConversationMessage.created_at.desc())
    .limit(40)
).all()

# Time: O(log N) index seek + O(40) scan + O(40) object creation
# Memory: 40 ConversationMessage objects in memory
```

**Optimization**: Batch query with joins (if needed)
```python
# OPTIMIZED (if needing related data)
from sqlalchemy import func

messages = session.scalars(
    select(ConversationMessage)
    .where(ConversationMessage.conversation_id == cid)
    .order_by(ConversationMessage.created_at.desc())
    .limit(40)
    .options(joinedload(ConversationMessage.conversation))  # Eager load if needed
).unique().all()

# Time: Same, but avoids N+1 if accessing conversation later
```

**Cache Strategy**:
```python
# Current: No caching
# Proposed: Redis cache recent messages
cache_key = f"conversation_messages:{cid}:recent"
cached = cache_service.get(cache_key)

if cached:
    return cached  # O(1)

messages = fetch_from_db()
cache_service.set(cache_key, messages, ttl_seconds=300)  # 5 min cache
return messages
```

**Gap Analysis**:
- ⚠️ No query result caching
- ⚠️ Full table scans for memory item retrieval
- ✅ Correct use of pagination (LIMIT)
- ⚠️ No explain plan analysis

**Recommendation**:
1. Add query result caching for message retrieval (5 min TTL)
2. Use explain/analyze to identify slow queries
3. Profile message query latency during load tests

---

## 5. Edge Cases in Memory

### 5.1 Very Long Conversations (10K+ messages)

**Problem**: Memory digest can exceed token budget

**Current Behavior**:
```python
# build_conversation_digest_for_run()
limit = max(1, min(80, int(message_limit)))  # Max 80 messages

rows = session.scalars(
    select(ConversationMessage)
    .where(ConversationMessage.conversation_id == cid)
    .order_by(ConversationMessage.created_at.desc())
    .limit(limit)  # Fetch last 80
).all()
```

**Edge Case Analysis**:
- **10K messages, limit=80**: Fetches last 80 (newest)
- **Problem**: Loses early discovery context (maybe first 1K messages)
- **Impact**: LLM doesn't see how conversation started

**Tiered Compaction Behavior**:
```python
# Stage 1: Keep recent messages (newest 80)
# Stage 2: Drop fragments ("ok", "thanks")
# Stage 3: Snip oldest (keep last 30)
# Stage 4: Auto-summarize first N into single line
# Stage 5: Context-collapse (keep only last 5)

# For 10K message conversation:
# → Fetch 80 (newest)
# → Apply tiers → ~1,500-3,000 chars → Fits in digest
```

**Gap Analysis**:
- ❌ Loses early context in very long conversations
- ⚠️ No sampling of older messages
- ⚠️ No conversation history segmentation
- ⚠️ No sliding window analysis

**Recommendation**:
```python
def build_intelligent_digest(session, conversation_id, char_cap):
    """Sample from full conversation, not just recent."""
    
    # Get total message count
    total_messages = session.scalar(
        select(func.count(ConversationMessage.id))
        .where(ConversationMessage.conversation_id == conversation_id)
    )
    
    if total_messages <= 80:
        # All messages fit, use all
        rows = fetch_all_messages()
    else:
        # Sample: first 5 + middle 5 + last 70
        first = session.scalars(...ORDER BY created_at ASC LIMIT 5).all()
        middle_offset = total_messages // 2 - 2
        middle = session.scalars(...ORDER BY created_at ASC LIMIT 5 OFFSET middle_offset).all()
        recent = session.scalars(...ORDER BY created_at DESC LIMIT 70).all()
        
        rows = first + middle + recent
    
    return compact_digest(rows, char_cap)
```

---

### 5.2 Rapid Message Sending (5 messages/second)

**Scenario**: User sends 5 messages in quick succession

**Current Behavior**:
```
T=0ms:  Msg 1 arrives → queue_turn(1)
T=200ms: Msg 2 arrives → queue_turn(2)  [Turn 1 still processing]
T=400ms: Msg 3 arrives → queue_turn(3)  [Turn 1 still processing]
T=600ms: Turn 1 completes → save state
T=800ms: Msg 4 arrives → load_state() reads stale state (from T=600ms, missing Msgs 2-3)
T=1000ms: Turn 2 completes → overwrite state with outdated version
```

**Race Condition**:
- Msg 2 & 3 processed in parallel, state may diverge
- Discovery slots from Msg 2 might be lost if Turn 3 completes first

**Data Loss Risk**:
- ⚠️ Medium: Slot extraction for Msg 2 might be overwritten
- ⚠️ Messages always saved to DB (safe)
- ⚠️ ConversationState file may be out of sync

**Gap Analysis**:
- ❌ No message queueing (processes all in parallel)
- ❌ No ordering guarantee
- ⚠️ ThreadPoolExecutor with max_workers=8 allows parallel processing
- ❌ No conflict resolution if state diverges

**Recommendation**:
```python
# Option 1: Sequential processing per conversation
# (Use a per-conversation lock)

conversation_locks: dict[str, threading.Lock] = {}

def get_conversation_lock(conv_id: str) -> threading.Lock:
    if conv_id not in conversation_locks:
        conversation_locks[conv_id] = threading.Lock()
    return conversation_locks[conv_id]

def start_turn(pid, body, user, db):
    conv = get_conversation(pid, body.conversation_id)
    
    # Acquire lock (serialize per conversation)
    with get_conversation_lock(conv.id):
        # Process message sequentially
        return _answer_turn_impl(...)

# Option 2: Use per-conversation queue
from queue import Queue

conversation_queues: dict[str, Queue] = {}

def queue_message_for_conversation(conv_id: str, msg: dict):
    if conv_id not in conversation_queues:
        conversation_queues[conv_id] = Queue()
        # Start worker thread
        _EXECUTOR.submit(conversation_worker, conv_id)
    
    conversation_queues[conv_id].put(msg)
```

---

### 5.3 Timeout & Stale State Scenarios

**Scenario 1**: Server restarts while turn is processing

**Current**: _LIVE_PHASE lost (in-memory dict)

**Data Consistency**:
- ConversationTurn.status = "running" (persisted)
- ConversationTurn.response_json = "" (no response saved)
- ConversationState file = stale
- Discovery progress = lost

**Recovery**:
```python
# On startup, recover stuck turns
def recover_stuck_turns(max_age_minutes=15):
    stuck = session.scalars(
        select(ConversationTurn).where(
            ConversationTurn.status == "running",
            ConversationTurn.created_at < (now() - timedelta(minutes=max_age_minutes))
        )
    ).all()
    
    for turn in stuck:
        turn.status = "failed"
        turn.response_json = json.dumps({
            "detail": "Server restart interrupted processing. Please try again."
        })
    
    session.commit()
```

**Gap Analysis**:
- ❌ No recovery logic implemented
- ❌ No startup cleanup of stuck turns
- ⚠️ Users see "running" status forever until timeout (15 min)

---

## 6. Data Isolation & Consent

### 6.1 Project & User Isolation

**Current Implementation**:
```python
# All queries filter by project_id + user_id (via Membership check)

# Get conversation (must own project)
conv = session.scalar(
    select(Conversation)
    .where(
        Conversation.id == conv_id,
        Conversation.project_id == pid  # Project isolation
    )
)

# Get messages (must have access to conversation)
require_project_role(pid, {"Owner", "Editor", "Viewer"}, user, db)

messages = session.scalars(
    select(ConversationMessage)
    .where(ConversationMessage.conversation_id == conv.id)  # Conversation isolation
)
```

**Isolation Guarantee**:
- ✅ User can only access projects they're member of
- ✅ User can only see conversations in their projects
- ✅ User can only see messages in conversations they own
- ✅ No cross-project data leakage

**Gap Analysis**:
- ✅ Good multi-tenant isolation
- ⚠️ No field-level access control (all members see all data)
- ⚠️ No audit logging for data access
- ⚠️ No redaction for sensitive slots (e.g., budget, salary)

**Recommendation**:
```python
# Field-level redaction
def redact_sensitive_slots(slots: dict, user_role: str) -> dict:
    """Redact sensitive information based on user role."""
    
    sensitive_keys = ["budget", "salary", "confidential_info"]
    
    if user_role == "Viewer":
        # Viewers can't see budget/salary
        return {k: v for k, v in slots.items() if k not in sensitive_keys}
    
    return slots  # Owner/Editor see everything

# Usage
state.slots = redact_sensitive_slots(state.slots, user.role)
```

---

### 6.2 DPDP Consent Enforcement

**Current Implementation**:
```python
def memory_item_allowed_for_use(item, respect_consent=True, enforce_consent_ledger=True):
    # Tier 1: Field-level consent_state
    if respect_consent:
        cs = (item.consent_state or "").strip().lower()
        if cs not in ("allowed", ""):
            return False, "consent_field"
    
    # Tier 2: Consent ledger (principal_id)
    if enforce_consent_ledger:
        principal = (item.principal_id or "").strip()
        if principal and not consent_ledger_latest_granted(session, project_id, principal):
            return False, "consent_ledger"
    
    return True, ""
```

**Consent Ledger Lookup**:
```python
def consent_ledger_latest_granted(session, project_id, principal_id) -> bool:
    row = session.scalar(
        select(ConsentLedger)
        .where(
            ConsentLedger.project_id == project_id,
            ConsentLedger.principal_id == principal_id
        )
        .order_by(ConsentLedger.created_at.desc())
        .limit(1)
    )
    return bool(row.granted) if row else False
```

**Data Filtering**:
```python
# Get allowed memory items for context
allowed_items = []
for item in memory_items:
    allowed, skip_reason = memory_item_allowed_for_use(item, respect_consent=True, enforce_consent_ledger=True)
    if allowed:
        allowed_items.append(item)
    else:
        metrics.increment(f"memory_items_{skip_reason}_total")
```

**Gap Analysis**:
- ✅ Two-tier consent model implemented
- ✅ Consent ledger checked before use
- ✅ Metrics track blocked items
- ⚠️ No audit logging of consent decisions
- ⚠️ No bulk erasure when consent revoked
- ⚠️ No consent timeline visualization

**Recommendation**:
```python
def revoke_principal_consent(session, project_id, principal_id, reason: str):
    """Revoke all access for a principal (DPDP erasure request)."""
    
    # 1. Record revocation in consent ledger
    session.add(ConsentLedger(
        project_id=project_id,
        principal_id=principal_id,
        purpose="bulk_revocation",
        granted=False,
        revoked_at=ist_now(),
        reason=reason
    ))
    
    # 2. Archive all memory items for this principal
    session.execute(
        update(MemoryItem)
        .where(
            MemoryItem.project_id == project_id,
            MemoryItem.principal_id == principal_id
        )
        .values(is_archived=True, consent_state="revoked")
    )
    
    # 3. Audit log
    _LOG.info("Principal consent revoked: project_id=%s, principal=%s, reason=%s", 
              project_id, principal_id, reason)
    
    session.commit()
```

---

## 7. Schema & Data Versioning

### 7.1 ConversationMessage Schema Evolution

**Current Schema** (v1):
```sql
CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY,
    conversation_id STRING NOT NULL,
    role STRING NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    source_type STRING,
    source_freshness_at DATETIME,
    created_at DATETIME NOT NULL
);
```

**Potential Schema Changes**:

| Version | Change | Migration | Impact |
|---------|--------|-----------|--------|
| v1 | Original | N/A | Current |
| v2 | Add `edited_at` | backfill NULL | New field, optional |
| v3 | Add `embedding` | NULL initially | Vector search support |
| v4 | Drop `metadata_json` | Extract to metadata_items table | Normalization |
| v5 | Add `content_hash` | Compute from content | Deduplication |

**Migration Safety**:
- ✅ Backward compatible (old code reads new schema)
- ⚠️ Forward compatibility uncertain (old code may not handle new fields)
- ⚠️ No rollback plan

**Gap Analysis**:
- ❌ No Alembic migrations for schema changes
- ❌ No version tracking
- ❌ No rollback strategy
- ⚠️ Manual SQL for schema changes (error-prone)

**Recommendation**:
```bash
# Initialize Alembic
alembic init alembic

# Create migration for new column
alembic revision --autogenerate -m "Add edited_at to conversation_messages"

# Review generated migration (alembic/versions/001_*.py)
# Then apply
alembic upgrade head
```

---

## 8. Data Lifecycle & Cleanup

### 8.1 Message Retention Policy

**Current Policy**:
```
ConversationMessage: Indefinite (never deleted)
ConversationTurn: 15 min (detected stale, not cleaned up)
ConversationState file: Indefinite (until conversation deleted)
```

**Data Growth**:
```
Assumptions:
- 1,000 projects
- 100 conversations per project
- 50 messages per conversation
- Average message size: 500 bytes

Total storage:
= 1,000 * 100 * 50 * 500 bytes
= 2.5 billion bytes
= 2.5 GB (messages only, excludes metadata)

Growth rate (new messages):
= 1,000 * 100 * 10 messages/day (estimate)
= 1M messages/day
= 500 MB/day message storage
```

**Retention Impact**:
- After 1 year: ~180 GB for messages alone
- Database bloat, slower queries
- Backup size increases

**Gap Analysis**:
- ❌ No message archival policy
- ❌ No cleanup of stale ConversationTurn rows
- ⚠️ No retention configuration
- ❌ No audit trail for deleted messages

**Recommendation**:
```python
# Config
CONVERSATION_MESSAGE_RETENTION_DAYS = 365  # 1 year
CONVERSATION_TURN_RETENTION_HOURS = 24     # 1 day

def cleanup_old_conversations():
    """Daily cleanup of old data."""
    
    # 1. Archive old messages (soft delete)
    cutoff = ist_now() - timedelta(days=CONVERSATION_MESSAGE_RETENTION_DAYS)
    
    archived = session.execute(
        update(ConversationMessage)
        .where(ConversationMessage.created_at < cutoff)
        .values(is_archived=True)
    ).rowcount
    
    _LOG.info("Archived %d old messages", archived)
    
    # 2. Hard delete stale turns
    cutoff_turn = ist_now() - timedelta(hours=CONVERSATION_TURN_RETENTION_HOURS)
    
    deleted = session.execute(
        delete(ConversationTurn)
        .where(
            ConversationTurn.status.in_(["done", "failed"]),
            ConversationTurn.updated_at < cutoff_turn
        )
    ).rowcount
    
    _LOG.info("Deleted %d stale turns", deleted)
    
    session.commit()
```

---

## 9. Data Loss Scenarios & Prevention

### Critical Data Loss Scenarios

| Scenario | Likelihood | Impact | Prevention |
|----------|-------------|--------|-----------|
| LLM call fails, no fallback | Low | Discovery progress lost | Implement fallback response |
| DB transaction fails | Low | All or nothing (safe) | Proper error handling |
| Filesystem write fails | Low | State diverges from DB | Atomic writes + backup queue |
| Concurrent writes race | Medium | Slot overwrite | SELECT FOR UPDATE locks |
| Stale turn cleanup | Low | User sees "running" forever | Implement cleanup job |
| Rapid message loss | Medium | Some slots overwritten | Sequential processing per conv |
| Conversation deletion | Low | All messages deleted | Soft delete + retention |
| Principal revocation | Low | Memory items exposed | Consent ledger check before use |

---

## 10. Monitoring & Alerting

### Key Metrics to Track

```python
# Data consistency
- memory_items_consent_skipped_total
- memory_items_ledger_blocked_total
- memory_events_deduped_total
- conversation_state_save_failures_total

# Performance
- conversation_message_retrieval_latency_ms
- memory_event_insert_latency_ms
- conversation_state_file_write_latency_ms

# Concurrency
- conversation_lock_wait_time_ms
- conversation_lock_contention_count
- simultaneous_turns_processing_count

# Errors
- llm_call_failures_total
- db_transaction_rollbacks_total
- filesystem_write_failures_total
- stale_turn_detections_total

# Data growth
- conversation_count_gauge
- total_conversation_messages_gauge
- memory_events_count_gauge
- memory_items_count_gauge

# Cleanup
- archived_messages_total
- deleted_stale_turns_total
- revoked_consents_total
```

---

## Summary Table: Gaps & Recommendations

| Area | Gap | Severity | Recommendation |
|------|-----|----------|-----------------|
| Error Handling | No retry on LLM fail | ⚠️ Medium | Add exponential backoff |
| Error Handling | No cleanup of stale turns | ⚠️ Medium | Daily cleanup job |
| Concurrency | No file locking on state | 🔴 High | Add fcntl.flock() |
| Concurrency | No message ordering guarantee | 🔴 High | Sequential per conversation |
| Consistency | No soft-delete support | ⚠️ Medium | Add is_deleted column |
| Consistency | No schema migration tool | 🔴 High | Implement Alembic |
| Performance | No message caching | ⚠️ Medium | Redis cache (5 min TTL) |
| Performance | No composite indices | ✅ Low | Add compound indices |
| Isolation | No field-level redaction | ⚠️ Medium | Redact sensitive slots |
| Consent | No bulk erasure on revocation | ⚠️ Medium | Batch archive items |
| Lifecycle | No message archival | 🔴 High | Set retention policy (1 year) |
| Monitoring | No data consistency metrics | ✅ Low | Add metric tracking |

---

## Conclusion

The conversation memory system has **solid fundamentals** but needs hardening in:
1. **Concurrency**: File locking and message ordering
2. **Data Lifecycle**: Retention policies and cleanup
3. **Error Recovery**: Retry logic and fallback strategies
4. **Compliance**: DPDP consent enforcement and audit trails

**Priority fixes**:
1. Add file locking (Critical)
2. Implement schema versioning (Critical)
3. Set message retention (High)
4. Add sequential processing per conversation (High)
5. Implement metrics & monitoring (Medium)
