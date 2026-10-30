# Leading Practice Library — Complete Memory, Data Storage & Engagement Architecture

Comprehensive specification of how the Leading Practice Library section captures, stores, retains, and uses memory and prompts throughout the engagement lifecycle.

---

## Table of Contents

1. [LP Memory Types & Capture](#1-lp-memory-types--capture)
2. [LP Data Storage Architecture](#2-lp-data-storage-architecture)
3. [LP Index & Embedding Storage](#3-lp-index--embedding-storage)
4. [LP Retention Policies](#4-lp-retention-policies)
5. [LP Prompt Registry & Usage](#5-lp-prompt-registry--usage)
6. [LP Integration in Engagement Flow](#6-lp-integration-in-engagement-flow)
7. [LP Memory Events & Recording](#7-lp-memory-events--recording)
8. [Complete LP Data Flow](#8-complete-lp-data-flow)

---

## 1. LP Memory Types & Capture

### 1.1 Search Query Memory

**What is captured:**
- User search query
- Search timestamp
- Project context
- Search parameters (max_results, dpdp_enabled)
- Search results returned

**Captured data structure:**
```json
{
    "timestamp": "2026-10-30T10:45:30Z",
    "project_id": "proj_123",
    "query": "month-end close process best practices",
    "max_results": 5,
    "dpdp_enabled": true,
    "search_type": "semantic_keyword_fused"
}
```

**Storage locations:**
1. **In-memory cache (5 minutes):**
   - Key: `lpsearch:{fingerprint}:{max_results}:{query_hash}`
   - TTL: 300 seconds
   - Hit/miss tracked in metrics

2. **Redis cache (if available):**
   - Same key pattern
   - Shared across API instances
   - Automatic eviction after TTL

3. **Metrics:**
   - Counter: `lp_rag_searches_total` (incremented)
   - No persistent storage of search queries (privacy)

**Access pattern:** Read-heavy; one-time write per unique query.

---

### 1.2 Search Results Memory

**What is captured per result:**
```json
{
    "id": "sha256_hash[:16]",
    "path": "/path/to/source/file",
    "heading": "Financial Calendar",
    "text": "Month-end close should complete within 3-5 business days...",
    "source": "library" | "wiki",
    "relevance_score": 0.92,
    "search_context": {
        "keyword_score": 0.95,
        "semantic_score": 0.89,
        "fused_score": 0.92,
        "rank_position": 1
    }
}
```

**Result metadata captured:**
```json
{
    "total_results_returned": 5,
    "search_duration_ms": 245,
    "keyword_hits_count": 8,
    "semantic_hits_count": 6,
    "deduped_count": 1,
    "final_selected_count": 5,
    "cache_hit": false,
    "passages_from_library": 3,
    "passages_from_wiki": 2
}
```

**Storage locations:**
1. **Cache (with TTL):**
   - Key: `lpsearch:{fingerprint}:{max_results}:{query_hash}`
   - Value: `{"results": [...]}`
   - TTL: 300 seconds

2. **Index file (persistent):**
   - Location: `workspace/.lp_index/index.json`
   - All indexed passages stored here
   - Rebuilt on source file change

**Access pattern:** Read from cache first; miss → run search → cache results.

---

### 1.3 Answer Generation Memory

**What is captured when answer is generated:**
```json
{
    "event_type": "lp_answer_generated",
    "timestamp": "2026-10-30T10:46:00Z",
    "project_id": "proj_123",
    "question": "How fast should month-end close happen?",
    "sources_count": 5,
    "sources_cited": [
        {"id": "lp_456", "heading": "Financial Calendar", "relevance_score": 0.95},
        {"id": "lp_789", "heading": "Close Checklist", "relevance_score": 0.87},
        {"id": "lp_012", "heading": "Timeline", "relevance_score": 0.82}
    ],
    "answer_text": "Month-end should close within [1] 3-5 business days, per the financial calendar best practice...",
    "answer_length_chars": 387,
    "answer_generated_by": "claude-opus-5-5",
    "tokens_used": {
        "input": 2100,
        "output": 350
    },
    "generation_latency_ms": 2340
}
```

**Storage locations:**
1. **Metrics (for monitoring):**
   - Counter: `lp_rag_answers_total` (incremented)
   - No persistent answer storage

2. **If used in run context:**
   - May be included in RunEvent
   - May be referenced in RunTask output_json
   - Included in assembled context (temp)

**Access pattern:** One-time generation per unique question; not cached.

---

### 1.4 LP Usage in Run Context Memory

**What is captured during run execution:**

When LP snippets are retrieved and integrated into coordinator context:

```json
{
    "event_type": "lp_context_integration",
    "timestamp": "2026-10-30T10:47:00Z",
    "run_id": "run_456",
    "project_id": "proj_123",
    "phase": "context_assembly",
    "lp_query": "generated from: process model extraction + output types",
    "lp_results_count": 5,
    "lp_results_used_count": 5,
    "lp_chars_in_context": 4200,
    "lp_passages": [
        {"id": "lp_456", "heading": "...", "source": "library", "relevance_score": 0.95},
        {"id": "lp_789", "heading": "...", "source": "wiki", "relevance_score": 0.87}
    ],
    "output_types_targeted": ["pptx", "docx"],
    "supplementary_searches": {
        "pptx": {"query": "Executive presentation", "results": 3},
        "docx": {"query": "Detailed process document", "results": 2}
    }
}
```

**Storage locations:**
1. **Temporary (during run):**
   - Held in `state.lp_snippets` (list of strings)
   - Passed to all downstream agents
   - Formatted as `[LP]{heading}\n{text}`

2. **Permanent (after run):**
   - If logged: becomes part of RunEvent payload
   - If referenced in output: included in final deliverable
   - Memory profile updated: decision that LP was used

**Captured in state:**
- `lp_snippets: list[str]` - formatted passages
- Passed to coordinator planning and specialist agents
- Available to all output types (PPTX, DOCX, PDF, XLSX)

---

### 1.5 LP Usage Decision Memory

**What is captured:**
```json
{
    "event_type": "lp_usage_decision",
    "timestamp": "2026-10-30T10:47:30Z",
    "run_id": "run_456",
    "decision": "used" | "not_used",
    "reason": "lp_configured_and_query_matches" | "lp_not_configured" | "error",
    "lp_library_configured": true,
    "lp_library_size": {"passages": 42, "fingerprint": "abc123"},
    "error_message": null
}
```

**Storage location:**
- MemoryEvent table (if decision made at project level)
- RunEvent table (if decision made at run level)

**Update to ProjectMemoryProfile:**
```json
{
    "lp_usage": {
        "total_runs_with_lp": 5,
        "total_runs": 8,
        "lp_adoption_rate": 0.625,
        "avg_lp_snippets_per_run": 4.2
    }
}
```

---

## 2. LP Data Storage Architecture

### 2.1 Storage Locations Summary

| Data Type | Location | Format | Size | Retention | Indexed |
|---|---|---|---|---|---|
| **LP Passages (text)** | `workspace/.lp_index/index.json` | JSON | <100 MB | Until source change | Fingerprint |
| **LP Embeddings** | `workspace/.lp_index/embeddings.npy` | NumPy binary | <200 MB | Until source change | Model name |
| **Embedding metadata** | `workspace/.lp_index/embeddings.json` | JSON | <1 MB | Until rebuild | Fingerprint |
| **LP search cache** | Redis / in-memory | Python dict | Variable | 300s TTL | Query hash |
| **LP usage in runs** | `run_events` table | JSON payload | <10 GB | Permanent | run_id |
| **LP memory events** | `memory_events` table | JSON payload | <1 GB | 30 days default | project_id, created_at |
| **LP in context** | Temp RAM during run | Python list[str] | <100 MB | Run lifetime | None |

### 2.2 Detailed Storage Breakdown

#### 2.2.1 Index JSON (`workspace/.lp_index/index.json`)

**Structure:**
```json
{
    "fingerprint": "abc123def456...",
    "items": [
        {
            "id": "hash[:16]",
            "path": "/path/to/file.md",
            "heading": "Section heading",
            "text": "Full passage text (≈1200 chars)",
            "source": "library"
        },
        {
            "id": "hash[:16]",
            "path": "workspace/proj_123/wiki/page.md",
            "heading": "Wiki page section",
            "text": "...",
            "source": "wiki"
        }
    ]
}
```

**Metadata:**
- Total passages: thousands (depends on library size)
- Fingerprint: SHA256[:16] of all source file mtimes + sizes
- Rebuilt: When fingerprint changes (file added/modified/deleted)

**Lifecycle:**
1. Built on first search after startup
2. Checked every 30 seconds for changes (RESCAN_SEC)
3. Fingerprint compared to previous; if different, rebuild triggered
4. Old embeddings deleted; new embeddings computed on next semantic search

---

#### 2.2.2 Embeddings Files (`workspace/.lp_index/embeddings.*`)

**embeddings.npy:**
- Binary NumPy format
- Shape: (num_passages, 384) — one row per passage
- Data type: float32, normalized (cosine similarity ready)
- Size: num_passages * 384 * 4 bytes ≈ 1.5 MB per 1000 passages
- Memory-mapped on load (lazy, only reads needed rows)

**embeddings.json:**
```json
{
    "fingerprint": "abc123def456...",
    "model": "all-MiniLM-L6-v2"
}
```

**Lifecycle:**
1. Computed only on first semantic search after index rebuild
2. Cached in numpy binary for speed
3. Metadata file tracks which index fingerprint + model version
4. If fingerprint doesn't match, embeddings are recomputed + saved

---

#### 2.2.3 Cache (`Redis` or in-memory)

**Cache key pattern:**
```
lpsearch:{index_fingerprint}:{max_results}:{query_sha256[:16]}
```

**Example:**
```
lpsearch:abc123def456:5:9f86d081884c7d6d
```

**Value structure:**
```json
{
    "results": [
        {
            "id": "...",
            "path": "...",
            "heading": "...",
            "text": "...",
            "source": "library" | "wiki",
            "relevance_score": 0.92
        }
    ]
}
```

**TTL:** 300 seconds (5 minutes)

**Invalidation:**
- Automatic on TTL expiration
- Manual: when index fingerprint changes (all cache keys with old fingerprint ignored)

---

#### 2.2.4 Database Storage

##### RunEvent (if LP used in run):
```python
RunEvent {
    id: int                          # Auto-increment
    run_id: str                      # FK to Run
    event_type: str                  # "lp_context_integrated"
    payload: str                     # JSON (see 1.4 above)
    created_at: DateTime             # Indexed
}
```

**Example payload:**
```json
{
    "event_type": "lp_context_integrated",
    "phase": "context_assembly",
    "lp_query": "...",
    "lp_results_count": 5,
    "lp_chars_in_context": 4200
}
```

##### MemoryEvent (if LP usage recorded as memory):
```python
MemoryEvent {
    id: int                          # Auto-increment
    project_id: str                  # FK
    run_id: str                      # FK
    event_type: str                  # "lp_snippet_referenced"
    fingerprint: str                 # Dedup key
    payload: str                     # JSON
    created_at: DateTime             # Indexed
}
```

**Retention:** 30 days (configurable via MEMORY_EVENTS_RETENTION_DAYS)

---

## 3. LP Index & Embedding Storage

### 3.1 Index Building Process

**Triggered by:**
1. First load (on app startup)
2. Source file change (detected every 30 seconds)
3. Explicit refresh: `POST /api/lp-library/refresh`
4. Force rebuild: `POST /api/lp-library/refresh?force=true`

**Process:**
```
1. List source files
   ├─ Library folder: LP_LIBRARY_LOCAL_PATH (*.md, *.txt)
   └─ Wiki folder: workspace/leading_practices/wiki (*.md)

2. Compute fingerprint
   └─ SHA256(file_path | mtime_ns | size) for each file

3. Parse each file into passages
   ├─ Split on Markdown headings
   ├─ Within section, split on paragraph boundary
   ├─ Target passage length: ~1200 chars
   └─ Create chunk: {id, path, heading, text, source}

4. Build BM25 index
   └─ In-memory: for keyword search

5. Write to disk
   ├─ index.json: all chunks + fingerprint
   └─ Create embeddings.json metadata (no embeddings yet)

6. Log result
   └─ "Leading practice library: indexed 42 passages from 5 files"
```

### 3.2 Embedding Storage & Lazy Load

**First semantic search:**
```
User query: "month-end close"
    ↓
_chunk_embeddings(index) called
    ↓
Check cache:
  ├─ embeddings.npy exists?
  ├─ embeddings.json metadata matches fingerprint?
  └─ If both yes → load from disk (memory-mapped)
    ↓
If cache miss or mismatch:
  ├─ Load embedding model: "all-MiniLM-L6-v2"
  ├─ Encode all passages in index
  ├─ Save embeddings.npy (NumPy binary)
  ├─ Save embeddings.json (metadata)
  └─ Return embeddings
    ↓
Semantic search runs
    ↓
Results cached (with index fingerprint in key)
```

**Model sharing:**
- Same embedding model (`all-MiniLM-L6-v2`) used by LP and wiki search
- Loaded once (LRU cached in `wiki_query._embed_model`)
- Memory: ≈500 MB for model weights

---

## 4. LP Retention Policies

### 4.1 LP Index Files Retention

**Files:** `workspace/.lp_index/index.json`, `embeddings.npy`, `embeddings.json`

**Retention policy:** Current version only

**Cleanup:**
- On source file change: old embeddings overwritten (no history)
- On LP library folder delete: entire `.lp_index` directory may be cleaned up
- No automatic deletion based on time

**No archival:** Historical LP library versions not preserved.

---

### 4.2 LP Search Results Cache Retention

**Retention policy:** 300 seconds (5 minutes)

**Cleanup:** Automatic cache eviction

**Key invalidation:** When index fingerprint changes
- Old cache keys become "stale"
- New searches generate new keys
- Stale keys evicted on timeout

**No persistent storage:** Search queries/results not logged permanently.

---

### 4.3 LP Usage in RunEvents Retention

**Retention policy:** Permanent (tied to Run lifetime)

**Storage:** `run_events` table → indefinite

**Example RunEvent:**
```json
{
    "event_type": "lp_context_integrated",
    "lp_results_count": 5,
    "lp_chars_in_context": 4200
}
```

**Never deleted:** Part of audit trail for runs.

---

### 4.4 LP Usage in MemoryEvents Retention

**Retention policy:** 30 days (MEMORY_EVENTS_RETENTION_DAYS)

**Event type:** `lp_snippet_referenced`

**Example:**
```json
{
    "event_type": "lp_snippet_referenced",
    "snippet_id": "lp_456",
    "relevance_score": 0.92,
    "used_in_phase": "context_assembly"
}
```

**Cleanup:**
- Events >30 days old eligible for deletion
- Deletion is NOT automatic (must be triggered via admin)
- Fingerprint-based deduplication prevents duplicates

**Why 30 days?** Balances long-term trend analysis with data minimization.

---

### 4.5 LP in ProjectMemoryProfile Retention

**Retention policy:** Indefinite

**Storage location:** `project_memory_profiles` table

**Aggregated fields:**
```json
{
    "lp_usage": {
        "total_runs_with_lp": 5,
        "total_runs": 8,
        "lp_adoption_rate": 0.625,
        "avg_lp_snippets_per_run": 4.2
    }
}
```

**Cleanup:** Never automatically deleted.

**Why?** Aggregated memory persists for future engagement context.

---

## 5. LP Prompt Registry & Usage

### 5.1 LP Prompts in Registry

**Prompt file:** `config/prompts/lp_rag_answer.yaml`

```yaml
name: lp_rag_answer
version: 1
description: Answer a question from Leading Practice library passages, citing them by number.
system: |
  You answer questions for consultants using only the numbered passages from the firm's
  Leading Practice library given in the message.
  - Use only what the passages say. If they do not answer the question, say so in one sentence.
  - Cite the passage number in square brackets after each statement, for example [2].
  - Be brief: at most six sentences or six bullets. Plain text, no headings.
user: |
  Question: ${question}

  Passages:
  ${passages}
```

**Template variables:**
- `${question}` — User's question (required)
- `${passages}` — Numbered passages from search results (required)

---

### 5.2 When LP Prompts Are Used

#### 5.2.1 During Answer Generation (POST /api/lp-library/ask)

```python
# API endpoint
@router.post("/api/lp-library/ask")
def ask_lp_library(body: AskRequest) -> dict:
    return {
        "answer": leading_practice_library_service.answer(body.question),
        "sources": [list of passages cited]
    }

# Service call
def answer(self, question: str, *, max_results: int = 5) -> dict:
    final = run_lp_rag(question, max_results=max_results, want_answer=True)
    return {
        "answer": final.get("answer"),
        "sources": final.get("results")
    }

# RAG pipeline
def _generate(state: LPState) -> LPState:
    prompt = get_prompt("lp_rag_answer")
    passages = "\n\n".join(
        f"[{n}] {r['heading']}\n{r['text']}"
        for n, r in enumerate(state["results"], start=1)
    )
    answer = claude_generate(
        system=prompt.render_system(),
        user=prompt.render_user(question=state["query"], passages=passages),
        max_tokens=700,
    )
    return {"answer": answer.strip()}
```

**Captured in Run:**
- If answer was generated in context of a run, tracked in `prompts_used`
- Token usage recorded in RunEvent

---

#### 5.2.2 During Context Assembly (in Coordinator)

**NOT using lp_rag_answer prompt:**
- LP snippets retrieved via search (no LLM call)
- Formatted as `[LP]{heading}\n{text}`
- Passed directly to agents
- No prompt template involved

**Stored in context:**
```python
# In supervisor_execution.py, lines 556-598

# Search for LP snippets
lp_results = leading_practice_library_service.search(
    redacted,
    project_id=project_id,
    dpdp_enabled=dpdp_enabled,
)

# Additional searches for specific output types
for output_type in ["pptx", "docx"]:
    extra = leading_practice_library_service.search(
        f"{redacted}\n[OUTPUT: {label}]",
        project_id=project_id,
        dpdp_enabled=dpdp_enabled,
    )

# Format snippets for context
for r in lp_results:
    text = r.get("text")
    heading = r.get("heading") or ""
    prefix = f"[LP]{heading}".strip() if heading else "[LP]"
    lp_snippets.append(f"{prefix}\n{text}")

# Pass to coordinator state
state["lp_snippets"] = lp_snippets
```

**Flow:**
```
Context Assembly Phase
├─ Redacted instruction + process model
├─ LP search: main query
├─ LP search: per-output-type (PPTX, DOCX) with supplementary queries
├─ Deduplicate results
└─ Format as [LP]{heading}\n{text}
    ↓
Coordinator Planning Phase
├─ Uses: document_outline_strategy
├─ Uses: storyline_arc_recommender
├─ Input includes lp_snippets (raw text, not prompted)
└─ Planning output not directly using lp_rag_answer prompt
    ↓
Generation Phase
├─ Specialists receive lp_snippets in context
├─ PPTX agent may incorporate LP knowledge
├─ DOCX agent may incorporate LP knowledge
└─ No dedicated LP prompts; knowledge embedded in general prompts
```

---

## 6. LP Integration in Engagement Flow

### 6.1 Complete Engagement Lifecycle with LP

```
1. USER CREATES PROJECT
   └─ If LP_LIBRARY_LOCAL_PATH configured
      └─ LP index NOT built yet (lazy load)

2. USER STARTS CONVERSATION
   └─ No LP interaction at this stage

3. USER REQUESTS DELIVERABLE (approves plan)
   ├─ Run created
   ├─ Store: Run record
   └─ Execution scheduled

4. CONTEXT ASSEMBLY PHASE (Coordinator)
   ├─ Redacted text prepared
   │
   ├─ LP search triggered:
   │  ├─ Query: redacted instruction text
   │  ├─ Search type: keyword + semantic (fused)
   │  ├─ Results: up to 5 passages
   │  ├─ Cache key: lpsearch:{fingerprint}:{5}:{query_hash}
   │  └─ TTL: 300s
   │
   ├─ Supplementary LP searches (for PPTX, DOCX if requested):
   │  ├─ Query #1: "{redacted}\n[OUTPUT: Executive presentation]"
   │  ├─ Query #2: "{redacted}\n[OUTPUT: Detailed process document]"
   │  └─ Dedup results (same passage ID not included twice)
   │
   ├─ Format LP snippets:
   │  ├─ For each result: prefix = "[LP]{heading}"
   │  └─ Format: "[LP]{heading}\n{text}"
   │
   ├─ Assemble context:
   │  ├─ Conversation digest
   │  ├─ Project memory profile
   │  ├─ Wiki search results
   │  ├─ LP snippets ← HERE
   │  └─ Engagement metadata
   │
   └─ Store: lp_snippets in state
      └─ Optional: emit RunEvent ("lp_context_integrated")

5. PLANNING PHASE (Coordinator)
   ├─ Input: assembled context (includes lp_snippets)
   ├─ Uses: document_outline_strategy prompt
   ├─ Uses: storyline_arc_recommender prompt
   ├─ NOTE: NOT using lp_rag_answer prompt here
   └─ Output: execution plan

6. GENERATION PHASE (Specialists)
   ├─ PPTX specialist:
   │  ├─ Input: lp_snippets (raw text)
   │  ├─ Uses: archetype_proposal prompt (if proposal)
   │  ├─ Uses: storyline_spine_builder prompt
   │  ├─ Incorporates LP knowledge into slide content
   │  └─ No specific "lp_" prompt used
   │
   ├─ DOCX specialist:
   │  ├─ Input: lp_snippets (raw text)
   │  ├─ Uses: docx_sop_user, docx_narrative_user, etc.
   │  ├─ Incorporates LP knowledge into sections
   │  └─ No specific "lp_" prompt used
   │
   └─ Same for PDF, XLSX specialists

7. EVALUATION PHASE
   ├─ QA review (uses editorial_reviewer, visual_qa_reviewer)
   └─ No LP-specific evaluation

8. FINALIZE PHASE
   ├─ Export, theme, save artifacts
   └─ Artifacts may contain LP-sourced content

9. MEMORY AGGREGATION
   ├─ Update ProjectMemoryProfile:
   │  └─ lp_usage: { total_runs_with_lp, adoption_rate, ... }
   │
   └─ Store: MemoryEvent (optional)
      └─ "lp_snippet_referenced" events

10. COMPLETION
    ├─ Store: Run completed
    ├─ Store: Run.prompts_used (includes lp_rag_answer IF answer was generated separately)
    ├─ Cache: LP search results cached for 5 min (if rerun same query)
    └─ Memory events: kept for 30 days
```

---

### 6.2 Search + Retrieve Steps in Detail

**Step: LP Search Execution (in supervisor_execution.py)**

```python
# Line 556-598 in supervisor_execution.py

def assemble_context_with_lp(state: dict) -> dict:
    project_id = state.get("project_id")
    redacted = state.get("raw_text", "")  # Redacted for DPDP
    dpdp_enabled = bool(state.get("dpdp_flags", {}).get("enabled", True))
    
    lp_snippets: list[str] = []
    
    if project_id:
        try:
            # Main search
            lp_results = leading_practice_library_service.search(
                redacted,
                project_id=project_id,
                dpdp_enabled=dpdp_enabled,
            )
            
            # Tracking for dedup
            _lp_seen_ids: set[str] = {str(r.get("id")) for r in lp_results}
            
            # Supplementary searches for output types
            _output_labels = {
                "pptx": "Executive presentation",
                "docx": "Detailed process document"
            }
            
            for output_type, label in _output_labels.items():
                if output_type in (state.get("requested_outputs") or []):
                    try:
                        # Augment query with output type hint
                        augmented_query = f"{redacted}\n[OUTPUT: {label}]"
                        extra_results = leading_practice_library_service.search(
                            augmented_query,
                            project_id=project_id,
                            dpdp_enabled=dpdp_enabled,
                        )
                        
                        # Add only new results (not already seen)
                        for result in extra_results:
                            result_id = str(result.get("id") or "")
                            if result_id and result_id not in _lp_seen_ids:
                                lp_results.append(result)
                                _lp_seen_ids.add(result_id)
                    except Exception as exc:
                        _LOG.warning(
                            "LP extra search failed for output=%s: %s",
                            output_type, exc
                        )
            
            # Limit results
            lp_results = lp_results[:50]
            
            # Format for context
            for result in lp_results:
                text = result.get("text")
                heading = result.get("heading") or ""
                if isinstance(text, str) and text.strip():
                    prefix = f"[LP]{heading}".strip() if heading else "[LP]"
                    lp_snippets.append(f"{prefix}\n{text}")
        
        except Exception:
            lp_snippets = []
    
    state["lp_snippets"] = lp_snippets
    return state
```

---

### 6.3 Data Passed to Agents

**What agents receive:**

```python
# In planning phase
planning_context = {
    "instruction": "Create Q4 sales deck",
    "conversation_digest": "...",
    "project_memory": {...},
    "lp_snippets": [  # ← HERE
        "[LP]Financial Calendar\nMonth-end close should...",
        "[LP]Close Checklist\nSteps to follow...",
        "[LP]Timeline\nExpected duration..."
    ],
    "wiki_search_results": [...],
    "web_search_results": [...]
}

# All specialists receive same context
# They incorporate LP knowledge into output
```

---

## 7. LP Memory Events & Recording

### 7.1 LP Memory Event Types

**Event #1: LP snippet referenced in run**

```json
{
    "event_type": "lp_snippet_referenced",
    "timestamp": "2026-10-30T10:47:30Z",
    "run_id": "run_456",
    "project_id": "proj_123",
    "snippet_id": "lp_456",
    "snippet_heading": "Month-End Financial Close",
    "snippet_source": "library",
    "relevance_score": 0.95,
    "used_in_phase": "context_assembly",
    "used_by_agents": ["docx_agent", "pptx_agent"]
}
```

**Storage:** MemoryEvent table
**Fingerprint:** SHA256 of (project_id, run_id, event_type, snippet_id)
**Dedup:** Prevents duplicate events for same snippet in same run
**Retention:** 30 days

---

**Event #2: LP context integration completed**

```json
{
    "event_type": "lp_context_integration",
    "timestamp": "2026-10-30T10:47:00Z",
    "run_id": "run_456",
    "project_id": "proj_123",
    "phase": "context_assembly",
    "lp_library_configured": true,
    "lp_library_size": {
        "passages": 42,
        "fingerprint": "abc123...",
        "model": "all-MiniLM-L6-v2"
    },
    "main_search": {
        "query": "redacted instruction...",
        "results": 5,
        "cache_hit": false,
        "duration_ms": 245
    },
    "supplementary_searches": {
        "pptx": {
            "query": "redacted...[OUTPUT: Executive presentation]",
            "results": 3
        },
        "docx": {
            "query": "redacted...[OUTPUT: Detailed process document]",
            "results": 2
        }
    },
    "total_passages_used": 5,
    "total_lp_chars_in_context": 4200
}
```

**Storage:** RunEvent table (optional)
**Retention:** Permanent (part of run audit trail)

---

### 7.2 LP Memory Profile Aggregation

**Updated in ProjectMemoryProfile:**

```json
{
    "project_id": "proj_123",
    "summary_json": {
        "lp_engagement": {
            "total_runs_executed": 12,
            "runs_with_lp": 8,
            "lp_adoption_rate": 0.667,
            "avg_lp_snippets_per_run": 4.2,
            "total_lp_snippets_used": 34,
            "most_referenced_snippets": [
                {
                    "id": "lp_456",
                    "heading": "Month-End Financial Close",
                    "reference_count": 5
                },
                {
                    "id": "lp_789",
                    "heading": "Close Checklist",
                    "reference_count": 4
                }
            ]
        }
    },
    "updated_at": "2026-10-30T10:47:30Z"
}
```

**Updated:** After each run that uses LP
**Retention:** Indefinite

---

## 8. Complete LP Data Flow

### 8.1 Full Data Journey

```
┌──────────────────────────────────────────────────────────────────┐
│               LEADING PRACTICE LIBRARY DATA FLOW                  │
└──────────────────────────────────────────────────────────────────┘

USER ACTION (e.g., POST /api/lp-library/ask)
    ↓
QUERY INPUT
├─ question: "How fast should month-end close be?"
├─ project_id: "proj_123"
└─ max_results: 5
    ↓
LP SEARCH SERVICE INVOKED
├─ Check cache: lpsearch:{fingerprint}:{5}:{query_hash}
├─ Cache miss → Run RAG pipeline
└─ Cache hit → Return cached results immediately
    ↓
RAG PIPELINE EXECUTION
│
├── Node: load_index
│   ├─ Load: workspace/.lp_index/index.json
│   └─ Count passages (e.g., 42)
│
├── Node: prepare_query
│   ├─ Trim to 32 most-frequent non-stopwords
│   └─ Result: "month-end close duration timeline"
│
├── Node: keyword (BM25)
│   ├─ Query: index.bm25
│   └─ Return: top 20 passages by BM25 score
│
├── Node: semantic (embedding)
│   ├─ Load model: "all-MiniLM-L6-v2"
│   ├─ Load/compute embeddings: workspace/.lp_index/embeddings.npy
│   └─ Return: top 20 passages by cosine similarity (>=0.3)
│
├── Node: fuse (reciprocal rank fusion)
│   ├─ Merge keyword + semantic rankings
│   └─ Score each passage: 0-1 (normalized)
│
├── Node: select
│   ├─ Deduplicate by passage text
│   └─ Keep top 5 (max_results)
│
├── Node: generate (optional, only if want_answer=true)
│   ├─ Load prompt: lp_rag_answer
│   ├─ Render:
│   │  └─ user: "Question: ${question}\n\nPassages: ${passages}"
│   ├─ Call LLM:
│   │  ├─ System: "You answer using only the passages..."
│   │  └─ Max tokens: 700
│   └─ Result: Formatted answer with [1], [2], [3] citations
│
└─ Return: {results: [...], answer: "..."}
    ↓
CACHE STORAGE
├─ Key: lpsearch:{fingerprint}:{max_results}:{query_hash}
├─ Value: {results: [...]}
└─ TTL: 300 seconds
    ↓
METRICS RECORDING
├─ Counter: lp_rag_searches_total (incremented)
├─ Counter: lp_rag_answers_total (if answer generated)
└─ Latency: observed (search duration ms)
    ↓
IF USED IN RUN CONTEXT
├─ Stored in: state["lp_snippets"]
├─ Passed to: All downstream agents
├─ Format: "[LP]{heading}\n{text}"
└─ Optional: emit RunEvent ("lp_context_integrated")
    ↓
INTEGRATION INTO DELIVERABLES
├─ PPTX specialist: Incorporates LP knowledge in slides
├─ DOCX specialist: Incorporates LP knowledge in sections
├─ PDF specialist: Incorporates LP knowledge in narrative
└─ XLSX specialist: May reference LP in metadata
    ↓
MEMORY RECORDING (AFTER RUN)
├─ Store: MemoryEvent (lp_snippet_referenced)
├─ Retention: 30 days
├─ Update: ProjectMemoryProfile (lp_engagement stats)
└─ Retention: Indefinite
    ↓
COMPLETION
├─ Cache: expires after 300 seconds (refresh on next query)
├─ Index: remains until source files change
├─ Embeddings: remain until index rebuild
├─ Memory events: kept for 30 days then eligible for deletion
└─ Run artifacts: kept indefinitely
```

---

### 8.2 Engagement Example: Complete Timeline

```
Oct 30, 10:00 AM
├─ User creates project "Q4 Sales Deck"
└─ LP_LIBRARY_LOCAL_PATH configured: /shared/lp_library

Oct 30, 10:30 AM - First user request
├─ User: "Create Q4 sales deck for finance team"
└─ No LP invoked yet (conversation only)

Oct 30, 11:00 AM - User approves execution plan
├─ Run created (run_456)
├─ LP index built (lazy load on first access)
│  ├─ Source files read: 5 files
│  ├─ Passages created: 42 passages
│  ├─ BM25 index built: in-memory
│  ├─ Fingerprint: abc123... (stored in index.json)
│  └─ Embeddings NOT built yet (lazy)
├─ Store: Run record
└─ Execution starts

Oct 30, 11:05 AM - Context Assembly Phase
├─ Query generated: "Create Q4 sales deck finance team executives..."
├─ LP search executed
│  ├─ Keyword search: returns 8 passages
│  ├─ Semantic search: loads model (first time, ~3 sec)
│  │  ├─ Encodes all 42 passages
│  │  ├─ Saves embeddings.npy (computed)
│  │  ├─ Returns 6 passages by similarity
│  │  └─ Saves embeddings.json (metadata)
│  ├─ Fusion: merges ranks → 5 passages with scores
│  └─ Cache: stored with key lpsearch:abc123:5:9f86d081...
│     └─ TTL: 300 seconds
│
├─ Supplementary searches:
│  ├─ "...finance team....[OUTPUT: Executive presentation]" → 3 passages
│  ├─ "...finance team....[OUTPUT: Detailed process document]" → 2 passages
│  └─ Deduplicated: 5 total new passages
│
├─ LP snippets formatted:
│  ├─ "[LP]Financial Calendar\n..."
│  ├─ "[LP]Sales Process\n..."
│  └─ 5 more snippets
│
├─ Store: state.lp_snippets (in memory)
├─ Optional emit: RunEvent (lp_context_integrated)
└─ Metrics: lp_rag_searches_total++ (now 1)

Oct 30, 11:07 AM - Planning Phase
├─ Context assembled (includes lp_snippets)
├─ Uses: document_outline_strategy prompt
├─ Uses: storyline_arc_recommender prompt
└─ Generates: execution plan

Oct 30, 11:15 AM - Generation Phase
├─ PPTX specialist
│  ├─ Input: lp_snippets (raw text)
│  ├─ Uses: archetype_proposal, storyline_spine_builder
│  └─ Output: draft slides (incorporating LP knowledge)
│
└─ DOCX specialist
   ├─ Input: lp_snippets (raw text)
   ├─ Uses: docx_narrative_user, docx_sop_user
   └─ Output: draft sections (incorporating LP knowledge)

Oct 30, 11:45 AM - Evaluation & Finalize
├─ QA gates passed
└─ Final artifacts saved

Oct 30, 12:00 PM - Memory Aggregation
├─ MemoryEvent created:
│  ├─ event_type: "lp_snippet_referenced"
│  ├─ Fingerprint: hash of (proj, run, event, snippet_id)
│  ├─ Retention start: now (Oct 30, 12:00 PM)
│  └─ Retention end: Nov 29, 12:00 PM (30 days)
│
├─ ProjectMemoryProfile updated:
│  ├─ lp_engagement.runs_with_lp: 1
│  ├─ lp_engagement.total_runs: 1
│  ├─ lp_engagement.adoption_rate: 1.0
│  ├─ lp_engagement.avg_lp_snippets: 5.0
│  └─ most_referenced_snippets: [...]
│
└─ Metrics: lp_rag_searches_total = 2 (including any subsequent searches)

Oct 30, 12:05 PM - Same user, new request
├─ User: "Actually, include our process models too"
├─ LP search with similar query
├─ Cache HIT! (lpsearch:abc123:5:9f86d081...)
│  └─ Returns cached results (fresh < 300 sec)
│
└─ Metrics: lp_rag_searches_total unchanged (already counted in context)

Oct 30, 12:10 PM
├─ Cache expires (300 seconds elapsed)
└─ Next LP search will rebuild & cache

Oct 31, 12:00 PM (24 hours later)
├─ Index still in memory (no source changes)
├─ Embeddings still in cache (no rebuild)
├─ MemoryEvent still retained (only 1 day old / 29 days left)
└─ ProjectMemoryProfile still tracking LP usage

Nov 29, 12:01 PM (30 days later)
├─ MemoryEvent eligibility: NOW ELIGIBLE FOR DELETION
├─ Admin cleanup job may delete it
└─ ProjectMemoryProfile: STILL RETAINED (aggregated, no expiry)

Nov 29, 11:55 AM
├─ If source files change (e.g., new LP document added)
├─ Index rebuild triggered
│  ├─ Fingerprint changes
│  ├─ Cache invalidated (old keys ignored)
│  ├─ Embeddings deleted (old .npy file)
│  └─ New embeddings computed on next semantic search
└─ All future searches use new fingerprint
```

---

## Summary

### LP Memory Capture Points
1. **Search queries** — Cached, not logged
2. **Search results** — Cached (5 min), indexed passages (persistent)
3. **Answer generation** — Optional, prompted via lp_rag_answer
4. **Run integration** — Stored in lp_snippets, passed to agents
5. **Usage recording** — MemoryEvent (30 days retention)
6. **Aggregation** — ProjectMemoryProfile (indefinite)

### LP Data Storage
1. **Index** — `workspace/.lp_index/index.json` (persistent, fingerprinted)
2. **Embeddings** — `embeddings.npy` (lazy-loaded, recomputed on rebuild)
3. **Cache** — Redis/in-memory (300s TTL)
4. **Database** — RunEvent, MemoryEvent (permanent/30-day)

### LP Retention
- **Cache:** 300 seconds
- **Index:** Until source change
- **Embeddings:** Until index rebuild
- **MemoryEvents:** 30 days (configurable)
- **ProjectMemoryProfile:** Indefinite
- **RunEvents:** Permanent

### LP Prompts
- **One prompt:** `lp_rag_answer` (for answer generation)
- **Usage context:** Embedded in coordinator context, not called per specialist
- **Token tracking:** Counted if answer generated in-run

