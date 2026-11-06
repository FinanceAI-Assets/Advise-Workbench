# Query pipeline: Sheldon, Talk to data and the Query API

Every question answered from documents takes one path, the query pipeline. It answers from an engagement's uploaded documents and/or the approved Leading Practice Library, cites `[S#]` sources, and says "insufficient evidence" instead of guessing. The pipeline is used in three places:

| Where | How it reaches the pipeline | What it searches |
|---|---|---|
| Engagement **Conversation** (Sheldon) | Sheldon's router agent sends document questions to the **rag_agent** | The engagement's uploaded documents + the Leading Practice Library |
| Leading Practice Library → **Talk to data** | `POST /api/library/ask` → rag_agent (content questions; catalog questions such as counts and owners are answered directly) | The library (or only the selected practices) |
| Any other caller, Postman, tests | `POST /api/query` | What the request asks for |

The live schema is at `/docs` (Swagger) and `/openapi.json` under the `query` tag.

## Code map

| File | Purpose |
|---|---|
| `src/agents/conversation/sheldon_router_agent.py` | Picks the agent for a Sheldon message: `rag`, `supervisor` (deliverables: discovery → plan → "go" → run) or `conversation` (chat) |
| `src/agents/conversation/rag_agent.py` | Calls the pipeline and turns its result into Sheldon's message (answer + sources, or why there is none) |
| `src/query/service.py` | The single entry point: access check, then the pipeline (`ask`, `source`) |
| `src/query/pipeline.py` | Understanding → retrieval → answer → error handling |
| `src/app/api/documents.py` | Engagement uploads: `/api/documents/upload`, `/list`, `/status/{job_id}`, `/reindex`, `/delete`. Upload queues the ingestion pipeline |
| `src/workers/pipeline.py` | The ingestion pipeline (Celery): SeaweedFS → Docling → chunks (Postgres) → embeddings (Qdrant), for the library and for engagements |
| `src/app/api/query.py` | `POST /api/query`, `/health`, `/sources/...` |
| `src/app/api/projects/conversation.py` | Sheldon's turn: `_turn_respond` asks the router agent; `_persist_rag_response` stores the rag_agent's reply |
| `src/workflows/task_router/conversation_router.py` | The per-message router LLM call; intent `knowledge_question` marks document questions |

## Engagement documents: upload and processing

Engagement uploads go through the same ingestion pipeline as the Leading Practice Library, in the background:

1. `POST /api/documents/upload` (form-data: `project_id`, `file`; Owner or Editor):
   - Saves the file to the engagement's workspace, as before; other features read it from there.
   - Stores the file in SeaweedFS (S3) and queues the pipeline.
   - Returns at once with `ingestion: {job_id, status, ...}`.
2. A Celery worker runs `uploading → parsing (Docling, OCR for scanned PDFs) → chunking → embedding`:
   - Passages go to Postgres (`chunk_archive`), and vectors to Qdrant (`document_chunks`), with `project_id` = the engagement id.
   - An engagement's passages are never shared with the library or with another engagement.
3. When the job is `completed` (`ingestion.searchable: true`), Sheldon's answers include the document.
   - Until then, Sheldon's reply names it as "still processing".

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload; returns `ingestion` |
| `GET` | `/api/documents/list?project_id=` | Every document with its latest `ingestion` (`items` is kept for older callers) |
| `GET` | `/api/documents/status/{job_id}?project_id=` | Poll one document: `status`, `stage`, `progress_percent`, `chunk_count`, `error` |
| `POST` | `/api/documents/reindex?project_id=` | Queue every document again: uploads from before the pipeline, or after a failure (unchanged content completes at once) |
| `DELETE` | `/api/documents/delete?project_id=&filename=` | Removes the file and the pipeline's copy (S3 object, passages, vectors) |

**Re-uploading a file with the same name replaces it:**
- The old version stays searchable until the new one is processed, then it is removed.
- If the broker or S3 is down, the upload still succeeds, with `ingestion.status: "failed"` and the reason. Use `/reindex` once the service is back.

## Sheldon flow

1. The user sends a message: `POST /api/projects/{pid}/conversation/messages` (the UI uses `?background=true` and polls the turn).
2. The conversation router (one LLM call) classifies it. `sheldon_router_agent.route` turns that into an agent:
   - **rag**: intent `knowledge_question` ("what does the workshop say about vendor master changes?"), or, when the router is unavailable, a question with no deliverable request outside a deliverable flow.
   - **supervisor**: the message asks to create a deliverable ("create a deck on …"), or the conversation is in a deliverable flow (discovery, storyline, slides, plan).
   - **conversation**: everything else (greetings, thanks, chat).
3. rag → `rag_agent.answer(engagement_id=pid)` → `service.ask` (checks membership) → pipeline. Earlier messages of the thread are passed, so follow-ups ("and who approves it?") work.
4. The reply is stored as an assistant message:
   - `content`: the answer with `[S1]` markers, then a numbered `Sources:` list, with each source marked as an engagement document or the Leading Practice Library. If nothing supports an answer, it is a plain sentence.
   - `metadata`: `{kind: "rag_answer", status, reason, citations, sources, coverage, retrieval, scope}`. The `citations` have the same shape as in the API below.

## Talk to data

`POST /api/library/ask` `{question, practiceIds?, maxResults?}` keeps its response shape, so `TalkToData.tsx` works unchanged:

- **Response:** `{answer, practices, documents, sources}`. For a content question, the citations are renumbered `[1]`, `[2]` …, and `sources[i]` is `[i+1]`.
- **Extra fields:** `status`, `reason` and `citations` (the full citation objects).

## Query API

Auth for every call: `Authorization: Bearer <access token>` from `POST /api/auth/login` `{email, password}`. `POST /api/query` is rate-limited per caller (`QUERY_RATE_LIMIT`, default 30/minute).

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/query` | Ask a question |
| `GET` | `/api/query/health` | Whether questions can be answered right now, plus limits |
| `GET` | `/api/query/sources/{chunk\|wiki}/{id}` | A cited source in full (`citations[].link`); an engagement passage needs `?engagement_id=` |

### Ask

```http
POST /api/query
{ "question": "How long do vendor master changes take?",
  "engagement_id": "p_3ac35e5cff",
  "include_library": true }
```

| Field | Default | Meaning |
|---|---|---|
| `question` | required | 2–2,000 characters |
| `engagement_id` | none | Also search this engagement's uploaded documents. The caller must be a member (Owner, Editor or Viewer), otherwise `403` |
| `include_library` | `true` | Search the approved Leading Practice Library (published versions only) |
| `practice_ids` | `[]` | Only these library practices |
| `history` | `[]` | Earlier turns `[{role: "user"\|"assistant", content}]` for follow-ups. The API is stateless |
| `top_k` | 10 | Sources given to the model (1–12) |

Response (shortened):

```json
{
  "status": "answered", "reason": null,
  "question": "How long do vendor master changes take?",
  "standalone_question": "How long do vendor master changes take?",
  "answer": "Vendor master changes need an IT ticket and take nine days on average [S1].",
  "answer_markdown": "... on average [S1](<sha>:3).",
  "citations": [
    { "ref": "S1", "type": "chunk", "scope": "engagement", "id": "pas_9c1e...", "title": "workshop-notes.txt, page 4",
      "filename": "workshop-notes.txt", "page_number": 4, "chunk_number": 3, "practice_id": null,
      "score": 0.82, "verification": 1.0, "snippet": "Vendor master changes require ...",
      "link": "/api/query/sources/chunk/pas_9c1e...?engagement_id=p_3ac35e5cff", "markdown": "[workshop-notes.txt, page 4](pas_9c1e...)" }
  ],
  "sources": [ { "type": "chunk", "scope": "library", "id": "...", "title": "Vendor onboarding, page 3", "...": "..." } ],
  "coverage": { "claims": 1, "cited": 1, "ratio": 1.0, "uncited": [], "fully_cited": true, "invalid_refs": [] },
  "understanding": { "intent": "fact", "question_type": "how", "is_follow_up": false, "...": "..." },
  "variants": [], "queries": [],
  "retrieval": { "candidates": 41, "engagement_candidates": 6, "verified": 29, "dropped_low_verification": 0,
                 "top_score": 0.82, "reranker": "keyword", "final": 10, "pending_documents": [] },
  "answer_metadata": { "provider": "claude_cli", "model": "...", "attempts": 1, "errors": [], "latency_ms": 2900 },
  "model_calls": 1, "timings_ms": { "understanding": 40, "retrieval": 120, "answer": 2900, "total": 3070 }
}
```

Source fields:

- **`type`:** `chunk` (a passage) or `wiki` (a library wiki page, scored against its source passages).
- **`scope`:** `engagement` (an engagement upload; its `link` carries `?engagement_id=`) or `library`.
- **`retrieval.pending_documents`:** engagement uploads still being processed, so not searched yet.

### Status and reason

| `status` | `reason` | What happened |
|---|---|---|
| `answered` | `null` | The answer is grounded in the sources, with citations |
| `insufficient_evidence` | `no_results` | Nothing matched |
| `insufficient_evidence` | `low_confidence` | There were only weak matches |
| `insufficient_evidence` | `low_verification` | There were matches, but none was well supported by its source documents |
| `insufficient_evidence` | `model_declined` | The sources didn't answer the question |
| `insufficient_evidence` | `uncited_answer` | The draft answer cited too few of its statements |
| `llm_unavailable` | `llm_failed` | The model failed after its retries. `sources` lists what was found |

For any status other than `answered`, `answer` holds a ready-made message.

### Errors

| HTTP | When |
|---|---|
| `401` | Missing or expired token |
| `403` | `engagement_id` is not one of the caller's engagements |
| `404` | Source not found, not published, or in an engagement the caller can't read |
| `422` | Invalid body, or nothing to search (`include_library: false` without `engagement_id`) |
| `429` | Rate limit exceeded |
| `503` | Search is down (embedding service or Qdrant). Retry later; `/api/query/health` shows when it is back |

## Testing with Postman

Before you start, the API and a Celery worker must be running, along with RabbitMQ, SeaweedFS, Postgres, Qdrant and
the embedding service (`scripts/check_shared_services.py --env .env`).

1. `POST {{base}}/api/auth/login` with body `{"email": "...", "password": "..."}`. Copy `access_token`.
2. Set the header `Authorization: Bearer <access_token>` on every request below.
3. Engagement: use an existing one, or `POST {{base}}/api/projects` with `{"name": "Test"}` and copy `id`.
4. Upload: `POST {{base}}/api/documents/upload`, body form-data `project_id=<id>` and `file=<your file>`. Copy `ingestion.job_id`.
5. Wait for processing: `GET {{base}}/api/documents/status/<job_id>?project_id=<id>` until `ingestion.status` is `completed`.
   If it is `failed`, `ingestion.error` says why; fix it and call `POST {{base}}/api/documents/reindex?project_id=<id>`.
6. Through Sheldon: `POST {{base}}/api/projects/<id>/conversation/messages` with `{"content": "What does the workshop say about vendor master changes?"}`.
   The last message in `messages` is Sheldon's reply, with `metadata.kind == "rag_answer"` and citations naming your file.
   With `?background=true` you get a `turn_id`; poll `GET {{base}}/api/projects/<id>/conversation/turns/<turn_id>` until `status` is `done`.
7. The pipeline directly: `POST {{base}}/api/query` with `{"question": "...", "engagement_id": "<id>", "include_library": false}`.
8. Open a source: `GET {{base}}<citations[0].link>`.
9. Delete: `DELETE {{base}}/api/documents/delete?project_id=<id>&filename=<file>`. Ask again: you should get `insufficient_evidence`.
10. Library question (needs a released practice): `POST {{base}}/api/query` with `{"question": "What are the leading practices for three-way match?"}`.

## How the pipeline answers

1. **Understanding**:
   - Works out the intent, question type, entities, keywords and language.
   - Rewrites a follow-up into a standalone question using the earlier turns.
   - Adds variants: focused, keywords, and an English translation for a non-English question. With `QUERY_LLM_VARIANTS=always`, it also adds a model-written rewrite and a paraphrase.
   - Drops variants that drift off-topic and searches the best 3.
2. **Retrieval**:
   - **Library:** Qdrant passages and wiki pages, checked against Postgres; only published practices are used.
   - **Engagement:** the same Qdrant search and Postgres check, under the engagement's id. Only processed, not-deleted uploads are used.
   - Wiki pages are scored against their source passages, and those below 0.6 are dropped.
   - The rest are reranked (by a cross-encoder when one is configured), and the top 10 are kept.
   - A weak best match means "insufficient evidence".
3. **Answer**:
   - The sources, plus the passages behind each wiki page, are deduplicated and capped at about 3,800 tokens.
   - The model must answer from the sources only and cite `[S#]`.
   - Each attempt has a 90-second limit (the model call itself is stopped at that limit), and timeouts and API errors are retried twice.
   - Invalid citations are removed, and answers that cite too little are rejected.

## Production notes

- **Concurrency:**
  - Requests share no state; each has its own database session.
  - Answer calls run on one bounded pool per process (`QUERY_MAX_CONCURRENT_ANSWERS`, default 8). A call that overruns is stopped at its limit.
  - Documents are processed by Celery workers, not the API, so uploads return at once and any API server answers from the same Postgres + Qdrant.
  - Workers: on Linux run several with `--pool=prefork --concurrency=N`. `./scripts/run_agent.sh` and `make` start one `--pool=solo` worker, which is enough for development.
  - Scanned PDFs need OCR in the worker (`DOCLING_OCR_ENABLED=true`, the default).
- **Configuration:**
  - Set `ADVISE_WORKBENCH_ENV=production`.
  - Use an API model provider (`LLM_PROVIDER=anthropic` or `openai_compatible`) rather than `claude_cli` for many concurrent users, because the CLI starts one process per call.
- **Settings:** `query_*` in `src/core/config.py` (environment variables `QUERY_*`; see `.env.example`).
