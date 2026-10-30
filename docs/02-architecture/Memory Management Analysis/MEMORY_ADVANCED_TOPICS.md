# Advanced Memory Management Topics

## 1. Memory Retrieval on Quadrant Model

### Quadrant Concept: Multi-Tiered Context Assembly

The application uses a **4-quadrant memory retrieval model** organizing context by source type and freshness.

```
┌─────────────────────────────────────────────────────────────┐
│ TIER 0: CONTEXT.md (Project-Level)                          │
│ - CONTEXT.md file                                           │
│ - Style context (branding, tone)                            │
│ - Up to 2,000 characters                                    │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ TIER 1: Leading Practices (LP) Snippets                     │
│ - Curated knowledge snippets                                │
│ - OneDrive/wiki integration                                 │
│ - Up to 12,000 characters                                   │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ TIER 2: Source Documents (BM25 Ranked)                      │
│ - parsed_docs chunks                                        │
│ - Wiki pages (with [STALE] markers if >72h old)            │
│ - BM25 + MMR-deduped selection                             │
│ - Up to 10,000 characters                                   │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ TIER 3: Conversation Context (for runs)                     │
│ - Conversation digest (compacted)                           │
│ - Discovery slots from ConversationState                    │
│ - Engagement metadata                                       │
│ - Up to variable budget                                    │
└─────────────────────────────────────────────────────────────┘

Total Context Budget: 32,000 characters (ContextBundle)
```

### Tier 0: Project Context

**File**: `workspace/{project_id}/CONTEXT.md`

```python
context_md = workspace_path(project_id) / "CONTEXT.md"
# User-written markdown describing the project
# Examples: vision, constraints, technical stack, domain knowledge
# First 2,000 chars used
```

### Tier 1: Leading Practices Snippets

**Source**: Passed in or from wiki/OneDrive integration

```python
# Curated snippets for domain-specific best practices
lp_snippets = [
    "Deck design best practices: 1 slide per idea...",
    "Executive brief framework: Problem → Solution → Impact...",
    "Stakeholder analysis: Map influence and interest...",
]
# Up to 12,000 characters total
```

### Tier 2: Document Chunks (BM25 Ranked)

**Location**: `workspace/{project_id}/parsed_docs/*.json`

**Ranking Algorithm**: BM25 (Okapi)

```python
class _BM25Index:
    tokenized: list[list[str]]      # Pre-tokenized chunks
    dl: list[int]                   # Document lengths
    avgdl: float                    # Average document length
    df: dict[str, int]              # Document frequency per term

# BM25 score = IDF * (TF * (k1 + 1)) / (TF + k1 * (1 - b + b * (dl / avgdl)))
# k1 = 1.5 (term saturation parameter)
# b = 0.75 (length normalization parameter)
```

**Selection Process**:

1. **Multi-Query Expansion**:
   ```python
   queries = [
       instruction,
       f"{instruction} roles steps decisions",
       f"{instruction} best practices standards frameworks"
   ]
   ```

2. **Candidate Scoring**: Top BM25 matches per query (max 60 unique chunks)

3. **MMR (Maximal Marginal Relevance)** Deduplication:
   - Formula: `lambda * relevance - (1 - lambda) * diversity`
   - `lambda_param = 0.7` (70% relevance, 30% diversity)
   - Diversity = Jaccard similarity over token sets
   - Prevents redundant chunks
   - Selects up to 15 chunks respecting char budget

**Wiki Cache with Freshness**:

```python
# Wiki pages marked [STALE] if older than 72 hours
_WIKI_STALE_HOURS = 72
if age_s > stale_threshold:
    body = f"[STALE: {age_h}h old]\n{body}"

# Mtime-based cache: re-read only when files change
# Cache key = str(wiki_dir)
# Invalidation trigger = any file mtime change
```

### Tier 2.5: Planner-Specific Retrieval

For coordinator planning (distinct from regular assembly):

```python
def planner_excerpt(project_id, query_text, char_cap):
    # Wiki budget: min(4000, cap * 2/5)  # 40% of planner budget
    # Parsed docs budget: remaining 60%
    
    # Same multi-query + BM25, but optimized for planner needs
    # Returns query-aligned context for planning, not execution
```

### Tier 3: Conversation & Engagement Context

**Components**:

1. **Conversation Digest** — Recent messages (compacted, see §3)
2. **Discovery Slots** — `state.slots` from ConversationState
3. **Engagement Metadata** — `EngagementMeta` fields (brief, sponsor objective, scope, success measures)
4. **Memory Items** — Filtered by consent & archival

---

## 2. Token-Aware Context Budget

### Budget Model

**Location**: `src/llm/token_budgets.py`

```python
class TokenBudgetChecker:
    CHARS_PER_TOKEN = 3.5          # Empirical ratio
    SAFETY_MARGIN_TOKENS = 100     # Buffer for estimation errors
    
    def estimate_tokens(text: str) -> int:
        return max(1, int(len(text) / 3.5))
```

### Pre-Call Budget Verification

```python
def check_budget(system, user, needed_output_tokens=4096, throw_on_exceed=False):
    """
    Returns: (fits_in_budget: bool, {
        'prompt_tokens': int,
        'output_tokens': int,
        'total_tokens_needed': int,
        'remaining_budget': int,
        'compression_needed_tokens': int,  # If over budget
    })
    """
    remaining = get_remaining_budget()
    prompt_tokens = estimate_prompt_tokens(system, user)
    output_tokens = int(needed_output_tokens or 4096)
    total_needed = prompt_tokens + output_tokens + 100  # safety margin
    
    compression_needed = max(0, total_needed - remaining)
    fits = compression_needed == 0
    
    if throw_on_exceed and not fits and remaining < 1000:
        raise TokenBudgetExceeded(...)
    
    return fits, {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens_needed": total_needed,
        "remaining_budget": remaining,
        "compression_needed_tokens": compression_needed,
    }
```

### Intelligent Prompt Compression (5 Tiers)

When budget exceeded, apply compression in order:

| Tier | Strategy | What's Removed | Char Reduction |
|------|----------|----------------|----------------|
| 1 | Trim system examples | "Examples:" sections from system prompt | ~10-20% |
| 2 | Compress context excerpts | Truncate "context excerpt" sections to 2,000 chars | ~15-30% |
| 3 | Reduce instruction | Truncate "instruction" section to 2,000 chars | ~10-25% |
| 4 | Simplify JSON | Strip optional fields from ProcessModel | ~5-15% |
| 5a | Hard truncation (conservative) | Keep first 60% + last 20% of user prompt | ~30-50% |
| 5b | Hard truncation (aggressive) | Keep first 40% + last 10% of user prompt | ~50-70% |

**Metrics Tracked**:
- `prompt_compression_applied_total` — counter

```python
# Example output
{
    "original_tokens": 8500,
    "compressed_tokens": 6200,
    "compression_ratio": 0.729,
    "tiers_applied": ["trim_system_examples", "compress_context_excerpts", "hard_truncation_conservative"],
    "removed_elements": ["verbose examples", "context excerpt details", "bulk user prompt"]
}
```

### Run-Level Token Budget Tracking

**Location**: `src/llm/run_budget.py`

```python
class _RunTokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int              # From prompt caching
    cache_creation_tokens: int          # From prompt caching
    
    def charge(input_tokens, output_tokens, cache_read_tokens=0, cache_creation_tokens=0):
        # Thread-safe accumulation across child threads
        pass
    
    def snapshot() -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
        }

# ContextVar storage — allows child threads to share usage object
_active_usage: ContextVar[_RunTokenUsage | None]

# Live registry for polling
_live_usage_registry: dict[str, _RunTokenUsage]  # {run_id -> usage}
```

---

## 3. Conversation Compaction (Tiered Digest)

### Problem: Token Budget Limit

Raw conversation history grows unbounded. Must compress for LLM context.

**Budget Model**:
- Default char_cap: 2,000–5,000 characters
- Message limit: up to 40 recent messages
- Per-message max: 600 characters

### TieredCompactor Strategy

**Location**: `src/memory/short_term/context_compaction.py`

```python
class TieredCompactor:
    def __init__(self, per_message_chars=600):
        self._per_message_chars = max(120, int(per_message_chars))
    
    def assemble(lines: list[CompactionLine], char_cap: int) -> tuple[str, CompactionTrace]:
        # Apply tiers until text fits within char_cap
```

| Tier | Operation | Trigger | Output |
|------|-----------|---------|--------|
| Tier 0 | Return as-is | If `original_chars ≤ cap` | Full conversation |
| Tier 1 (Micro-Compact) | Drop fragments; truncate msgs to 600 chars | If after T0 still over | Messages without filler ("ok", "thanks") |
| Tier 2 (Snip Oldest) | Keep only last 120 messages | If after T1 still over | Recent-only digest |
| Tier 3 (Auto-Summary) | Summarize first N-8 messages into single line | If after T2 still over | `[summary]: ...` + tail |
| Tier 4 (Context-Collapse) | Keep only last 5 messages + context marker | If after T3 still over | Ultra-compact with note |

**Example Flow**:

```
Original: 8,000 chars, 50 messages
Cap: 2,000 chars

→ Tier 1: 6,500 chars (remove "ok", "thanks")
→ Tier 2: 5,200 chars (keep last 30 messages)
→ Tier 3: 2,100 chars (summarize old 22, keep last 8 + summary line)
→ Final: 2,050 chars (fits in cap)

Output:
[summary]: User asked about timeline → discussed Q4 → confirmed budget
Message 44: "Great, let's start the discovery phase"
Message 45: "Perfect, I'm ready"
...
Message 50: [latest message]

[context-collapse]: Preserved latest high-signal turns only. Older turns were compacted.
```

### ConversationDigest Assembly

**Location**: `src/memory/short_term/conversation_digest.py`

```python
def build_conversation_digest_for_run_with_trace(
    session: Session,
    project_id: str,
    conversation_id: str | None,
    char_cap: int,
    message_limit: int = 40,
    per_message_chars: int = 600,
) -> tuple[str, CompactionTrace]:
    
    # 1. Fetch up to message_limit recent messages
    rows = session.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == cid)
        .order_by(ConversationMessage.created_at.desc())
        .limit(message_limit)
    ).all()
    rows.reverse()  # Oldest → newest
    
    # 2. Mark stale sources (>TTL old)
    freshness_map = mark_stale_sources(
        rows,
        ttl_seconds=settings.conversation_source_freshness_ttl_seconds  # Default: 72h
    )
    
    # 3. Build CompactionLine list
    lines = []
    for m in rows:
        body = redact_emails(m.content)
        if stale:
            body = f"[STALE: {age_h}h old] {body}"
        
        # Extract metadata for importance scoring
        meta = json.loads(m.metadata_json or "{}")
        if has_plan_hash or has_failure_signal or has_constraint:
            extras.append("[PLAN]" or "[FAILURE]" or "[CONSTRAINT]")
        
        lines.append(CompactionLine(source_id=m.id, text=f"{role}: {body}{extras}"))
    
    # 4. Apply tiered compaction
    compactor = TieredCompactor(per_message_chars=per_message_chars)
    digest, trace = compactor.assemble(lines=lines, char_cap=char_cap)
    
    return digest, trace
```

### CompactionTrace Observability

```python
@dataclass
class CompactionTrace:
    original_char_count: int
    final_char_count: int
    tiers_applied: list[str]           # ["tier1_micro_compact", "tier2_snip_oldest"]
    dropped_sources: dict[str, int]    # {"conversation_segments": 15}
    
    # Metrics emitted:
    # - conversation_digest_built_total (increment)
    # - conversation_digest_tiered_compaction_total (if tiers applied)
```

---

## 4. Persistent Memory Types

### Type Taxonomy

**Table**: `memory_items`

| Type | Examples | Use Case | Lifetime |
|------|----------|----------|----------|
| **preference** | audience_preference="finance", tone="executive" | User-stated preferences; inform options | Session → permanent |
| **constraint** | timeline_constraint="Q4_2024", budget_constraint="<$50k" | Hard limits on execution | Session → permanent |
| **decision** | format_decision="slide_deck", approval_strategy="async" | Confirmed choices to reuse | Until overridden |
| **fact** | company_size="500_employees", industry="fintech" | Domain knowledge about client | Until invalidated |

### Unique Constraint

```sql
UNIQUE (project_id, memory_type, key)
-- Only one fact per (type, key) per project
-- Upsert: update if exists, insert otherwise
```

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | String(64) | Primary key |
| `project_id` | FK | Project scope |
| `memory_type` | String(32) | Enum: preference, constraint, decision, fact |
| `key` | String(128) | Identifier (e.g., "audience_preference") |
| `value` | Text | Content (JSON-friendly) |
| `confidence` | String(16) | "high", "medium", "low" |
| `source` | String(64) | "chat", "wiki", "run_output", "user_input" |
| `consent_state` | String(16) | "allowed", "restricted", "revoked" |
| `principal_id` | String(128) | DPDP data subject (nullable) |
| `is_archived` | Boolean | Soft-delete flag |
| `created_at` | DateTime | Indexed for retention |
| `updated_at` | DateTime | Last modification |

---

## 5. Memory Write Pipeline

### Event-Driven Flow

```
1. ConversationTurn receives user message
         │
         ▼
2. _post_project_conversation_message_impl()
         │
         ├─→ load_state(conversation)  [filesystem read]
         │
         ├─→ _extract_discovery_answers()  [parse message]
         │   └─→ Extract slots like {"audience": "finance_team"}
         │
         ├─→ route_turn()  [decide next action]
         │
         ├─→ record_discovery_answer()  [write event]
         │   ├─→ append MemoryEvent(event_type="discovery_answer_recorded")
         │   ├─→ update ProjectMemoryProfile.summary_json
         │   └─→ metric: memory_events_written_total
         │
         ├─→ record_routing_decision()  [write event]
         │   ├─→ append MemoryEvent(event_type="routing_decision_recorded")
         │   └─→ update ProjectMemoryProfile.summary_json
         │
         ├─→ save_state(conversation, state)  [filesystem write]
         │   └─→ Write to workspace/{project_id}/conversation_state/{conv_id}.json
         │
         └─→ Return response
```

### record_discovery_answer()

**Location**: `src/memory/long_term/memory_event_service.py`

```python
def record_discovery_answer(session: Session, *, project_id: str, user_id: str, slot_key: str, value: Any):
    # 1. Load profile with lock (SELECT FOR UPDATE on PostgreSQL)
    row, summary = _load_profile_for_update(session, project_id=project_id)
    
    # 2. Normalize user block in summary
    block = _normalize_user_profile(summary, user_id)
    slots = block["aggregated_slots"]
    
    # 3. Update slots
    slots[slot_key] = value
    block["updated_at"] = _now_iso()
    
    # 4. Save profile back to DB
    _save_profile(session, project_id=project_id, row=row, payload=summary)
    # → ProjectMemoryProfile.summary_json updated
    
    # 5. Append MemoryEvent (with deduplication)
    _append_event_if_possible(
        session,
        project_id=project_id,
        event_type="discovery_answer_recorded",
        payload={"user_id": user_id, "slot_key": slot_key, "value": value},
    )
    # → Fingerprint = sha256(project_id | run_id | event_type | canonical_payload)
    # → Skip if fingerprint already exists (dedup)
    
    # 6. Metric: memory_events_written_total += 1
```

### record_routing_decision()

Similar to discovery, but records decision outcomes:

```python
def record_routing_decision(session, *, project_id, user_id, decision_type, confidence, outcome):
    # 1. Load profile with lock
    row, summary = _load_profile_for_update(session, project_id=project_id)
    
    # 2. Update decision_outcomes
    block = _normalize_user_profile(summary, user_id)
    outcomes = block["decision_outcomes"]
    
    # 3. Aggregate stats
    current = outcomes.get(decision_type, {})
    count = int(current.get("count", 0)) + 1
    avg_confidence = ((prev_avg * (count - 1)) + confidence) / count
    
    outcomes[decision_type] = {
        "count": count,
        "avg_confidence": round(avg_confidence, 4),
        "last_outcome": outcome[:200],
        "last_updated_at": _now_iso(),
    }
    
    # 4-6. Same as discovery: save, append event, metric
```

### Deduplication via Fingerprint

```python
def _append_event_if_possible(session, *, project_id, event_type, payload):
    run_id = _latest_project_run_id(session, project_id=project_id)
    
    canonical = json.dumps(payload, sort_keys=True)
    fingerprint = sha256(f"{project_id}|{run_id}|{event_type}|{canonical}".encode()).hexdigest()
    
    existing = session.scalar(
        select(MemoryEvent).where(
            MemoryEvent.project_id == project_id,
            MemoryEvent.run_id == run_id,
            MemoryEvent.event_type == event_type,
            MemoryEvent.fingerprint == fingerprint,
        )
    )
    
    if existing:
        # Skip: already recorded
        metrics.increment("memory_events_deduped_total")
        return
    
    # New event: insert
    session.add(MemoryEvent(...))
    metrics.increment("memory_events_written_total")
```

### Metrics

```
memory_events_written_total        # New events appended
memory_events_deduped_total        # Duplicate fingerprints skipped
memory_items_injected_into_context_total     # Items merged into LLM context
memory_items_consent_skipped_total           # Blocked by consent_state
memory_items_ledger_blocked_total            # Blocked by Consent Ledger
```

---

## 6. Memory Lifecycle and Consent

### Lifecycle Stages

```
1. CREATION
   ├─ Via conversation message → record_discovery_answer()
   ├─ Via form input → batch memory create API
   └─ Via run output → programmatic insertion
         │
         ▼
2. ACTIVE
   ├─ Stored in MemoryItem (is_archived=false)
   ├─ Indexed in ProjectMemoryProfile.summary_json
   └─ Retrieved for context assembly
         │
         ▼
3. ARCHIVAL (Soft Delete)
   ├─ Set is_archived=true
   ├─ Still queryable (for audit)
   └─ Excluded from context retrieval
         │
         ▼
4. ERASURE (DPDP Compliance)
   ├─ Hard delete (principal_id subject to erasure)
   └─ Remove from ProjectMemoryProfile
```

### Consent Model: Two-Tier

#### Tier 1: Field-Level consent_state

```python
# Values: "allowed", "restricted", "revoked"
item.consent_state = "restricted"  # User opted out
```

**When checked**:
```python
def memory_item_allowed_for_use(item, respect_consent=True):
    if respect_consent:
        cs = (item.consent_state or "").strip().lower()
        if cs not in ("allowed", ""):
            return False, "consent_field"
    return True, ""
```

#### Tier 2: Consent Ledger (DPDP Principal Tracking)

```sql
-- Table: consent_ledger
-- Tracks data subject (principal_id) consent per project
CREATE TABLE consent_ledger (
    id STRING PRIMARY KEY,
    project_id STRING,
    principal_id STRING,      -- e.g., "user@company.com"
    purpose STRING,           -- "use_in_context", "training", etc.
    granted BOOLEAN,
    revoked_at DATETIME,
    created_at DATETIME,
    INDEX (project_id, principal_id)
);
```

**When checked**:
```python
def memory_item_allowed_for_use(item, enforce_consent_ledger=True):
    if enforce_consent_ledger:
        principal = item.principal_id  # e.g., "user@company.com"
        if principal and not consent_ledger_latest_granted(session, project_id, principal):
            return False, "consent_ledger"
    return True, ""

def consent_ledger_latest_granted(session, project_id, principal_id) -> bool:
    # Get most recent ledger row for (project_id, principal_id)
    row = session.scalar(
        select(ConsentLedger)
        .where(ConsentLedger.project_id == project_id,
               ConsentLedger.principal_id == principal_id)
        .order_by(ConsentLedger.created_at.desc())
        .limit(1)
    )
    return bool(row.granted) if row else False
```

**Metrics**:
```
memory_items_consent_skipped_total       # Blocked by consent_state
memory_items_ledger_blocked_total        # Blocked by Consent Ledger
```

---

## 7. Memory Scope and Isolation

### Isolation Model

| Scope | Boundary | Example |
|-------|----------|---------|
| **Project** | `project_id` FK | MemoryItem, MemoryEvent, ProjectMemoryProfile all scoped to project |
| **Conversation** | `conversation_id` FK | ConversationMessage, ConversationState, ConversationTurn |
| **User** | `user_id` FK | Membership, UserProjectPreference, runs filtered by project membership |
| **Run** | `run_id` FK | RunEvent, RunTask, MemoryEvent linked to specific run |

### Cross-Conversation Isolation

```python
# Memory items are PER-PROJECT, not per-conversation
# This means: aggregated_slots learned in one conversation
#            are available to all conversations in that project

# Example:
# Conv A: User says "audience is finance team"
#   → record_discovery_answer(project_id, slot_key="audience", value="finance_team")
#   → Stored in ProjectMemoryProfile.summary_json["users"][user_id]["aggregated_slots"]["audience"]

# Conv B (same project, same user): 
#   → When loading context, ProjectMemoryProfile is retrieved
#   → Already has "audience": "finance_team" from Conv A
#   → Avoids re-asking the question
```

### Project-Level Aggregation

```python
class ProjectMemoryProfile:
    project_id: str          # PK: single row per project
    summary_json: str        # All aggregated memory
    updated_at: DateTime     # Last update
    
# Structure of summary_json:
{
    "users": {
        "user_123": {
            "aggregated_slots": {
                "audience": "finance_team",
                "timeline": "Q4_2024",
                ...
            },
            "decision_outcomes": {
                "format_choice": {
                    "count": 3,
                    "avg_confidence": 0.95,
                    "last_outcome": "slide_deck",
                    "last_updated_at": "2026-10-30T..."
                },
                ...
            },
            "updated_at": "2026-10-30T..."
        },
        ...
    }
}
```

### Retrieval Filtering

```python
def get_aggregated_profile(session, project_id, user_id):
    row = session.scalar(
        select(ProjectMemoryProfile)
        .where(ProjectMemoryProfile.project_id == project_id)
    )
    
    # Extract user's block from project summary
    summary = json.loads(row.summary_json)
    users = summary.get("users", {})
    block = users.get(user_id, {})
    
    return {
        "aggregated_slots": block.get("aggregated_slots", {}),
        "decision_outcomes": block.get("decision_outcomes", {}),
    }
```

---

## 8. Cache Key TTL and Invalidation

### Cache Layers

#### Layer 1: Filesystem mtime Cache (TieredContextEngine)

**Cache Locations**:
- `_parsed_cache: dict[cache_key, (latest_mtime, chunks, bm25_index)]`
- `_wiki_cache: dict[cache_key, (latest_mtime, wiki_chunks, bm25_index)]`

**Invalidation Trigger**: File modification time (mtime) change

```python
def _load_all_parsed_chunks(self, project_id: str | None) -> list[dict[str, Any]]:
    parsed_dir = workspace_path(project_id) / "parsed_docs"
    
    # Compute latest mtime across all files
    latest_mtime = 0.0
    for p in parsed_dir.glob("*.json"):
        try:
            latest_mtime = max(latest_mtime, p.stat().st_mtime)
        except Exception:
            continue
    
    # Check if we have cached result
    cached = self._parsed_cache.get(str(parsed_dir))
    if cached and cached[0] == latest_mtime:
        return list(cached[1])  # Cache hit
    
    # Cache miss: reload and rebuild BM25 index
    chunks = load_chunks_from_disk(...)
    texts = chunk_strings(chunks)
    bm25_index = _build_bm25_index(texts)
    
    self._parsed_cache[str(parsed_dir)] = (latest_mtime, chunks, bm25_index)
    return chunks
```

**TTL Model**: No explicit TTL; invalidation is event-driven (mtime change)

#### Layer 2: Wiki Freshness TTL

**Parameter**: `_WIKI_STALE_HOURS = 72`

**Behavior**:
```python
now = time.time()
stale_threshold = 72 * 3600  # seconds

for md_file in md_files:
    content = md_file.read_text()
    age_s = now - md_file.stat().st_mtime
    
    if age_s > stale_threshold:
        age_h = int(age_s / 3600)
        content = f"[STALE: {age_h}h old]\n{content}"  # Prefix warning
    
    chunks.append(f"[Wiki: {title}]\n{content}")
```

**Purpose**: Age awareness (not eviction). LLM can weight [STALE] content lower.

#### Layer 3: ConversationSource Freshness

**Parameter**: `conversation_source_freshness_ttl_seconds` (default: 259200 = 72 hours)

**When Building Digest**:
```python
freshness_map = mark_stale_sources(
    rows,
    ttl_seconds=settings.conversation_source_freshness_ttl_seconds
)

for m in rows:
    info = freshness_map.get(int(m.id))
    if info and info.is_stale and settings.conversation_digest_exclude_stale_sources:
        continue  # Skip old messages
    if info and info.prefix:
        body = f"{info.prefix}{body}"  # Add [STALE] marker
```

#### Layer 4: Redis Cache Service

**Location**: `src/core/cache.py`

```python
class CacheService:
    def __init__(self):
        self._mem: dict[str, tuple[float, str]] = {}  # In-memory fallback
        self._redis = redis.Redis.from_url(settings.redis_url)  # If available
    
    def get(self, key: str) -> dict | None:
        if self._redis:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        
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
            self._redis.setex(key, ttl_seconds, raw)
        else:
            self._mem[key] = (time.monotonic() + float(ttl_seconds), raw)
```

**TTL Model**: Explicit `ttl_seconds` parameter per `set()` call

**Fallback**: In-memory cache if Redis unavailable (single-process only)

---

## 9. LLM Prompt Caching

### Prompt Caching in Claude API

**Location**: `src/llm/claude.py`

```python
def _build_system_message(system: str) -> list[dict]:
    """Wrap system prompt with cache_control for prompt caching."""
    return [
        {
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"}  # Ephemeral cache
        }
    ]
```

**Cache Strategy**: Ephemeral (short-lived, cost-optimized)

### Token Usage Tracking

```python
# Extract cache metrics from API response
usage = response.usage

cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
cache_create = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

# Log to run budget
charge_llm_usage(
    input_tokens=usage.input_tokens,
    output_tokens=usage.output_tokens,
    cache_read_tokens=cache_read,
    cache_creation_tokens=cache_create,
)
```

### Budget Model: Cache Tokens Count Toward Budget

```python
# In run_budget.py:
class _RunTokenUsage:
    cache_read_tokens: int
    cache_creation_tokens: int
    
    def snapshot():
        return {
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
        }
```

**Metric**: Tracked per-run for observability and cost calculation

### When Enabled

- System prompts (especially long ones)
- Repeated context assembly patterns
- Multi-turn conversations (ephemeral cache within session)

### Limitations

- **Ephemeral only**: Caches expire between sessions
- **Min cost threshold**: Cache creation costs more if total cached tokens < threshold
- **Same prompt required**: Cache hit requires identical system prompt

---

## 10. Run State and File Storage

### Run State Persistence

#### Database (Immediate)

**Table**: `runs`

```python
class Run(Base):
    id: str                    # Primary key
    project_id: str            # FK
    status: str                # queued, running, paused, done, failed
    output_types: str          # JSON list of output types
    instruction: str           # User instruction
    plan_payload: str          # JSON of execution plan
    approved_by: str | None    # FK to User (if approved)
    approved_at: DateTime | None
    error_message: str | None
    pause_requested: bool
    resume_requested: bool
    abort_requested: bool
    tokens_input: int | None
    tokens_output: int | None
    tokens_cache_read: int | None           # From prompt caching
    tokens_cache_creation: int | None       # From prompt caching
    cost_usd: float | None
    prompts_used: str | None   # JSON: [{"name": "...", "version": "..."}]
    created_at: DateTime
```

#### Event Stream

**Table**: `run_events`

Immutable event log for run execution.

```python
class RunEvent(Base):
    id: int                    # Auto-increment
    run_id: str                # FK
    event_type: str            # "started", "task_assigned", "approved", "completed", etc.
    payload: str               # JSON details
    created_at: DateTime       # Indexed
    
    @property
    def payload_json(self) -> dict:
        try:
            return json.loads(self.payload)
        except Exception:
            return {"value": self.payload}
```

#### File System Storage

**Location**: `workspace/{project_id}/runs/{run_id}/`

```
runs/
  {run_id}/
    ├─ state.json              # Run state snapshot
    ├─ plan.json               # Execution plan
    ├─ context.md              # Assembled context
    ├─ events.jsonl            # Event log (newline-delimited JSON)
    ├─ tokens.json             # Token usage breakdown
    └─ artifacts/
        ├─ {artifact_1}.pptx
        ├─ {artifact_2}.docx
        └─ ...
```

### Token Usage Persistence

**Storage**: Database (Run.tokens_*)

```python
def save_token_usage_to_run(session, run_id, usage_snapshot):
    run = session.get(Run, run_id)
    if run:
        run.tokens_input = usage_snapshot["input_tokens"]
        run.tokens_output = usage_snapshot["output_tokens"]
        run.tokens_cache_read = usage_snapshot.get("cache_read_tokens", 0)
        run.tokens_cache_creation = usage_snapshot.get("cache_creation_tokens", 0)
        
        # Calculate cost
        total_tokens = (
            usage_snapshot["input_tokens"] +
            usage_snapshot["output_tokens"] +
            (usage_snapshot.get("cache_read_tokens", 0) * 0.1) +  # 10% of input cost
            (usage_snapshot.get("cache_creation_tokens", 0))       # Full input cost
        )
        run.cost_usd = total_tokens / 1000 * model_cost_per_1k_tokens
        
        session.commit()
```

### Conversation File Storage

**Location**: `workspace/{project_id}/conversation_state/{conversation_id}.json`

```json
{
    "schema_version": 2,
    "state": "discovery",
    "slots": {
        "audience": "finance_team",
        "timeline": "Q4_2024"
    },
    "deliverable": {
        "template_ids": ["pptx_default"],
        "output_types": ["slide_deck"]
    },
    "last_router": {
        "route": "ask_discovery_question",
        "skill": null,
        "reason": "Missing required slots"
    },
    "pending_questions": ["What format?"],
    "surfaced_wiki_refs": ["Best Practices for Executive Decks"],
    "history_summary": "User requested a sales deck for Q4..."
}
```

---

## 11. Memory Observability

### Metrics Exported

**Location**: `src/core/observability/metrics.py`

#### Counter Metrics

```
memory_events_written_total                      # New MemoryEvent rows
memory_events_deduped_total                      # Events skipped (duplicate fingerprint)
memory_events_pruned_total                       # Events deleted by retention
memory_items_injected_into_context_total         # MemoryItems merged into LLM context
memory_items_consent_skipped_total               # Skipped by consent_state
memory_items_ledger_blocked_total                # Skipped by Consent Ledger
memory_batch_create_total                        # Items created via POST API
user_preference_learning_runs_bumped_total       # UserProjectPreference learning increments

conversation_digest_built_total                  # Non-empty digests built for runs
conversation_digest_tiered_compaction_total      # Digests where tiers applied
prompt_compression_applied_total                 # Prompts compressed for token budget
planner_excerpt_chars_total                      # Total chars in planner context
```

#### Histogram Metrics (Latency)

```
memory_retrieve_ms                               # Time to assemble context
memory_compress_ms                               # Time to compress conversation
bm25_score_ms                                    # BM25 scoring time
```

#### Gauge Metrics

```
live_run_tokens_input                            # Running total of input tokens
live_run_tokens_output                           # Running total of output tokens
live_run_tokens_cache_read                       # Running cache read tokens
live_run_tokens_cache_creation                   # Running cache creation tokens
active_conversation_count                        # Conversations in memory
```

### Prometheus Endpoint

**Endpoint**: `GET /metrics/prometheus`

Exports all metrics in OpenMetrics format for Prometheus scraping.

### OpenTelemetry Integration

```python
def set_otel_meter(meter):
    global _OTEL_METER
    _OTEL_METER = meter

# All metrics above also sent to OTEL when configured
# Supports OpenObserve, Datadog, New Relic, etc.
```

### Example Query

```python
# Live run token usage
@app.get("/runs/{run_id}/tokens")
def get_run_token_usage(run_id: str):
    usage = _live_usage_registry.get(run_id)
    if usage:
        return usage.snapshot()
    
    # Fallback to database
    run = db.get(Run, run_id)
    return {
        "input_tokens": run.tokens_input,
        "output_tokens": run.tokens_output,
        "cache_read_tokens": run.tokens_cache_read,
        "cache_creation_tokens": run.tokens_cache_creation,
    }
```

### Dashboard Examples

**Run-Level Observability**:
- Input/output tokens per run
- Cache hit/creation tokens
- Cost per run (calculated)
- Compression ratio applied

**Project-Level Observability**:
- Total memory items stored
- Consent violations (skipped items)
- Discovery slot coverage (how many required slots filled)
- Conversation compaction frequency

**System-Level Observability**:
- Memory event rate (events/second)
- Cache hit rate (cache_read / total_input)
- Average compression ratio
- Consent enforcement rate

---

## Summary Diagram

```
User Message (POST /conversation/messages)
         │
         ▼
ConversationTurn (async)
         │
         ├─→ load_state() [filesystem]
         │   └─→ ConversationState (short-term memory)
         │
         ├─→ extract_discovery() [parse]
         │
         ├─→ record_discovery_answer()  [long-term write]
         │   ├─→ MemoryEvent (event stream)
         │   ├─→ ProjectMemoryProfile (aggregation)
         │   └─→ metrics: memory_events_written_total
         │
         ├─→ save_state() [filesystem write]
         │
         ├─→ assemble_context()  [quadrant retrieval]
         │   ├─→ Tier 0: CONTEXT.md
         │   ├─→ Tier 1: LP snippets
         │   ├─→ Tier 2: BM25 + MMR (with mtime cache)
         │   └─→ Tier 3: Conversation digest (with compaction)
         │
         ├─→ check_budget()
         │   └─→ compress_prompt_if_needed() [5-tier compression]
         │
         ├─→ LLM API call
         │   └─→ System prompt [cache_control: ephemeral]
         │
         └─→ charge_llm_usage()
             └─→ _RunTokenUsage (accumulator)
```

---

## References

- **Token Budgeting**: `src/llm/token_budgets.py`
- **Context Assembly**: `src/memory/retrieval.py`
- **Conversation Compaction**: `src/memory/short_term/context_compaction.py`, `conversation_digest.py`
- **Memory Write Pipeline**: `src/memory/long_term/memory_event_service.py`
- **Consent Model**: `src/memory/long_term/memory_consent.py`
- **Caching**: `src/core/cache.py`
- **Observability**: `src/core/observability/metrics.py`
- **LLM Integration**: `src/llm/claude.py`, `run_budget.py`
