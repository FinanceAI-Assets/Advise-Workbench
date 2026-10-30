# Leading Practice Library — Data & Memory Architecture

How the Leading Practice Library is indexed, stored, searched, and integrated throughout the application.

## What the Library Is

The Leading Practice Library (LP) is a **searchable knowledge base** with two possible sources:

| Source | Location | Files |
|---|---|---|
| **Library folder** | `LP_LIBRARY_LOCAL_PATH` in `.env` | `.md` and `.txt`, any depth |
| **Shared wiki** | `<workspace>/leading_practices/wiki` | `.md` pages |

**Initial state:** Empty by default. Set `LP_LIBRARY_LOCAL_PATH` to a folder of Markdown or text files to populate the library.

---

## Data Storage & Indexing

**Module:** [`src/memory/knowledge/lp_index.py`](../../src/memory/knowledge/lp_index.py)

**Index directory:** `<workspace>/.lp_index/`

### File Chunking

Each source file is segmented into **passages**:
- New passage at every Markdown heading (`#` to `######`)
- Within a section, new passage every ~1,200 characters on a paragraph boundary
- Passages preserve heading context and source attribution

### Index Files

| File | Format | Purpose |
|---|---|---|
| `index.json` | JSON | Passages: `id`, `path`, `heading`, `text`, `source` |
| `embeddings.npy` | NumPy binary | Dense vectors (float32, normalized), one row per passage |
| `embeddings.json` | JSON | Metadata: index fingerprint, embedding model name |

### Passage Structure

```json
{
  "id": "sha256_hash[:16]",
  "path": "/path/to/source/file",
  "heading": "Section heading (max 120 chars)",
  "text": "Passage body",
  "source": "library" | "wiki"
}
```

### Index Lifecycle

| Event | Behavior |
|---|---|
| **Fresh start** | No index; built on first search or manual refresh |
| **30s rescan** | Source folders checked for changes (add/modify/delete) |
| **File changed** | Fingerprint mismatch → index rebuilt; embeddings recomputed |
| **Explicit rebuild** | `POST /api/lp-library/refresh` forces immediate rebuild |
| **Semantic search** | Embeddings loaded lazily on first use; model: `all-MiniLM-L6-v2` |

---

## Retrieval Pipeline (LangGraph)

**Module:** [`src/memory/knowledge/lp_rag.py`](../../src/memory/knowledge/lp_rag.py)

A 7-node state machine coordinating keyword search, semantic search, and answer generation:

```
START → load_index → prepare_query → [keyword ⫽ semantic] → fuse → select → [generate] → END
           ↓                                                                      ↓
        (empty) → END                                                    (no answer) → END
```

### Node Descriptions

| Node | Input | Output | Logic |
|---|---|---|---|
| **load_index** | — | `passages: int` | Load index from disk; conditional exit if empty |
| **prepare_query** | `query: str` | `search_text: str` | Trim to 32 most-frequent non-stopword terms; skip common words |
| **keyword** | `search_text: str` | `keyword_hits: list[(pos, score)]` | BM25 full-text search; top 20 passages |
| **semantic** | `search_text: str` | `semantic_hits: list[(pos, score)]` | Embedding similarity ≥0.3 (skipped if `LP_RAG_SEMANTIC_ENABLED=false`); top 20 |
| **fuse** | Both hit lists | `fused: list[(pos, score)]` | Reciprocal Rank Fusion (k=60); merges ranks into 0–1 score |
| **select** | `fused`, `max_results` | `results: list[chunk]` | Drop duplicates; keep top N; add `relevance_score` to each |
| **generate** | `results`, `query`, `want_answer` | `answer: str` | *If asked:* call model to answer using passages; cite by `[1]`, `[2]`, etc. |

### Scoring

- **relevance_score:** Rank-based (0–1), derived from RRF. A passage ranked first by both keyword and semantic receives ~1.0; near-ties rank lower.
- **Not confidence:** The score reflects ranking position, not match strength. A weak search's second-best passage can still score close to 1.0.

### Tracing

Each node emits a trace span under `rag.lp.*`:
- Span name: `rag.lp.<node>`  
- Attributes: query length, node-specific counts (hits, results, passages)
- Parent: `rag.lp` (the search/answer as a whole)

---

## Memory Service Layer

**Module:** [`src/memory/knowledge/leading_practices.py`](../../src/memory/knowledge/leading_practices.py)

```python
class LeadingPracticeLibraryService:
    
    def ensure_index(*, force: bool = False) -> None:
        """Ensure the index is loaded; optionally force a rebuild."""
    
    def search(query: str, *, project_id: str | None, max_results: int = 5) -> list[dict]:
        """Return up to `max_results` passages matching the query.
        
        Returns:
            [{"id", "path", "heading", "text", "source", "relevance_score"}, ...]
        """
    
    def answer(question: str, *, max_results: int = 5) -> dict:
        """Return an answer written from the library, with cited sources.
        
        Returns:
            {"answer": str, "sources": list[chunk]}
        """
```

### Caching

- **TTL:** 5 minutes
- **Key:** `lpsearch:{index_fingerprint}:{max_results}:{query_sha256[:16]}`
- **When:** Every successful search; skipped if cache hit

---

## HTTP API

**Module:** [`src/app/api/lp_library.py`](../../src/app/api/lp_library.py)

All endpoints require project role (`Owner`, `Editor`, or `Viewer`).

### Endpoints

| Method | Path | Body | Returns | Use |
|---|---|---|---|---|
| **GET** | `/api/lp-library/search` | `q` (query param) | `{project_id, query, items: [chunks]}` | UI search bar |
| **POST** | `/api/lp-library/ask` | `{project_id, question}` | `{project_id, question, answer, sources}` | Get cited answer |
| **POST** | `/api/lp-library/refresh` | `{project_id}` | `{status}` | Rebuild index |
| **GET** | `/api/lp-library/bookmarks` | `project_id` (param) | `[{item_id, note, ...}]` | Per-project bookmarks |
| **POST** | `/api/lp-library/bookmarks` | `{project_id, item_id, note}` | `{status}` | Save bookmark |
| **DELETE** | `/api/lp-library/bookmarks` | `project_id`, `item_id` (params) | `{status}` | Remove bookmark |

### Example Requests

**Search:**
```bash
GET /api/lp-library/search?project_id=abc&q=month-end+process
```

**Ask (with answer):**
```bash
POST /api/lp-library/ask
{
  "project_id": "abc",
  "question": "How fast should month-end close?"
}

# Response:
{
  "answer": "Month-end should close within [1] 3–5 business days, per the financial calendar best practice...",
  "sources": [
    {
      "id": "...",
      "heading": "Financial Calendar",
      "text": "...",
      "relevance_score": 0.95
    }
  ]
}
```

---

## Integration Points

| Consumer | Module | Pattern | Use |
|---|---|---|---|
| **UI Search** | Frontend wiki component | `GET /api/lp-library/search` | Real-time search suggestions |
| **Run Enrichment** | `src/agents/supervisor_execution.py` | Coordinator calls service | 1–2 LP snippets contextualize run tasks |
| **Tool Call** | `src/tools/registry.py` (`search_leading_practices`) | Document agents invoke tool | Research during content generation |
| **Conversation** | `src/agents/conversation/storyline_builder.py` | Storyline builder, slide negotiator | 2 LP snippets per narrative arc/slide option |

---

## Configuration

Set in `.env`:

```ini
# Path to library folder (optional; no library by default)
LP_LIBRARY_LOCAL_PATH=/path/to/practices/folder

# Enable semantic search; disable to skip embedding load
LP_RAG_SEMANTIC_ENABLED=true
```

---

## Related Resources

| Resource | Purpose |
|---|---|
| [`config/prompts/lp_rag_answer.yaml`](../../config/prompts/lp_rag_answer.yaml) | System & user prompts for answer generation |
| [`docs/03-design/leading-practice-rag.md`](../03-design/leading-practice-rag.md) | Detailed pipeline design & verification |
| [`tests/unit/test_lp_rag.py`](../../tests/unit/test_lp_rag.py) | Retrieval & answer generation tests |

---

## Key Design Decisions

1. **Dual search (keyword + semantic):** Catches both exact matches and meaning-based relevance; gracefully falls back to keywords if embeddings unavailable.
2. **Lazy embedding load:** Semantic model only loaded when first needed; saves startup time and memory.
3. **Reciprocal Rank Fusion:** Prevents one search method from dominating; balances precision (keyword) vs. recall (semantic).
4. **Fingerprint-based change detection:** Avoids expensive re-indexing during startup; 30s rescan window batches file changes.
5. **In-memory BM25 index:** No external service; searches complete in milliseconds.
6. **Passage deduplication at select time:** Allows both searches to find the same passage without duplication in results.
7. **Typed state machine (LangGraph):** Enforces contract between nodes; easier to add nodes or rearrange later.

---

## Roadmap & Limitations

### Not Yet Implemented

- `.pdf`, `.docx`, `.pptx` files in the library folder are not indexed
- OneDrive / Microsoft Graph integration (mentioned in older code, not implemented)
- Query rewriting by LLM; no reranker model
- UI calls to `/api/lp-library/ask` (endpoint exists, not wired to frontend)

### Future Enhancements

- Reranker model to fine-tune top-K results
- LLM-based query expansion or rewriting
- Passage-level tagging (e.g., industry, function) for filtering
- Incremental index updates (append-only, not full rebuild)

