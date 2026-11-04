# Test plan: Sheldon answers from engagement documents

This plan tests the whole path, end to end:

1. Engagement upload.
2. Ingestion pipeline (SeaweedFS → Celery/Docling → Postgres + Qdrant).
3. Sheldon's router agent sends the question to the rag_agent.
4. The query pipeline produces a cited answer.

It covers every file type, Sheldon's routing, follow-ups, "insufficient evidence", replacing and deleting a document,
documents still being processed, and access control. Each question has the answer you should see, so you can check
the results without knowing the documents.

API reference: [library-query-api.md](../04-development/library-query-api.md).

## 1. The test files

All under `data/examples/northwind-p2p/`. They describe a fictional client, Northwind Manufacturing, and its
procure-to-pay process.

| # | File | Type | Tests |
|---|---|---|---|
| 1 | `source-documents/01_procure_to_pay_current_state.md` | Markdown | Process, policy, risks |
| 2 | `source-documents/02_discovery_workshop_notes.txt` | Plain text | Workshop facts and quotes |
| 3 | `source-documents/03_roles_and_glossary.md` | Markdown | Roles, RACI, escalation |
| 4 | `source-documents/04_systems_and_volumes.csv` | CSV | Table data |
| 5 | `source-documents/05_baseline_metrics_memo.md` | Markdown | Metrics, current vs target |
| 6 | `source-documents/06_ap_match_exception_sop_draft.docx` | Word | Docling: Word with tables and lists |
| 7 | `source-documents/07_p2p_raci_and_kpi_workbook.xlsx` | Excel | Docling: three sheets |
| 8 | `rag-test/upload-first/08_vendor_master_change_policy.pdf` | PDF (2 pages) | Docling: PDF, page numbers |
| 9 | `rag-test/upload-second/08_vendor_master_change_policy.pdf` | PDF, same name, changed content | Replacing a document |

Files 6–9 are generated. If they are missing, run these from the repo root:

```powershell
.\.venv\Scripts\python.exe data/examples/northwind-p2p/rag-test/generate_rag_test_files.py
cd data/examples/northwind-p2p; ..\..\..\.venv\Scripts\python.exe generate_binary_artifacts.py; cd ..\..\..
```

## 2. Prepare (once)

1. **Check `.env`.** It must contain:
   - `DATABASE_URL`, `CELERY_BROKER_URL`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`
   - `QDRANT_URL`, `EMBEDDING_BASE_URL`, `JWT_SECRET` (16+ characters)
   - An LLM provider (`LLM_PROVIDER`)
2. **Check the shared services:**
   ```powershell
   .\.venv\Scripts\python.exe scripts/check_shared_services.py --env .env --only postgres,rabbitmq,s3,qdrant,embeddings
   ```
   Every line must say PASS.
3. **Run the automated tests** (in-memory, no services needed):
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/test_query_api.py tests/unit/test_query_pipeline.py tests/unit/test_document_pipeline.py -q
   ```
4. **Start the app** in three PowerShell windows, from the repo root:
   - **API:** `.\.venv\Scripts\python.exe -m uvicorn src.app.main:app --port 8000`
   - **Worker:** `.\.venv\Scripts\python.exe -m celery -A src.workers.celery_app worker --pool=solo --loglevel=INFO`
   - **Frontend:** `cd frontend; npm run dev`
5. **Watch both terminals during the tests.** `LOG_LEVEL=INFO` is the default. Every line carries the job, the project
   and the file name.

   | Terminal | Tag | What it shows |
   |---|---|---|
   | API | `[UPLOAD]` | File received, saved to the workspace, ingestion job queued (or why not) |
   | API | `[PIPELINE] … queued` | File stored in SeaweedFS and handed to the worker |
   | Worker | `[S3]` | Worker found the file in SeaweedFS; `document_files` row in Postgres |
   | Worker | `[PARSE]` | Docling result (pages, tables, characters); `parsed_documents` in Postgres |
   | Worker | `[CHUNK]` | Passages written to Postgres `chunk_archive` |
   | Worker | `[EMBED]` | Embedding model used, and points written to the Qdrant collection with `project_id` = the engagement |
   | Worker | `[PIPELINE] … COMPLETED` | Searchable now (`FAILED at stage …` / `retrying` on errors) |
   | API | `[SHELDON] … agent=…` | Which agent the router chose: `rag`, `supervisor` or `conversation` |
   | API | `[RAG_AGENT] called` / `result` | rag_agent started, and what it got back (status, citations engagement / library) |
   | API | `[QUERY] start`, `1/3`, `2/3`, `#1…#5`, `3/3`, `done` | Each stage of the query pipeline: understanding, retrieval (hits, verified, reranker, top sources), answer (model, context, attempts), citations |

## 3. Postman setup

1. **Environment.** Create one with these variables:
   - `base` = `http://localhost:8000`
   - `token` (empty)
   - `pid` (empty)
   - `job` (empty)
2. **Collection header.** On the collection, set `Authorization: Bearer {{token}}`.
3. **Log in:** `POST {{base}}/api/auth/login`, Body → raw JSON `{"email": "<your email>", "password": "<password>"}`.
   Put `access_token` from the response into `token`.
4. **Create a test engagement:** `POST {{base}}/api/projects`, Body `{"name": "RAG test - Northwind"}`. Put `id` into `pid`.

## 4. Upload and processing

**Step 4.1. Upload files 1–8**, one request per file:
- `POST {{base}}/api/documents/upload`, Body → form-data:
  - `project_id` (Text) = `{{pid}}`
  - `file` (File) = the file
- Expected: `200`, and `ingestion.job_id` with `ingestion.status` = `pending` (or a later stage).
- Copy the `job_id` of file 8 (the PDF) into `job`.

**Step 4.2. Follow one document:** `GET {{base}}/api/documents/status/{{job}}?project_id={{pid}}`. Send it every few seconds:
- `ingestion.stage` moves through `uploading` → `parsing` → `chunking` → `embedding`.
- Then `status: "completed"`, `searchable: true` and `progress_percent: 100`.
- The first PDF takes longer, because Docling loads its OCR models once.

**Step 4.3. List all documents:** `GET {{base}}/api/documents/list?project_id={{pid}}`.
- Expected: 8 entries in `documents`, each with `ingestion.status: "completed"` and `chunk_count` > 0.

**If a file shows `failed`:**
- Read `ingestion.error`. A failure at stage `queue` means RabbitMQ or S3 is unreachable.
- Fix the cause, then `POST {{base}}/api/documents/reindex?project_id={{pid}}`.

## 5. Questions to Sheldon

**How to send a question:**
- `POST {{base}}/api/projects/{{pid}}/conversation/messages`, Body `{"content": "<question>"}`.
- Read the **last** item of `messages`:
  - `content` is Sheldon's reply.
  - `metadata.kind` must be `rag_answer`.
  - `metadata.citations[].filename` must name the expected file.
- Each answer cites `[S1]`, `[S2]`… and ends with `Sources:`, listing each source as `(engagement document)`. If the
  Leading Practice Library has released practices on the topic, it may also cite them as `(Leading Practice Library)`.

### 5.1 Facts from one document

| # | Question | Expected answer | Cited file |
|---|---|---|---|
| A1 | How long do vendor master changes take today? | They need an IT ticket, about **9 days** | 02 |
| A2 | What budget did the board approve for the finance transformation? | **$4.2M** over **18 months** | 02 or 05 |
| A3 | When are non-PO invoices allowed? | Only for **utilities, freight and pre-approved petty-cash vendors** (policy FIN-AP-014) | 01 |
| A4 | Who is accountable for running payments? | The **Controller** | 03 or 07 |
| A5 | Which ERP system is planned for decommissioning, and when? | **SAP ECC 6.0** (NWM-EU), **Q4 2026** | 04 |
| A6 | Within how many hours must an AP clerk triage a match exception? | **4 business hours** | 06 (Word) |
| A7 | What is the current and target cost per invoice? | **$4.85** now, target **$3.20** | 05 or 07 (Excel) |
| A8 | Which invoice in the exception sample is a duplicate? | **INV-88461**, Acme Industrial Supply, $12,450 | 07 (Excel) |
| A9 | How quickly must the MDG steward approve a bank detail change? | Within **4 business days** | 08 (PDF) |
| A10 | How many call-backs does a bank detail change need? | **One** independent call-back, to the number on file | 08 (PDF) |

### 5.2 Several documents, comparisons, lists

| # | Question | Expected answer |
|---|---|---|
| B1 | Compare the invoice-to-payment time for the US and the EU, current and target. | US **14.2 → 10.0** days; EU **23.1 → 14.0** days |
| B2 | What are the main causes of match exceptions? | **Price variance, quantity mismatch, missing goods receipt, wrong tax code** |
| B3 | What escalation applies when a match exception stays unresolved? | After **3 days**: AP supervisor → Buyer → Category manager (03); the SOP (06) adds AP manager + Controller after **5 days** |

### 5.3 Follow-up questions (send them in this order)

| # | Question | Expected answer |
|---|---|---|
| C1 | What is Kofax used for? | Invoice capture and **OCR**, at the US AP hub |
| C2 | Who owns it? | **Priya Sharma** (Sheldon understands "it" = Kofax) |
| C3 | And what is its first-pass accuracy? | **87%**, target **95%** |

### 5.4 Not in the documents: Sheldon must not guess

| # | Question | Expected answer |
|---|---|---|
| E1 | What is Northwind's cafeteria budget? | "I couldn't find anything in this engagement's documents or the Leading Practice Library that answers that, so I won't guess." `metadata.status` = `insufficient_evidence` |
| E2 | Who is Northwind's CEO? | The same: no invented name |

### 5.5 Routing: other agents

| # | Message | Expected |
|---|---|---|
| F1 | Thanks, that was helpful. | A normal chat reply; `metadata.kind` = `conversational_response` (no rag_answer) |
| F2 | Create an executive deck summarising the P2P baseline metrics. | The deliverable flow (supervisor): discovery questions or a plan, not a rag_answer. Stop here; don't confirm a run |

### 5.6 The way the UI asks (background turn)

1. `POST {{base}}/api/projects/{{pid}}/conversation/messages?background=true` with `{"content": "<A1>"}`. You get a `turn_id`.
2. `GET {{base}}/api/projects/{{pid}}/conversation/turns/<turn_id>`, repeated until `status` is `done`.
3. Check that `response.messages[-1]` is the same answer as A1.

## 6. Replace, process and delete

**Step 6.1. Replace the PDF with a new version.**
- Upload `rag-test/upload-second/08_vendor_master_change_policy.pdf` (the **same file name**).
- Wait until its status is `completed`.

| # | Question | Expected answer (new version only) |
|---|---|---|
| D1 | How quickly must the MDG steward approve a bank detail change? | **2 business days** (no longer 4) |
| D2 | How many call-backs does a bank detail change need? | **Two** independent call-backs by different people |
| D3 | How long before a payment run are bank detail changes frozen? | **3 business days** (version 1 said 5) |

**Step 6.2. A document still being processed.**
- Upload `07_p2p_raci_and_kpi_workbook.xlsx` again with a small change. For example, open it, add a row, save it, then upload it.
- **Immediately** ask A1. The reply should end with: *"Still processing, so not searched yet: 07_p2p_raci_and_kpi_workbook.xlsx."*
- If processing finishes before you ask, stop the worker (window 2), upload, ask, then start the worker again.

**Step 6.3. Delete a document.**
- `DELETE {{base}}/api/documents/delete?project_id={{pid}}&filename=08_vendor_master_change_policy.pdf`
- Ask D1 again. The answer must be `insufficient_evidence`; no bank-detail answer remains.

## 7. The query API directly

1. **Ask:** `POST {{base}}/api/query` with:
   ```json
   {"question": "What budget did the board approve?", "engagement_id": "{{pid}}", "include_library": false}
   ```
   Expected: `status: "answered"`, and `citations[0].scope: "engagement"` with the file name.
2. **Open a source:** `GET {{base}}<citations[0].link>`. The `link` already contains `?engagement_id=`. Expected: the full passage text.
3. **Health:** `GET {{base}}/api/query/health`. Expected: `"ready": true`.

## 8. Access control

1. Log in as a second user who is **not** a member of the test engagement, and use that token.
2. `POST {{base}}/api/query` with `{"question": "What budget?", "engagement_id": "{{pid}}"}`. Expected: **403**.
3. `GET {{base}}/api/documents/status/{{job}}?project_id={{pid}}`. Expected: **403**.
4. `GET` a citation link from step 7. Expected: **404**.
5. Any request without a token. Expected: **401**.

## 9. The same in the UI (http://localhost:3000)

1. **Upload:** sign in, open the test engagement, and upload files 1–8 in its documents section.
2. **Watch the status:** each file shows **Processing (stage) %**, refreshing every 3 seconds, then **Ready for questions**.
3. **Ask:** open **Conversation**. Ask A1, then C1 → C2 → C3, then E1, F1 and F2. The replies should match the tables above.
4. **Replace:** upload the second PDF and wait for **Ready**. Ask D1, which should now say 2 business days.
5. **Delete:** delete the PDF in the documents list, then ask D1 again. Sheldon should say it can't find it.
6. **Older documents:** in an engagement with documents uploaded before this change, they show **Not processed - process now**. Click it once, and they become **Ready for questions**.

## 10. Results checklist

| Area | Pass when |
|---|---|
| Upload | Every file reaches `completed`; the worker log shows all four stages |
| File types | A5 (CSV), A6 (Word), A7/A8 (Excel) and A9/A10 (PDF) answer correctly |
| Citations | Each answer cites the expected file, marked "engagement document" |
| Follow-ups | C2 and C3 are answered about Kofax |
| No guessing | E1 and E2 are `insufficient_evidence` |
| Routing | F1 is a chat reply; F2 goes to the deliverable flow |
| Replace | D1–D3 give the version 2 values only |
| Processing | The "Still processing" line appears |
| Delete | D1 is `insufficient_evidence` after the delete |
| Access | 403 / 404 / 401 as listed |

## 11. If something goes wrong

| Symptom | Cause and fix |
|---|---|
| `ingestion.status` stays `pending` | No worker is running (window 2), or another worker on the shared broker took the job |
| `failed` at stage `queue` | RabbitMQ or S3 unreachable: check `CELERY_BROKER_URL` and the S3 settings, then `/reindex` |
| `failed` at `parsing` / `chunking` with "no text" | A scanned PDF with OCR off: set `DOCLING_OCR_ENABLED=true` and restart the worker |
| Sheldon replies with chat instead of an answer | Phrase the question about the documents ("What does … say about …?") |
| `503 Search is unavailable` | Qdrant or the embedding service is down: rerun the service check |
| `llm_unavailable` | The model provider failed: check `LLM_PROVIDER` and its credentials |
