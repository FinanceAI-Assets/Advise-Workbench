# Detailed Memory Management Architecture - Engagement Section

## 1. Memory Retrieval on Quadrant (Tiered Context Engine)

### **TieredContextEngine** (`src/memory/retrieval.py`)

The context assembly uses a **three-tier hierarchical retrieval system**:

```
Tier 0: CONTEXT.md + caller-provided style
   ↓
Tier 1: LP (Leading Practices) snippets
   ↓
Tier 2: Source document chunks (ranked by BM25)
   ↓
Output: ContextBundle (text + char_budget + metadata)
```

#### **BM25 Ranking Implementation**

```python
@dataclass
class _BM25Index:
    tokenized: list[list[str]]        # Tokenized chunks
    dl: list[int]                     # Document lengths
    avgdl: float                      # Average document length
    df: dict[str, int]                # Document frequency per token

# BM25 parameters
k1 = 1.5                              # Term saturation
b = 0.75                              # Length normalization
```

**Score Formula:**
```
BM25(q, D) = Σ IDF(qi) * (f(qi,D) * (k1+1)) / (f(qi,D) + k1*(1-b+b*|D|/avgdl))
```

#### **Cache Strategy for Retrieval**

**Parsed Document Cache:**
```python
_parsed_cache: dict[str, tuple[float, list[dict], _BM25Index]]
           # cache_key → (latest_mtime, chunks, precomputed_index)
```

- Key: `str(workspace_path(project_id) / "parsed_docs")`
- Invalidation: Mtime-based (directory mtime tracked)
- Behavior: Re-read only when any file in parsed_docs changes
- Recovery: Best-effort with `try/except` to skip corrupted JSON files

**Wiki Cache:**
```python
_wiki_cache: dict[str, tuple[float, list[str], _BM25Index]]
             # cache_key → (latest_mtime, wiki_chunks, index)
```

- Key: `str(workspace_path(project_id) / "wiki")`
- Invalidation: Mtime-based, stale prefix added if > 72 hours old
- Format: Each chunk prefixed with page title for provenance
- Filter: Excludes `index.md` and `log.md`

---

## 2. Token-Aware Context Budget

### **TokenBudgetChecker** (`src/llm/token_budgets.py`)

#### **Token Estimation**

```python
CHARS_PER_TOKEN = 3.5          # Empirical ratio (more accurate than /4)
SAFETY_MARGIN_TOKENS = 100     # Buffer for estimation errors
```

**Estimation Formula:**
```python
tokens = max(1, int(len(text) / 3.5))
```

#### **Prompt-Level Budget Checking**

```python
def check_budget(system: str, user: str, needed_output_tokens=4096, throw_on_exceed=False):
    remaining = get_remaining_budget()
    prompt_tokens = estimate_prompt_tokens(system, user)
    output_tokens = int(needed_output_tokens)
    total_needed = prompt_tokens + output_tokens + SAFETY_MARGIN_TOKENS
    
    compression_needed = max(0, total_needed - remaining)
    fits = compression_needed == 0
    
    return (fits, {
        'prompt_tokens': prompt_tokens,
        'output_tokens': output_tokens,
        'total_tokens_needed': total_needed,
        'remaining_budget': remaining,
        'compression_needed_tokens': compression_needed,
    })
```

**Usage:**
```python
fits, budget_info = TokenBudgetChecker.check_budget(
    system=system_prompt,
    user=user_prompt,
    needed_output_tokens=4096,
    throw_on_exceed=True  # Raises TokenBudgetExceeded if over budget
)
```

#### **Intelligent Prompt Compression** (5-tier strategy)

```python
def compress_prompt_for_budget(system, user, target_tokens, compression_strategy):
    """
    Compression tiers (in order):
    1. Trim verbose examples from system prompt
    2. Compress context excerpts to summaries
    3. Reduce user instruction to essentials
    4. Simplify structured data (ProcessModel JSON)
    5. Hard truncation with safety buffer
    """
```

### **Run-Level Token Budget** (`src/llm/run_budget.py`)

#### **Per-Run Budget Tracking** (Context-scoped)

```python
# ContextVar for thread-safe per-run tracking
_remaining: ContextVar[int | None] = ContextVar("run_llm_budget_remaining", default=None)
_active_usage: ContextVar[_RunTokenUsage | None] = ContextVar("run_active_usage", default=None)

class _RunTokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    
    def charge(self, **kwargs) -> None:
        # Thread-safe increment via Lock
        with self._lock:
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cache_read_tokens += cache_read_tokens
            self.cache_creation_tokens += cache_creation_tokens
```

#### **Run Budget Context Manager**

```python
@contextmanager
def run_llm_budget(max_tokens: int, *, run_id: str | None = None):
    usage = _RunTokenUsage()
    _active_usage.set(usage)
    
    # Register for live polling
    if run_id:
        _live_usage_registry[run_id] = usage
    
    try:
        _remaining.set(int(max_tokens))
        yield
    finally:
        _remaining.reset()
        _live_usage_registry.pop(run_id, None)
```

#### **Token Charging**

```python
def charge_llm_usage(*, input_tokens, output_tokens, cache_read_tokens=0, cache_creation_tokens=0):
    rem = _remaining.get()
    if rem is not None:
        used = input_tokens + output_tokens
        new_val = rem - used
        if new_val < 0:
            raise RunBudgetExceeded("Run LLM token budget exhausted")
        _remaining.set(new_val)
    
    usage = _active_usage.get()
    if usage is not None:
        usage.charge(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )
```

#### **Live Usage Polling**

```python
# Module-level registry for live polling during execution
_live_usage_registry: dict[str, _RunTokenUsage] = {}

def get_live_usage(run_id: str) -> dict[str, int] | None:
    usage = _live_usage_registry.get(run_id)
    return usage.snapshot() if usage else None
```

---

## 3. Conversation Compaction

### **TieredCompactor** (`src/memory/short_term/context_compaction.py`)

Progressive compression in 4 tiers until text fits character budget.

#### **Tier Architecture**

```python
class TieredCompactor:
    def __init__(self, *, per_message_chars: int = 600):
        self._per_message_chars = max(120, int(per_message_chars))
    
    def assemble(self, *, lines: list[CompactionLine], char_cap: int) -> tuple[str, CompactionTrace]:
        cap = max(200, int(char_cap))
        current = list(lines)
        original_len = self._joined_len(current)
        
        if original_len <= cap:
            return self._join(current, cap), trace  # No compression needed
        
        current = self._tier1_micro_compact(current, trace)
        if self._joined_len(current) > cap:
            current = self._tier2_snip_oldest(current, trace, keep_newest=120)
        if self._joined_len(current) > cap:
            current = self._tier3_auto_summary(current, trace)
        if self._joined_len(current) > cap:
            current = self._tier4_context_collapse(current, trace)
        
        return self._join(current, cap), trace
```

#### **Tier 1: Micro Compact**

- Drops conversation "fragments" matching: `/(ok|okay|thanks|sure|done)[.! ]*$/i`
- Truncates individual messages > 600 chars to 600 chars + "…"
- Preserves source_id for audit trail

```python
def _tier1_micro_compact(self, lines, trace):
    result = []
    for line in lines:
        if self._is_fragment(line.text):
            trace.drop_source("conversation_segments", line.source_id)
            continue
        if len(line.text) > self._per_message_chars:
            text = line.text[:self._per_message_chars] + "…"
        result.append(CompactionLine(source_id=line.source_id, text=text))
    return result
```

#### **Tier 2: Snip Oldest**

- Keeps only the newest 120 messages
- Drops everything older

```python
def _tier2_snip_oldest(self, lines, trace, keep_newest=120):
    if len(lines) <= keep_newest:
        return lines
    dropped = lines[: len(lines) - keep_newest]
    kept = lines[len(lines) - keep_newest:]
    for line in dropped:
        trace.drop_source("conversation_segments", line.source_id)
    return kept
```

#### **Tier 3: Auto Summary**

- Keeps latest 8 messages, summarizes older ones
- Summary: pipe-separated non-fragment messages from last 8, capped at 1200 chars

```python
def _tier3_auto_summary(self, lines, trace):
    if len(lines) <= 8:
        return lines
    head = lines[:-8]
    tail = lines[-8:]
    summary_bits = [line.text for line in tail if not self._is_fragment(line.text)]
    summary_text = " | ".join(summary_bits)[:1200].strip()
    for line in head:
        trace.drop_source("conversation_segments", line.source_id)
    return [CompactionLine(source_id="summary:last8", text=f"[summary]: {summary_text}"), *tail]
```

#### **Tier 4: Context Collapse**

- Keeps only latest 5 messages
- Adds explicit marker: `[context-collapse]: Preserved latest high-signal turns only...`

```python
def _tier4_context_collapse(self, lines, trace):
    keep = lines[-5:]
    dropped = lines[: len(lines) - len(keep)]
    for line in dropped:
        trace.drop_source("conversation_segments", line.source_id)
    collapse = CompactionLine(
        source_id="collapse:context",
        text="[context-collapse]: Preserved latest high-signal turns only. Older turns compacted to fit budget."
    )
    return [collapse, *keep]
```

#### **Compaction Trace**

```python
class CompactionTrace:
    original_char_count: int
    final_char_count: int
    tiers_applied: list[str]           # e.g., ["tier1_micro_compact", "tier2_snip_oldest"]
    dropped_sources: dict[str, list[str]]  # source_type → [source_ids dropped]
```

---

## 4. Persistent Memory Types

### **Memory Type Taxonomy**

| Type | Table | Scope | Retention | Primary Use |
|------|-------|-------|-----------|------------|
| **discovery_answer** | MemoryEvent | Run-scoped | 30 days | Discovery slots filled in conversation |
| **routing_decision** | MemoryEvent | Run-scoped | 30 days | Routing/planning decisions made |
| **preference** | MemoryItem | Project-scoped | Indefinite | User preferences (e.g., "use-pptx-style") |
| **constraint** | MemoryItem | Project-scoped | Indefinite | Operational constraints |
| **decision** | MemoryItem | Project-scoped | Indefinite | Past decisions to remember |
| **fact** | MemoryItem | Project-scoped | Indefinite | Facts about organization/domain |
| **aggregated_slots** | ProjectMemoryProfile | Project-scoped | Indefinite | Consolidated discovery answers |
| **decision_outcomes** | ProjectMemoryProfile | Project-scoped | Indefinite | Consolidated routing decisions |

### **MemoryEvent** (Short-term, Run-scoped)

```python
class MemoryEvent:
    id: int                           # Auto-increment
    project_id: str                   # FK (indexed)
    run_id: str                       # FK (indexed) - latest run
    event_type: str                   # "discovery_answer_recorded", "routing_decision_recorded"
    fingerprint: str(64)              # SHA256 dedup key (indexed)
    payload: Text                     # JSON: {"user_id", "slot_key", "value"} etc.
    created_at: DateTime              # (indexed)
```

**Retention:** 30 days (configurable `MEMORY_EVENTS_RETENTION_DAYS`)

**Deduplication:** Fingerprint = `sha256(project_id|run_id|event_type|canonical_json)`

### **MemoryItem** (Long-term, Project-scoped)

```python
class MemoryItem:
    id: str(64)
    project_id: str                   # FK (indexed)
    memory_type: str                  # "preference"|"constraint"|"decision"|"fact"
    key: str(128)                     # Knowledge key
    value: Text                       # Knowledge value
    confidence: str                   # "low"|"medium"|"high"
    source: str                       # "chat"|"document"|"system"
    consent_state: str                # "allowed"|"blocked"|etc
    principal_id: str(128) | None     # For DPDP Consent Ledger checks
    is_archived: bool                 # Soft delete flag
    created_at, updated_at: DateTime
```

**Unique Constraint:** `(project_id, memory_type, key)` — prevents duplicate knowledge

### **ProjectMemoryProfile** (Aggregated, Project-scoped)

```python
class ProjectMemoryProfile:
    project_id: str                   # PK, FK
    summary_json: Text                # Aggregated structure
    updated_at: DateTime
```

**Structure:**
```json
{
  "users": {
    "user-1": {
      "aggregated_slots": {
        "client": {"name": "Acme"},
        "outcome": {"primary": "..."},
        "win_themes": ["...", "..."]
      },
      "decision_outcomes": {
        "output_format": "pptx",
        "doc_style": "executive"
      },
      "updated_at": "2026-10-30T..."
    },
    "user-2": {...}
  }
}
```

### **UserProjectPreference** (Per-user, Project-scoped)

```python
class UserProjectPreference:
    user_id: str(64)                  # PK, FK
    project_id: str(64)               # PK, FK
    preferences_json: Text            # {"context_lines": [...], ...}
    updated_at: DateTime
```

**Structure:**
```json
{
  "context_lines": [
    "Prefers detailed technical documentation",
    "Focus on ROI metrics",
    "Use compliance-first approach"
  ]
}
```

---

## 5. Memory Write Pipeline

### **Discovery Answer Recording**

```python
def record_discovery_answer(
    session: Session,
    *,
    project_id: str,
    user_id: str,
    slot_key: str,
    value: Any,
) -> None:
    # Step 1: Load ProjectMemoryProfile with row-level lock (SELECT FOR UPDATE)
    row, summary = _load_profile_for_update(session, project_id=project_id)
    
    # Step 2: Normalize/ensure user block in summary
    block = _normalize_user_profile(summary, user_id)
    
    # Step 3: Update aggregated_slots[slot_key] = value
    slots = block["aggregated_slots"]
    slots[key] = value
    block["updated_at"] = _now_iso()
    
    # Step 4: Save profile back (insert or update)
    _save_profile(session, project_id=project_id, row=row, payload=summary)
    
    # Step 5: Append event (with fingerprint-based deduplication)
    _append_event_if_possible(
        session,
        project_id=project_id,
        event_type="discovery_answer_recorded",
        payload={"user_id": user_id, "slot_key": key, "value": value},
    )
```

### **Routing Decision Recording**

```python
def record_routing_decision(
    session: Session,
    *,
    project_id: str,
    user_id: str,
    decision_type: str,      # e.g., "output_format", "doc_style"
    confidence: float,       # 0.0 - 1.0
    value: Any,
) -> None:
    # Same pattern as discovery_answer but updates decision_outcomes instead
    block = _normalize_user_profile(summary, user_id)
    decision_block = block["decision_outcomes"]
    decision_block[decision_type] = {"value": value, "confidence": confidence}
    _save_profile(session, project_id=project_id, row=row, payload=summary)
    _append_event_if_possible(
        session,
        project_id=project_id,
        event_type="routing_decision_recorded",
        payload={"user_id": user_id, "decision_type": decision_type, "confidence": confidence, "value": value},
    )
```

### **Event Deduplication**

```python
def _append_event_if_possible(session, *, project_id, event_type, payload):
    # Get latest run for this project
    run_id = _latest_project_run_id(session, project_id=project_id)
    if not run_id:
        return  # No run context, skip event
    
    # Build fingerprint for deduplication
    canonical = json.dumps(payload, sort_keys=True)
    fingerprint = sha256(f"{project_id}|{run_id}|{event_type}|{canonical}".encode()).hexdigest()
    
    # Check if already exists
    existing = session.scalar(
        select(MemoryEvent).where(
            MemoryEvent.project_id == project_id,
            MemoryEvent.run_id == run_id,
            MemoryEvent.event_type == event_type,
            MemoryEvent.fingerprint == fingerprint,
        )
    )
    
    if existing:
        return  # Already recorded, skip
    
    # Create new event
    session.add(MemoryEvent(
        project_id=project_id,
        run_id=run_id,
        event_type=event_type,
        fingerprint=fingerprint,
        payload=canonical,
    ))
    session.flush()
```

### **Write Pipeline Transaction Guarantees**

1. **Row-level locks** on ProjectMemoryProfile (PostgreSQL `SELECT FOR UPDATE`)
2. **Fingerprint-based idempotency** for events
3. **Separate sessions** to prevent transaction interference
4. **Flush after each step** to ensure durability

---

## 6. Memory Lifecycle and Consent

### **Event Retention Policy**

```python
MEMORY_EVENTS_RETENTION_DAYS = 30  # Default, configurable via .env
```

**Pruning:**
- Background job runs on startup and periodically
- Deletes `MemoryEvent` rows with `created_at < NOW() - retention_days`
- Counter: `memory_events_pruned_total` (observability)

### **Consent Checking** (`src/memory/long_term/memory_consent.py`)

#### **Consent State Filtering**

```python
def memory_item_allowed_for_use(
    session: Session,
    project_id: str,
    item: MemoryItem,
    *,
    respect_consent: bool,
    enforce_consent_ledger: bool = False,
) -> tuple[bool, str]:
    """
    Returns:
        (True, "") — Use the item
        (False, "consent_field") — Blocked by consent_state
        (False, "consent_ledger") — Blocked by ledger check
    """
    
    # Check 1: consent_state field
    if respect_consent:
        cs = (item.consent_state or "").strip().lower()
        if cs not in ("allowed", ""):
            return (False, "consent_field")
    
    # Check 2: ConsentLedger row (if principal_id set)
    if enforce_consent_ledger and item.principal_id:
        ledger_row = session.scalar(
            select(ConsentLedger).where(
                ConsentLedger.project_id == project_id,
                ConsentLedger.principal_id == item.principal_id,
            ).order_by(ConsentLedger.created_at.desc()).limit(1)
        )
        if ledger_row is None or not ledger_row.granted:
            return (False, "consent_ledger")
    
    return (True, "")
```

#### **Configuration Flags**

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEMORY_RESPECT_CONSENT_IN_CONTEXT` | `true` | Check consent_state field |
| `MEMORY_ENFORCE_CONSENT_LEDGER` | `false` | Require ConsentLedger grant for principal_id holders |

**Behavior:**
- Both enabled: Check consent_state AND ConsentLedger
- Respect consent only: Check consent_state field only
- Both disabled: Load all items without consent checks

#### **MemoryItem Lifecycle**

```
Created (source=chat|document|system)
  ↓
Optional DPDP PII detection (future)
  ↓
Stored with consent_state=allowed (default)
  ↓
On use: Check consent_state AND optional ConsentLedger
  ↓
is_archived=true (soft delete, not removed from DB)
```

---

## 7. Memory Scope and Isolation

### **Project-Level Scope**

All memory queries scoped by `project_id`:

```python
# MemoryEvent
select(MemoryEvent).where(MemoryEvent.project_id == project_id)

# MemoryItem
select(MemoryItem).where(MemoryItem.project_id == project_id)

# ProjectMemoryProfile
select(ProjectMemoryProfile).where(ProjectMemoryProfile.project_id == project_id)

# UserProjectPreference
select(UserProjectPreference).where(UserProjectPreference.project_id == project_id)
```

### **User-Level Isolation** (via preferences)

```python
# UserProjectPreference scoped to (user_id, project_id)
select(UserProjectPreference).where(
    UserProjectPreference.user_id == user_id,
    UserProjectPreference.project_id == project_id,
)

# Discovery/Decision aggregation per user in ProjectMemoryProfile
profile["users"][user_id] = {
    "aggregated_slots": {...},
    "decision_outcomes": {...},
}
```

### **Run-Level Scope** (for MemoryEvent)

```python
# MemoryEvent tied to latest run
run_id = _latest_project_run_id(session, project_id=project_id)
event = MemoryEvent(
    project_id=project_id,
    run_id=run_id,          # Associates event with specific run
    event_type=...,
    payload=...,
)
```

### **Data Isolation Matrix**

| Resource | Scope | Isolation |
|----------|-------|-----------|
| MemoryEvent | project_id + run_id | Row-level (DB) |
| MemoryItem | project_id + (memory_type, key) | Unique constraint |
| ProjectMemoryProfile | project_id | Row-level lock |
| UserProjectPreference | (user_id, project_id) | Primary key |
| ConversationTurn | (project_id, user_id) | Index-based query |
| ConversationMessage | conversation_id | Foreign key |

---

## 8. Cache Key TTL and Invalidation

### **Redis Cache Service** (`src/core/cache.py`)

#### **Architecture**

```python
class CacheService:
    def __init__(self):
        self._mem: dict[str, tuple[float, str]] = {}  # In-memory fallback
        self._redis = Redis.from_url(settings.redis_url)  # Primary
    
    def get(self, key: str) -> dict | None:
        if self._redis:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        else:
            ent = self._mem.get(key)
            if not ent:
                return None
            exp_mono, raw = ent
            if time.monotonic() >= exp_mono:
                self._mem.pop(key, None)
                return None
            return json.loads(raw)
    
    def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        raw = json.dumps(value)
        if self._redis:
            self._redis.setex(key, ttl_seconds, raw)  # SET with expiration
        else:
            ttl = max(1, int(ttl_seconds))
            self._mem[key] = (time.monotonic() + float(ttl), raw)
```

#### **Fallback Strategy**

```
If Redis available:
    Primary: Redis (distributed, multi-process)
    ├─ SETEX key ttl_seconds value (expires automatically)
    └─ GET key returns value or nil
Else:
    Fallback: In-memory dict with monotonic clock
    ├─ Stores (expiration_monotonic_time, json_value)
    ├─ Check expiration on each get
    └─ Only works single-process
```

**Configuration:**
```bash
REDIS_URL=redis://localhost:6379/0
CACHE_ALLOW_MEMORY_FALLBACK=true   # Allow in-memory if Redis unavailable
                                    # false = fail-fast in multi-replica
```

### **File-Based Cache Invalidation** (Mtime-based)

#### **Parsed Document Cache**

```python
# Key pattern
cache_key = str(workspace_path(project_id) / "parsed_docs")

# Stored as
_parsed_cache[cache_key] = (latest_mtime, chunks, bm25_index)

# On next access
current_mtime = max(f.stat().st_mtime for f in parsed_dir.glob("*.json"))
if current_mtime != cached[0]:
    # Cache invalid, re-read all files
    chunks = [reload all .json files]
    _parsed_cache[cache_key] = (current_mtime, chunks, _build_bm25_index(chunks))
else:
    # Cache valid
    return cached[1]  # Use cached chunks
```

#### **Wiki Cache**

```python
# Similar pattern
_wiki_cache: dict[str, tuple[float, list[str], _BM25Index]]

# Stale detection
_WIKI_STALE_HOURS = 72
if now() - file.stat().st_mtime > 72 hours:
    chunk_text = "[STALE] " + chunk_text  # Mark as stale for LLM
```

### **Common Cache Keys** (Redis patterns)

```
conversation:{project_id}:{user_id}
  → Conversation usage tokens (input, output, cache_read, cache_creation)

parsed_docs:{project_id}
  → Parsed document chunks + BM25 index (TTL: until file change)

wiki:{project_id}
  → Wiki pages as context chunks (TTL: until file change)

preference:{user_id}:{project_id}
  → User preferences (TTL: 3600 seconds / 1 hour)

engagement_brief:{project_id}
  → Formatted engagement brief text (TTL: 1800 seconds / 30 min)
```

---

## 9. LLM Prompt Caching

### **Prompt Caching Mechanism** (`src/llm/providers/_common.py`)

Advise Workbench captures and tracks prompt caching tokens from Claude API:

```python
# Response structure includes cache metrics
usage = SimpleNamespace(
    input_tokens=int(...),
    output_tokens=int(...),
    cache_read_input_tokens=0,      # Tokens read from cache
    cache_creation_input_tokens=0,  # Tokens written to cache
)
```

#### **Cache Control Blocks**

Claude's prompt caching uses `cache_control` blocks on system prompts:

```python
# System prompt structure (implicit in Advise Workbench)
system_message = {
    "type": "text",
    "text": "[Long engagement brief and context]",
    "cache_control": {"type": "ephemeral"}  # Applied by SDK
}
```

**Cache Tiers:**
- **ephemeral**: Cache expires when conversation ends or after 5 min
- **static**: Cache persists for 5+ min, reused across calls

#### **Token Budget Impact**

```python
def charge_llm_usage(
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,           # Read from cache (cheaper)
    cache_creation_tokens: int = 0,       # Written to cache (expensive)
) -> None:
    # Budget tracking accounts for both fresh and cached tokens
    used_for_budget = input_tokens + output_tokens
    new_remaining = remaining_budget - used_for_budget
    if new_remaining < 0:
        raise RunBudgetExceeded()
    
    # Record all token types for observability
    usage.charge(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )
```

#### **Live Capture for Observability**

```python
# During conversation, capture cache metrics
@contextmanager
def capture_usage(key: str = f"conversation:{project_id}:{user_id}"):
    usage = _RunTokenUsage()
    _live_captures[key] = usage
    try:
        yield usage
    finally:
        _live_captures.pop(key, None)

# Query during active conversation
def get_live_capture(key: str) -> dict[str, int]:
    usage = _live_captures.get(key)
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_creation_tokens": usage.cache_creation_tokens,
    }
```

---

## 10. Run State and File Storage

### **Run Event Persistence** (`src/workflows/run_event_service.py`)

#### **Event Recording Pipeline**

```python
class RunEventService:
    def record_event(
        self,
        session: Session,
        *,
        run_id: str,
        event_type: str,
        payload_obj: Any,
    ) -> RunEvent:
        # Step 1: Build canonical event payload
        event_payload = build_event_payload(
            run_id=run_id,
            event_type=event_type,
            payload_obj=payload_obj,
        )
        
        # Step 2: Persist to database
        payload_str = json.dumps(event_payload)
        ev = RunEvent(run_id=run_id, event_type=event_type, payload=payload_str)
        session.add(ev)
        session.flush()
        
        # Step 3: Publish for SSE streaming
        self._publish_event(run_id, ev.id, event_type, payload_str)
        
        # Step 4: Log to Langfuse (optional tracing)
        langfuse_event(
            trace_id=run_id,
            name=f"run_event.{event_type}",
            metadata={"run_id": run_id, "payload": event_payload},
        )
        
        # Step 5: Create canonical aliases (alternative names for same event)
        for alias in canonical_event_aliases(event_type=event_type, payload=payload_obj):
            alias_payload = build_event_payload(run_id=run_id, event_type=alias, payload_obj=payload_obj)
            alias_ev = RunEvent(run_id=run_id, event_type=alias, payload=json.dumps(alias_payload))
            session.add(alias_ev)
            session.flush()
            self._publish_event(run_id, alias_ev.id, alias, alias_payload)
```

#### **Canonical Event Envelope** (schema v1)

```json
{
  "schema_version": "run-events-v1",
  "event_type": "coordinator_plan_generated",
  "phase": "planning",
  "ts_ms": 1698567000000,
  "run_id": "run-abc123",
  "payload": {
    "coordinator_plan": {...},
    "reasoning_excerpt": "...",
    "planned_outputs": [...]
  }
}
```

**Strict Contract** (when `EVENT_CONTRACT_STRICT=true`):
- All events MUST conform to this envelope
- Legacy payload flattening disabled
- Unknown event types rejected

### **File Storage** (Workspace Structure)

#### **Workspace Directory Layout**

```
workspace/{project_id}/
├── parsed_docs/                      # Source document JSON chunks
│   ├── doc1_sha256.json
│   ├── doc2_sha256.json
│   └── ...
├── wiki/                             # Project wiki (markdown)
│   ├── index.md
│   ├── process_overview.md
│   ├── integration_guidelines.md
│   └── ...
├── logs/                             # Audit trail
│   ├── wiki_operations.log
│   └── ...
├── conversation_state/               # Persistent conversation state
│   ├── {conversation_id}.json
│   └── ...
├── settings.json                     # Project-specific settings
└── [run outputs]                     # Generated artifacts
    ├── run-123_output.docx
    ├── run-123_output.pptx
    └── ...
```

#### **Conversation State File** (`conversation_state/{conversation_id}.json`)

```json
{
  "state": "discovery",
  "slots": {
    "client": {"name": "Acme Corp"},
    "outcome": {"primary": "Streamline operations"},
    "win_themes": ["Cost reduction", "Efficiency"]
  },
  "deliverable": "sop",
  "last_router": "output_format_router",
  "pending_questions": ["success_measures"],
  "history_summary": "User described pain points in current process...",
  "updated_at": "2026-10-30T14:30:00Z"
}
```

### **Run State Recovery**

```python
def load_resume_state(session: Session, *, run_id: str) -> dict[str, Any]:
    rows = session.scalars(
        select(RunEvent)
        .where(RunEvent.run_id == run_id)
        .order_by(RunEvent.id.asc())
    ).all()
    
    if not rows:
        return {
            "event_count": 0,
            "last_event_id": 0,
            "last_step_status": None,
        }
    
    by_type: dict[str, int] = {}
    last_status = None
    
    for ev in rows:
        by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1
        payload = json.loads(ev.payload)
        step_status = payload.get("payload", {}).get("status")
        if step_status:
            last_status = step_status
    
    return {
        "event_count": len(rows),
        "last_event_id": rows[-1].id,
        "last_step_status": last_status,
        "event_type_counts": by_type,
    }
```

---

## 11. Memory Observability

### **Metrics** (`src/core/observability/metrics.py`)

#### **Memory-Related Counters**

```python
# Memory item metrics
increment("memory_items_injected_into_context_total")       # Items merged into context
increment("memory_items_consent_skipped_total")             # Skipped due to consent_state
increment("memory_items_ledger_blocked_total")              # Blocked by ConsentLedger
increment("memory_batch_create_total")                      # Batch create operations

# Memory event metrics
increment("memory_events_written_total")                    # New events recorded
increment("memory_events_pruned_total")                     # Deleted by retention
increment("memory_events_deduped_total")                    # Deduplicated by fingerprint

# User preference metrics
increment("user_preference_learning_runs_bumped_total")     # Preference updates after runs
```

#### **Context Assembly Metrics**

```python
increment("coordinator_context_assemble_v2_total")         # Calls to assemble_v2
observe_latency("context_assembly_ms", duration)           # Assembly time histogram

# Per-agent context metrics
increment("subagent_context_offered_chars_narrative_total") # Offered chars (narrative)
increment("subagent_context_consumed_chars_narrative_total")# Consumed chars (narrative)
increment("subagent_context_truncated_total")              # Truncations due to cap
```

#### **Conversation Compaction Metrics**

```python
increment("conversation_digest_built_total")               # HITL digest created
increment("conversation_digest_tiered_compaction_total")   # Compaction applied
```

#### **Latency Histograms**

```python
observe_latency("context_retrieval_ms", duration)
observe_latency("memory_lookup_ms", duration)
observe_latency("consent_check_ms", duration)
observe_latency("conversation_compaction_ms", duration)
```

### **Prometheus Export** (`/metrics/prometheus`)

Metrics exposed in Prometheus text format:

```
# HELP memory_items_injected_into_context_total MemoryItem lines merged into assemble_v2 context.
# TYPE memory_items_injected_into_context_total counter
memory_items_injected_into_context_total 1247

# HELP memory_items_consent_skipped_total MemoryItem rows excluded due to consent_state.
# TYPE memory_items_consent_skipped_total counter
memory_items_consent_skipped_total 23

# HELP memory_events_written_total MemoryEvent rows appended.
# TYPE memory_events_written_total counter
memory_events_written_total 5634

# HELP context_assembly_ms Context assembly latency histogram.
# TYPE context_assembly_ms histogram
context_assembly_ms_bucket{le="100"} 1234
context_assembly_ms_bucket{le="500"} 4567
context_assembly_ms_bucket{le="1000"} 5432
```

### **Live Usage Polling**

```python
# During active conversation
def get_conversation_usage(project_id: str, user_id: str) -> dict:
    key = f"conversation:{project_id}:{user_id}"
    tokens = get_live_capture(key)
    return {
        "input_tokens": tokens["input_tokens"],
        "output_tokens": tokens["output_tokens"],
        "cache_read_tokens": tokens["cache_read_tokens"],
        "cache_creation_tokens": tokens["cache_creation_tokens"],
        "total_cost_usd": calculate_cost_usd(**tokens),
    }
```

### **Observability Snapshot**

```python
def snapshot() -> dict:
    return {
        "counters": dict(_COUNTERS),           # All counter values
        "gauges": dict(_GAUGES),               # All gauge values
        "latency_avg_ms": {                    # Average latencies
            "context_assembly_ms": 245.3,
            "memory_lookup_ms": 12.5,
        },
        "recent_run_events": [                 # Last 50 run events
            {"event": "execution_started", "project_id": "...", "run_id": "..."},
            ...
        ],
    }
```

---

## Summary: Data Flow Integration

```
User sends Conversation Message
    ↓
Load Engagement Brief (EngagementMeta → engagement_brief_text)
    ↓
Pre-fill Discovery Slots (EngagementMeta → engagement_discovery)
    ↓
Assemble Context (TieredContextEngine):
  ├─ Load & BM25-rank parsed docs (mtime-cached)
  ├─ Load & rank wiki pages (mtime-cached, stale-marked)
  ├─ Query MemoryEvent rows (30-day retention)
  ├─ Query ProjectMemoryProfile (per-user aggregates)
  ├─ Query MemoryItem rows (consent-filtered)
  ├─ Add UserProjectPreference context_lines
  └─ Compact conversation history (TieredCompactor, 4 tiers)
    ↓
Check Token Budget (TokenBudgetChecker):
  ├─ Estimate prompt tokens (chars / 3.5)
  ├─ Check remaining run budget
  ├─ Compress if needed (5-tier compression)
  └─ Track usage (input, output, cache_read, cache_creation)
    ↓
Call Claude API (with prompt caching):
  ├─ Send system + user with cache_control blocks
  └─ Charge tokens via run_budget context
    ↓
Record Outcomes:
  ├─ record_discovery_answer() → MemoryEvent + ProjectMemoryProfile
  ├─ record_routing_decision() → MemoryEvent + ProjectMemoryProfile
  ├─ save_state() → conversation_state/{conversation_id}.json
  └─ Increment metrics (memory_items_*, conversation_digest_*, etc.)
    ↓
Persist Run Event:
  ├─ RunEvent record with canonical envelope
  ├─ Publish for SSE streaming
  ├─ Log to Langfuse (optional)
  └─ Create canonical aliases
    ↓
Update Observability:
  ├─ Increment counters
  ├─ Record latencies
  ├─ Update gauges
  └─ Snapshot to file (optional)
```

---

## Configuration Reference

```bash
# Memory compaction
MEMORY_COMPACTION_V1_ENABLED=true
MEMORY_V2_RETRIEVAL_ENABLED=true
MEMORY_COMPACTION_CHAR_CAP=32000

# Memory item access
MEMORY_RESPECT_CONSENT_IN_CONTEXT=true
MEMORY_ENFORCE_CONSENT_LEDGER=false

# Retention
MEMORY_EVENTS_RETENTION_DAYS=30
MEMORY_BATCH_CREATE_ENABLED=true

# Token budgeting (run-level)
SUBAGENT_TOOL_MAX_TOKENS=4096           # Per sub-agent call
ANTHROPIC_COORDINATOR_PLAN_MAX_TOKENS=8192

# Cache
REDIS_URL=redis://localhost:6379/0
CACHE_ALLOW_MEMORY_FALLBACK=true        # false = fail-fast multi-replica
OBSERVABILITY_SNAPSHOT_PATH=/tmp/metrics.json

# Observability
LANGFUSE_ENABLED=false
```
