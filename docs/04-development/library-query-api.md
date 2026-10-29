# Library Q&A API (frontend integration)

Ask the Leading Practice Library a question and get an answer that cites its sources. Answers are kept in conversations, so follow-up questions work, and users can rate answers. The live schema is at `/docs` (Swagger) and `/openapi.json`; look for the `query` tag.

- **Auth**: every call needs `Authorization: Bearer <access token>`, the same as the rest of the workbench (`apiFetch` in `frontend/lib/apiClient.ts`). Without it you get `401`.
- **Who sees what**: any signed-in user can ask. Only the published version of Approved practices is ever searched or shown. Candidates still in review never appear. Each conversation is visible only to the user who started it. The metrics endpoint is for administrators only.
- **Code**: `src/app/api/query.py` (endpoints and response models), `src/query/pipeline.py` (the pipeline), `src/query/conversations.py` (conversations), `src/query/events.py` (question log and metrics).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/query/health` | Whether questions can be answered right now, plus the form limits |
| `POST` | `/api/query` | Ask a question (starts a conversation, or continues one with `conversation_id`) |
| `GET` | `/api/query/conversations?limit=50&offset=0` | The user's conversations, most recently updated first |
| `GET` | `/api/query/conversations/{id}` | One conversation with all its turns |
| `PATCH` | `/api/query/conversations/{id}` | Rename: `{"title": "..."}` (1–80 characters) |
| `DELETE` | `/api/query/conversations/{id}` | Delete |
| `PUT` | `/api/query/conversations/{id}/turns/{turn_id}/feedback` | Rate an answer: `{"rating": "up"\|"down", "comment": "..."}` |
| `GET` | `/api/query/sources/{chunk\|wiki}/{id}` | A cited source in full (this is `citations[].link`) |
| `GET` | `/api/admin/library/query/metrics?days=7&top=20` | Admin: outcomes, latency, model errors, feedback, unanswered questions |

## Health (call when the Q&A panel opens)

```json
{ "ready": true, "search_available": true, "model_available": true,
  "embedding_model": "BAAI/bge-small-en-v1.5", "reranker": "keyword",
  "limits": { "question_max_chars": 2000, "top_k_max": 12, "top_k_default": 10, "max_turns_per_conversation": 100 } }
```

When `ready` is false, disable the ask box and say why: "Search is unavailable" if `search_available` is false, otherwise "Answers are unavailable". Use `limits.question_max_chars` for the input's `maxLength`.

## Ask

```http
POST /api/query
{ "question": "How are new vendors screened?" }
```

For a follow-up, send back the `conversation_id` from the previous response. The server reads the earlier turns itself, so don't send them:

```json
{ "question": "and who approves it?", "conversation_id": "conv_3f2a..." }
```

Optional fields: `save: false` answers without storing a conversation (for a one-off search box), and `top_k` (1–12, default 10) sets how many sources go to the model.

Response (shortened):

```json
{
  "conversation_id": "conv_3f2a...", "turn_id": "turn_91bc...", "created_at": "2026-10-27T10:42:03",
  "status": "answered", "reason": null,
  "question": "How are new vendors screened?",
  "standalone_question": "How are new vendors screened?",
  "answer": "New vendors are screened against sanctions lists before onboarding [S1]. Finance approves bank details [S2].",
  "answer_markdown": "New vendors are screened ... onboarding [S1](chunk_ab12). Finance approves bank details [S2](wiki_77fe).",
  "citations": [
    { "ref": "S1", "type": "chunk", "id": "chunk_ab12", "title": "Vendor onboarding, page 3",
      "filename": "vendor-onboarding.docx", "page_number": 3, "chunk_number": 7,
      "practice_id": "lp-004", "practice_title": "Vendor onboarding", "supports": null,
      "score": 0.81, "verification": 1.0, "snippet": "All new vendors are screened ...",
      "link": "/api/query/sources/chunk/chunk_ab12", "markdown": "[Vendor onboarding, page 3](chunk_ab12)" }
  ],
  "sources": [ { "type": "wiki", "id": "wiki_77fe", "title": "Vendor approval", "score": 0.74, "rank_score": 0.71,
                 "verification": 0.83, "verification_details": { "method": "term_support", "supported_terms": 10,
                 "total_terms": 12, "unsupported_terms": ["..."], "evidence_ids": ["chunk_cd34"], "passed": true },
                 "snippet": "...", "link": "/api/query/sources/wiki/wiki_77fe" } ],
  "coverage": { "claims": 2, "cited": 2, "ratio": 1.0, "uncited": [], "fully_cited": true, "invalid_refs": [] },
  "understanding": { "intent": "procedure", "question_type": "how", "is_follow_up": false, "context_turns": 0,
                     "entities": [], "keywords": ["new", "vendors", "screened"], "language": "en" },
  "variants": [ { "text": "How are new vendors screened?", "kind": "original", "score": 1.0, "embedded": true },
                { "text": "new vendors screened", "kind": "keywords", "score": 0.91, "embedded": true } ],
  "queries": ["How are new vendors screened?", "new vendors screened"],
  "retrieval": { "candidates": 41, "verified": 23, "dropped_low_verification": 1, "top_score": 0.81, "reranker": "keyword", "final": 10 },
  "answer_metadata": { "provider": "claude_cli", "model": "claude-sonnet-...", "attempts": 1, "errors": [], "latency_ms": 2900,
                       "answer_chars": 112, "context": { "sources": 12, "chars": 14100, "tokens_est": 3525, "max_tokens": 3800 } },
  "model_calls": 1, "timings_ms": { "understanding": 40, "retrieval": 120, "answer": 2900, "total": 3070 },
  "feedback": null
}
```

A call usually takes a few seconds because of the model. Show a loading state, and don't send the same question twice while one is still pending.

## Rendering an answer

1. **Answer text**: render `answer` and turn each `[S1]`, `[S2]` … into a clickable chip for `citations[]` with the matching `ref`. If you just render markdown, `answer_markdown` already has each marker linked to the source id. References to sources the model was never given have already been removed.
2. **Citation chip or popover**: show `title`, plus `practice_title` when it is set, and `snippet`. To show the full source, call `GET` on `link`.
3. **Practice link**: when `practice_id` is set, link to `/library?practice={practice_id}`.
4. **Sources list** (optional): for an answered question, `sources` is everything the model was given. For other statuses, it is what was retrieved. A `wiki` source's `verification_details` explains its score; you could show it as "Supported by 3 source passages (83%)".
5. **Uncited claims** (optional): when `coverage.fully_cited` is false, you can show a "some statements are not cited" hint. `coverage.uncited` lists those sentences.
6. **Feedback**: thumbs up or down under each saved answer (`turn_id` set) calls `PUT …/turns/{turn_id}/feedback`. The response is the updated turn. A turn's `feedback` field shows the saved rating when the conversation is reloaded.
7. **Debug details** (optional, for example an "i" icon): `understanding`, `variants`, `retrieval`, `answer_metadata` and `timings_ms`.

## Status and reason

| `status` | `reason` | What happened | Suggested UI |
|---|---|---|---|
| `answered` | `null` | Answer grounded in the sources, with citations | Render it |
| `insufficient_evidence` | `no_results` | Nothing in the published library matched | "No published practice covers this. Try rephrasing." |
| `insufficient_evidence` | `low_confidence` | Only weak matches | Same message |
| `insufficient_evidence` | `low_verification` | Matches existed, but none was well supported by its source documents | Same message |
| `insufficient_evidence` | `model_declined` | The sources didn't answer the question | Same message; `sources` may still be worth showing |
| `insufficient_evidence` | `uncited_answer` | The draft answer cited less than half of its statements, so it was rejected | Same message |
| `llm_unavailable` | `llm_failed` | The model failed after its retries (timeouts and API errors are tried 3 times; configuration errors once) | Show `answer` ("Unable to process question now…") and the `sources`; offer a retry (ask the same question again) |

For every status other than `answered`, `answer` holds a ready-made message you can display as is. Every status is saved as a turn of the conversation, so it can be rated and reloaded like any other.

## Errors

| HTTP | When |
|---|---|
| `401` | Missing or expired token |
| `403` | The metrics endpoint, called by someone who isn't an administrator |
| `404` | Conversation, turn or source not found, or it belongs to another user; a source that isn't part of a published practice |
| `409` | The conversation has 100 turns; start a new one |
| `422` | Invalid body (for example, a question shorter than 2 or longer than 2,000 characters, or a rating other than `up`/`down`) |
| `503` | Search is down (embedding service or Qdrant). Retry later; `/api/query/health` shows when it is back |

## Conversations

`GET /api/query/conversations` returns `{ "items": [ { "id", "title", "created_at", "updated_at", "turn_count", "last_question", "last_status" } ], "total" }`. The title starts as the first question (up to 80 characters) and can be renamed. `GET /api/query/conversations/{id}` adds `turns`. Each turn has the same shape as the ask response, without `conversation_id` and `turn_id`; its own id is `id`.

## Source detail

`GET /api/query/sources/chunk/{id}` returns the full passage: `text`, `filename`, `page_number`, `chunk_number`, `practice_id`, `practice_title` and `verification` (always 1.0, because a passage is the source text itself).

`GET /api/query/sources/wiki/{id}` returns the wiki page's `text`, `verification_details`, and `evidence`: the source passages it was checked against, each with its own `link`.

## Admin metrics (Library admin console)

`GET /api/admin/library/query/metrics?days=7` returns data for a Q&A panel in the admin console. `days` is capped by the retention period, 90 days by default.

```json
{ "window_days": 7, "since": "...", "total": 214, "answered": 171, "answer_rate": 0.799,
  "by_status": { "answered": 171, "insufficient_evidence": 39, "llm_unavailable": 4 },
  "by_reason": { "no_results": 22, "model_declined": 11, "low_confidence": 6, "llm_failed": 4 },
  "by_intent": { "procedure": 80, "definition": 41, "...": 0 },
  "latency_ms": { "avg": 3400, "p50": 2900, "p95": 7800 },
  "llm": { "calls": 230, "failed_requests": 4, "errors_by_kind": { "timeout": 6, "api_error": 3 } },
  "feedback": { "up": 52, "down": 7, "recent_comments": [ { "rating": "down", "comment": "...", "at": "..." } ] },
  "unanswered_questions": [ { "question": "What is the vendor exit process?", "count": 5, "reason": "no_results", "last_asked_at": "..." } ],
  "daily": [ { "date": "2026-10-21", "total": 30, "answered": 24 } ] }
```

`unanswered_questions` lists the content gaps: questions users ask that no published practice answers yet, most frequent first.

## How the backend answers (for reference)

1. **Understanding**: works out the intent, question type, entities, keywords and language, and loads the conversation's earlier turns. A follow-up is rewritten into a standalone question. Variants are added: focused (entities and keywords), keywords, and an English translation for a non-English question; with `QUERY_LLM_VARIANTS=always`, also a model-written rewrite and paraphrase. Each variant is scored by similarity to the question, variants that drift off-topic are dropped, and the best 3 are searched.
2. **Retrieval**: Qdrant search over passages and wiki pages (50 hits per variant). Each hit is checked against Postgres: it must still exist and be published. Every wiki page in the top 20 is scored against its source passages, and pages scoring below 0.6 are dropped. The rest are reranked (a cross-encoder when one is configured), and the top 10 are kept. If the best match is weak, the answer is "insufficient evidence".
3. **Answer**: the sources go to the model together with the passages behind each wiki page, deduplicated and capped at about 3,800 tokens. The model must answer from the sources only and cite `[S#]`. Each attempt has a 90-second limit, and timeouts and API errors are retried twice. Citations are then checked, invalid ones removed, and answers that cite too little are rejected.

Settings are under `query_*` in `src/core/config.py` (environment variables `QUERY_*`).
