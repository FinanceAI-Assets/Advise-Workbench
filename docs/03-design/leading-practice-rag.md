# Leading Practice library: retrieval pipeline

How the Leading Practice library is indexed and searched. The search is a LangGraph graph; every caller of `leading_practice_library_service.search` goes through it.

## What the library is

| Source | Where | Files |
|---|---|---|
| Library folder | The folder named by `LP_LIBRARY_LOCAL_PATH` in `.env` | `.md` and `.txt`, any depth |
| Leading-practice wiki | `<workspace>/leading_practices/wiki` | `.md` pages |

With neither present the library is empty and every search returns nothing. That is the state of a fresh install: set `LP_LIBRARY_LOCAL_PATH` to a folder of Markdown or text files to fill it.

## Index

`src/memory/knowledge/lp_index.py`

- Each file is cut into passages: a new passage at every Markdown heading, and within a section a new passage about every 1,200 characters, on a paragraph boundary.
- Passages are stored in `<workspace>/.lp_index/index.json`; their embeddings (model `all-MiniLM-L6-v2`, the same one the wiki search uses) in `embeddings.npy` next to it. Embeddings are computed on the first search that needs them.
- The source folders are re-checked at most every 30 seconds. The index is rebuilt when a file is added, changed or removed. `POST /api/lp-library/refresh` forces a rebuild.

## The graph

`src/memory/knowledge/lp_rag.py`

```
START -> load_index -> prepare_query -> keyword  -> fuse -> select -> generate -> END
             |                       -> semantic ->            |
             +--> END (library is empty)                       +--> END (no answer asked for)
```

| Node | What it does |
|---|---|
| `load_index` | Loads the passages; ends the search when the library is empty |
| `prepare_query` | Some callers pass a whole document as the query. Queries with more than 32 meaningful terms are cut to their 32 most frequent terms |
| `keyword` | BM25 search, best 20 passages |
| `semantic` | Embedding search, best 20 passages with similarity of at least 0.3. Runs alongside `keyword`. Skipped with `LP_RAG_SEMANTIC_ENABLED=false`; if the embedding model cannot be loaded, the search continues on keywords alone |
| `fuse` | Merges the two rankings by reciprocal rank fusion. A passage ranked first by both gets `relevance_score` 1.0 |
| `select` | Drops repeated passages and keeps the best `max_results` |
| `generate` | Only for `answer()`: asks the model to answer from the selected passages and cite them by number. The prompt is `config/prompts/lp_rag_answer.yaml` |

Each node is one trace span (`rag.lp.<node>`) under `rag.lp`.

`relevance_score` is rank-based: it says how high a passage ranked, not how strongly it matches. The second-best passage of a weak search can still score close to 1.

## Callers

| Caller | Use |
|---|---|
| `GET /api/lp-library/search` | Search from the UI |
| `POST /api/lp-library/ask` (new) | Body `{"project_id", "question"}`; returns `answer` and the `sources` it cites |
| `search_leading_practices` tool (`src/tools/registry.py`) | Document agents |
| Coordinator (`src/agents/supervisor_execution.py`) | Leading practice snippets for a run |
| Storyline builder and slide negotiator (`src/agents/conversation/`) | Two snippets per storyline arc or slide |

The result shape is unchanged (`id`, `path`, `heading`, `text`, `relevance_score`), plus `source` (`library` or `wiki`).

## What changed from before

The earlier search compared query words with passage words and kept only the first 2,000 characters of each top-level section. Its indexer also failed on any real content (it hashed a text string where bytes were required, and the error was swallowed), so with a library folder set, search still returned nothing. Results are cached for 5 minutes as before; the cache key now includes the index version and `max_results`.

## How it was verified

- `tests/unit/test_lp_rag.py` (9 tests): passages by heading, keyword match, a match by meaning with no shared words, a passage found by both searches ranking first, a whole document as the query, rebuild after a file change, empty library, an answer written through the registry prompt, registry files valid. The tests use a small stand-in embedder.
- Live check on 2026-10-06 with the real embedding model and a five-passage sample library: "how fast should month-end finish" returned the close calendar passage, "stop fraudulent vendor bank changes" returned supplier onboarding, and an unrelated query returned nothing. First search 4 seconds (model load), later ones about 20 ms.

## Not done

- `.pdf`, `.docx` and `.pptx` files in the library folder are not read.
- The OneDrive / Microsoft Graph source named in the earlier code comment does not exist.
- No reranking model and no query rewriting by the model; retrieval makes no model call.
- `answer()` has only been tested with a stubbed model, and no UI calls `/ask` yet.
