"""Query pipeline: understanding, retrieval with verification + reranking, cited answers, no-result and LLM failure."""

import hashlib
import uuid
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from src.core.db.models import (
    ChunkArchive,
    DocumentChunkLink,
    DocumentFile,
    DocumentJob,
    ParsedDocument,
    Project,
    User,
    WikiPageFinal,
)
from src.core.db.session import session_scope
from src.core.parsing.docling_parser import DoclingParserService
from src.core.vector_db.qdrant_client import QdrantVectorStore
from src.memory.knowledge import practice_ingest as ingest
from src.query import pipeline as qp

TEXTS = {
    1: "The AP clerk posts supplier invoices after a three-way match of purchase order, receipt and invoice.",
    2: "Duplicate invoice payments are a key risk; the duplicate check runs before each payment run.",
    3: "The cafeteria menu changes every Monday and includes vegetarian options.",
}


def vec(text: str) -> list[float]:
    """Bag-of-words vector over a tiny vocabulary: overlapping wording -> high cosine."""
    vocab = ["invoice", "invoices", "clerk", "match", "duplicate", "payment", "risk", "menu", "cafeteria", "post", "posts", "ap"]
    words = text.lower().replace(",", " ").replace(".", " ").replace("?", " ").split()
    v = [float(sum(w == t for w in words)) for t in vocab]
    return v + [0.0 if any(v) else 1.0]  # unknown wording points in its own direction


class Embedder:
    model_name = "bow"

    def embed_batch(self, texts, batch_size=32):
        return [vec(t) for t in texts]


@pytest.fixture
def project(monkeypatch):
    stores = {}

    def get_store(collection_name=None, url=None):
        name = collection_name or "document_chunks"
        if name not in stores:
            stores[name] = QdrantVectorStore("http://unused", None, f"q_{name}")
            stores[name].client = QdrantClient(location=":memory:")
        return stores[name]

    monkeypatch.setattr(qp, "get_qdrant_client", get_store)
    monkeypatch.setattr(qp, "get_embedding_service", lambda: Embedder())
    monkeypatch.setattr(qp.settings, "query_min_score", 0.3)
    monkeypatch.setattr(qp.settings, "query_llm_retry_backoff_sec", 0.0)
    calls = []

    def fake_llm(*, system, user, **_):
        calls.append(system)
        if "standalone" in system:
            return "What is the duplicate invoice payment risk?"
        return "Duplicate payments are a risk, prevented by a duplicate check [S1]."

    monkeypatch.setattr(qp, "claude_generate", fake_llm)

    with session_scope() as db:
        uid, pid, job = f"u_{uuid.uuid4().hex[:6]}", f"p_{uuid.uuid4().hex[:6]}", str(uuid.uuid4())
        db.add(User(id=uid, email=f"{uid}@example.com", hashed_password="x"))
        db.flush()
        db.add(Project(id=pid, name="q", created_by=uid))
        db.flush()
        db.add(DocumentJob(id=f"doc_{job[:8]}", job_id=job, project_id=pid, user_id=uid, filename="p2p.pdf", status="completed"))
        db.flush()
        doc = DocumentFile(id=f"docfile_{job[:8]}", project_id=pid, job_id=job, filename="p2p.pdf")
        db.add(doc)
        db.flush()
        doc_id = doc.id
        db.add(ParsedDocument(id=f"parsed_{doc.id}", document_file_id=doc.id, project_id=pid))
        db.flush()
        records = []
        for n, text in TEXTS.items():
            cid = f"{doc.id}_c{n:05d}"
            db.add(ChunkArchive(id=cid, document_file_id=doc.id, parsed_document_id=f"parsed_{doc.id}", project_id=pid,
                                chunk_number=n, text=text, page_number=n, source_type="main_text"))
            db.flush()
            db.add(DocumentChunkLink(document_file_id=doc.id, chunk_number=n, chunk_id=cid, page_number=n))
            records.append({"chunk_id": cid, "embedding": vec(text),
                            "metadata": {"chunk_id": cid, "project_id": pid, "document_id": doc.id, "text": text}})
        get_store().store_embeddings_batch(records)
        ghost = "ghost_chunk"  # in Qdrant but no longer in Postgres -> must be dropped by verification
        get_store().store_embeddings_batch([{"chunk_id": ghost, "embedding": vec("duplicate payment risk"),
                                             "metadata": {"chunk_id": ghost, "project_id": pid, "text": "stale"}}])
        db.add(WikiPageFinal(id=f"wiki_{pid}", project_id=pid, entity_name="Duplicate payment", entity_type="risk",
                             content="Duplicate payment risk is controlled by the duplicate check.", is_published=True,
                             merge_info={"source_documents": [doc.id]}))
        # Written from the same document, but says things the document does not: fails verification.
        db.add(WikiPageFinal(id=f"wiki_bad_{pid}", project_id=pid, entity_name="Payment fraud", entity_type="risk",
                             content="Payment fraud is investigated quarterly by external forensic auditors in Zurich.",
                             is_published=True, merge_info={"source_documents": [doc.id]}))
        get_store("wiki_pages").store_embeddings_batch([
            {"chunk_id": f"wiki_{pid}", "embedding": vec("duplicate payment risk"),
             "metadata": {"wiki_id": f"wiki_{pid}", "project_id": pid}},
            {"chunk_id": f"wiki_bad_{pid}", "embedding": vec("payment risk"),
             "metadata": {"wiki_id": f"wiki_bad_{pid}", "project_id": pid}},
        ])
    return {"pid": pid, "calls": calls, "doc": doc_id}


def ask(project, question, history=None):
    with session_scope() as db:
        return qp.answer_question(db, project["pid"], question, history or [])


def test_answer_cites_verified_sources(project):
    r = ask(project, "What is the duplicate payment risk?")
    assert r.status == "answered" and "[S1]" in r.answer
    assert r.citations[0]["ref"] == "S1"
    ids = {s["id"] for s in r.sources}
    assert "ghost_chunk" not in ids  # verification removed content missing from Postgres
    assert r.model_calls == 1  # no rewrite without history


def test_no_matching_content_is_insufficient_without_model_call(project):
    r = ask(project, "quarterly marketing budget forecast")
    assert r.status == "insufficient_evidence" and "Insufficient evidence" in r.answer
    assert r.model_calls == 0 and project["calls"] == []


def test_follow_up_is_rewritten_once(project):
    history = [{"role": "user", "content": "Tell me about invoice risks"}, {"role": "assistant", "content": "Duplicates [S1]"}]
    r = ask(project, "how is it prevented?", history)
    assert r.standalone_question == "What is the duplicate invoice payment risk?"
    assert r.model_calls == 2 and r.status == "answered"


def test_answer_without_citations_counts_as_insufficient(project, monkeypatch):
    monkeypatch.setattr(qp, "claude_generate", lambda **_: "Some unsupported claim.")
    assert ask(project, "What is the duplicate payment risk?").status == "insufficient_evidence"


def test_llm_failure_returns_sources(project, monkeypatch):
    def boom(**_):
        raise RuntimeError("cli down")

    monkeypatch.setattr(qp, "claude_generate", boom)
    r = ask(project, "What is the duplicate payment risk?")
    assert r.status == "llm_unavailable" and r.sources


def test_context_budget_and_rerank_dedup():
    a = qp.Source("chunk", "a", 0.9, text="duplicate invoice check " * 50, filename="f.pdf")
    b = qp.Source("chunk", "b", 0.8, text="duplicate invoice check " * 50, filename="f.pdf")  # near duplicate
    c = qp.Source("wiki", "c", 0.7, text="cafeteria", title="Menu")
    ranked = qp.rerank("duplicate invoice", [a, b, c], 5)
    assert [s.key for s in ranked] == ["a", "c"]
    context, used = qp.build_context(ranked, 400)
    assert len(context) <= 420 and used[0].key == "a" and context.startswith("[S1] f.pdf")


def test_format_answer_lists_cited_sources(project):
    r = ask(project, "What is the duplicate payment risk?")
    text = qp.format_answer(r)
    assert text.startswith(r.answer) and "Sources:\n[S1] " in text
    empty = ask(project, "quarterly marketing budget forecast")
    assert qp.format_answer(empty) == empty.answer


def test_expand_and_follow_up_detection():
    assert qp.expand("What are the key risks in procurement?")[1] == "key risks procurement"
    assert not qp.needs_rewrite("what about it?", [])
    assert qp.needs_rewrite("what about it?", [{"role": "user", "content": "x"}])


def test_understanding_types_entities_topics_and_language():
    assert qp.question_type("Who approves supplier invoices?") == "who"
    assert qp.question_type("In which region is the AP team?") == "which"
    assert qp.question_type("Explain the three-way match") == "what"
    assert qp.question_type("Is the duplicate check automated?") == "yes_no"
    history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
    u = qp.understand('How does Northwind Traders run the "three-way match" in SAP Ariba?', history)
    assert u["question_type"] == "how" and u["intent"] == "procedure" and u["language"] == "en"
    assert u["context_turns"] == 1 and not u["is_follow_up"]
    assert {"three-way match", "Northwind Traders", "SAP Ariba"} <= set(u["entities"]) and "How" not in u["entities"]
    assert "run" in u["keywords"] and "northwind" not in u["keywords"]
    assert qp.language_of("重复付款的风险是什么？") == "other"


@pytest.mark.parametrize("question, expected", [
    ("What is a three-way match?", "definition"),
    ("How do we onboard a new vendor?", "procedure"),
    ("Compare centralised and decentralised AP", "comparison"),
    ("Should we automate invoice matching?", "recommendation"),
    ("Why is segregation of duties needed?", "reason"),
    ("What are the types of procurement fraud?", "list"),
    ("Summarise the vendor policy", "summary"),
    ("Is the duplicate check automated?", "verification"),
    ("Who approves supplier invoices?", "fact"),
    ("Invoice tolerances", "other"),
])
def test_intent(question, expected):
    assert qp.intent(question) == expected


def test_variants_are_ranked_scored_and_drifting_ones_are_not_searched(monkeypatch):
    monkeypatch.setattr(qp.settings, "query_max_variants", 3)
    understanding = qp.understand("how is it prevented at Northwind?", [{"role": "user", "content": "x"}])
    v = qp.build_variants("how is it prevented at Northwind?", "How is duplicate invoice payment prevented?",
                          [{"text": "Duplicate invoice payment prevention controls", "kind": "clarified"}], understanding)
    assert [x["kind"] for x in v] == ["standalone", "original", "clarified", "focused", "keywords"]
    vectors = [[1.0, 0.0], [0.1, 1.0], [0.9, 0.1], [0.8, 0.3], [0.95, 0.05]]
    chosen = qp.select_variants(v, vectors)
    assert v[0]["score"] == 1.0 and v[1]["score"] < 0.5  # the raw follow-up drifted from the standalone question
    assert [x["embedded"] for x in v] == [True, False, True, True, False] and len(chosen) == 3


def test_variants_are_returned_and_non_english_questions_get_a_translation(project, monkeypatch):
    monkeypatch.setattr(qp, "model_variants", lambda q, lang, paraphrase: [
        {"text": "What is the duplicate payment risk?", "kind": "translated"}])
    r = ask(project, "重复付款的风险是什么？")
    assert r.understanding["language"] == "other"
    assert [v["kind"] for v in r.variants][:2] == ["original", "translated"]
    assert r.variants[1]["embedded"]  # kept although an English-only model sees little similarity
    assert r.queries == [v["text"] for v in r.variants if v["embedded"]]
    assert r.status == "answered" and r.model_calls == 2  # variant + answer


def test_always_mode_asks_for_a_rewrite_and_a_paraphrase(monkeypatch):
    prompts = []

    def fake(*, system, user, **_):
        prompts.append(system)
        return "1. What is the duplicate invoice payment risk?\n2. How big is the danger of paying an invoice twice?"

    monkeypatch.setattr(qp, "claude_generate", fake)
    out = qp.model_variants("duplicate payment risk?", "en", paraphrase=True)
    assert [v["kind"] for v in out] == ["clarified", "paraphrase"] and out[0]["text"].startswith("What is")
    assert "Line 2" in prompts[0]


def test_wiki_pages_are_verified_against_their_source_chunks(project):
    r = ask(project, "What is the duplicate payment risk?")
    wiki = {s["id"]: s for s in r.sources if s["type"] == "wiki"}
    assert f"wiki_{project['pid']}" in wiki and wiki[f"wiki_{project['pid']}"]["verification"] >= 0.6
    assert f"wiki_bad_{project['pid']}" not in wiki  # unsupported by its source document
    assert r.retrieval["dropped_low_verification"] >= 1 and r.retrieval["reranker"] == "keyword"
    assert all(s["verification"] == 1.0 for s in r.sources if s["type"] == "chunk")
    with session_scope() as db:
        detail = qp.source_detail(db, project["pid"], "wiki", f"wiki_{project['pid']}")
    assert detail["evidence"] and detail["evidence"][0]["id"].startswith(project["doc"])


def test_only_unverified_content_is_insufficient_with_its_reason(project, monkeypatch):
    monkeypatch.setattr(qp.settings, "query_min_verification", 1.01)  # nothing can pass
    r = ask(project, "What is the duplicate payment risk?")
    assert r.status == "insufficient_evidence" and r.reason == "low_verification" and r.model_calls == 0


def test_cross_encoder_orders_results_when_configured(monkeypatch):
    class Fake:
        def predict(self, pairs):
            return [0.1 if "cafeteria" not in text else 0.9 for _, text in pairs]

    monkeypatch.setattr(qp, "_get_cross_encoder", lambda: Fake())
    a = qp.Source("chunk", "a", 0.9, text="duplicate invoice check")
    c = qp.Source("wiki", "c", 0.2, text="cafeteria menu", title="Menu")
    assert [s.key for s in qp.rerank("duplicate invoice", [a, c], 5)] == ["c", "a"]


def test_answer_retries_then_succeeds(project, monkeypatch):
    attempts = []

    def flaky(*, system, user, **_):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("overloaded")
        return "Duplicate payments are a risk [S1]."

    monkeypatch.setattr(qp, "claude_generate", flaky)
    r = ask(project, "What is the duplicate payment risk?")
    assert r.status == "answered" and len(attempts) == 3 and r.model_calls == 3


def test_answer_gives_up_after_two_retries(project, monkeypatch):
    attempts = []

    def down(**_):
        attempts.append(1)
        raise RuntimeError("down")

    monkeypatch.setattr(qp, "claude_generate", down)
    r = ask(project, "What is the duplicate payment risk?")
    assert len(attempts) == 3 and r.status == "llm_unavailable" and r.reason == "llm_failed"
    assert r.answer.startswith("Unable to process question now") and r.sources


def test_citations_carry_links_and_uncited_claims_are_reported(project, monkeypatch):
    monkeypatch.setattr(qp, "claude_generate", lambda **_: (
        "Duplicate payments are a key risk. [S1]\nThe duplicate check runs before every payment run [S1][S9]. "
        "Finance also reviews vendor master changes weekly."))
    r = ask(project, "What is the duplicate payment risk?")
    c = r.citations[0]
    assert c["link"] == f"/api/query/sources/{c['type']}/{c['id']}" and c["markdown"] == f"[{c['title']}]({c['id']})"
    assert f"[S1]({c['id']})" in r.answer_markdown
    assert "[S9]" not in r.answer and "payment run [S1]." in r.answer  # citation to no source removed
    assert r.coverage["claims"] == 3 and r.coverage["cited"] == 2 and not r.coverage["fully_cited"]
    assert r.coverage["uncited"] == ["Finance also reviews vendor master changes weekly."]
    assert r.coverage["invalid_refs"] == ["S9"] and r.coverage["ratio"] == 0.667


def test_answers_citing_too_little_are_rejected(project, monkeypatch):
    monkeypatch.setattr(qp, "claude_generate", lambda **_: (
        "Duplicate payments are a key risk [S1]. Finance reviews vendor master changes weekly. "
        "Treasury reconciles bank accounts every day. Auditors sample payments every quarter."))
    r = ask(project, "What is the duplicate payment risk?")
    assert r.status == "insufficient_evidence" and r.reason == "uncited_answer" and r.coverage["ratio"] == 0.25


def test_model_declining_and_empty_search_give_their_reason(project, monkeypatch):
    assert ask(project, "quarterly marketing budget forecast").reason == "no_results"
    monkeypatch.setattr(qp, "claude_generate", lambda **_: "INSUFFICIENT_EVIDENCE")
    assert ask(project, "What is the duplicate payment risk?").reason == "model_declined"


def test_weak_matches_are_low_confidence_without_a_model_call(project, monkeypatch):
    monkeypatch.setattr(qp.settings, "query_min_confidence", 0.99)
    r = ask(project, "Which invoices need a match?")
    assert r.status == "insufficient_evidence" and r.reason == "low_confidence" and r.model_calls == 0
    assert 0 < r.retrieval["top_score"] < 0.99


def test_wiki_evidence_joins_the_context_and_verification_details_are_kept(project, monkeypatch):
    seen = []
    monkeypatch.setattr(qp, "claude_generate", lambda *, system, user, **_: seen.append(user) or "A risk [S1].")
    r = ask(project, "What is the duplicate payment risk?")
    wiki = next(s for s in r.sources if s["type"] == "wiki")
    details = wiki["verification_details"]
    assert details["method"] == "term_support" and details["passed"] and details["evidence_ids"]
    assert details["supported_terms"] <= details["total_terms"] and "controlled" in details["unsupported_terms"]
    keys = [s["id"] for s in r.sources]
    assert len(keys) == len(set(keys))  # evidence already retrieved on its own is not repeated
    assert set(details["evidence_ids"]) <= set(keys) and seen[0].count("Duplicate invoice payments are a key risk") == 1
    meta = r.answer_metadata
    assert meta["attempts"] == 1 and meta["errors"] == [] and meta["context"]["tokens_est"] <= meta["context"]["max_tokens"]
    assert {"provider", "model", "latency_ms"} <= set(meta)


def test_permanent_model_errors_are_not_retried(project, monkeypatch):
    attempts = []

    def unconfigured(**_):
        attempts.append(1)
        raise RuntimeError("Model provider is not configured (see config/model_config.yaml and docs/SETUP.md)")

    monkeypatch.setattr(qp, "claude_generate", unconfigured)
    r = ask(project, "What is the duplicate payment risk?")
    assert len(attempts) == 1 and r.status == "llm_unavailable"
    assert r.answer_metadata["errors"][0]["kind"] == "not_configured"


def test_slow_answers_time_out_and_are_retried(project, monkeypatch):
    import time as _time

    calls = []

    def slow_then_fast(**_):
        calls.append(1)
        if len(calls) == 1:
            _time.sleep(0.5)
        return "Duplicate payments are a risk [S1]."

    monkeypatch.setattr(qp.settings, "query_llm_timeout_sec", 0.1)
    monkeypatch.setattr(qp, "claude_generate", slow_then_fast)
    r = ask(project, "What is the duplicate payment risk?")
    assert r.status == "answered" and r.answer_metadata["attempts"] == 2
    assert r.answer_metadata["errors"][0]["kind"] == "timeout"


@pytest.mark.parametrize("exc, kind", [
    (TimeoutError("Claude CLI timed out after 600s"), "timeout"),
    (RuntimeError("Error code: 429 rate limit"), "rate_limit"),
    (RuntimeError("Claude circuit breaker is open"), "circuit_open"),
    (RuntimeError("Claude CLI error: boom"), "api_error"),
])
def test_error_classification(exc, kind):
    assert qp.classify_error(exc) == kind


def test_outcomes_and_model_errors_are_counted(project, monkeypatch):
    counted = []
    monkeypatch.setattr(qp.metrics, "increment", lambda name, value=1: counted.append(name))
    monkeypatch.setattr(qp, "claude_generate", lambda **_: (_ for _ in ()).throw(RuntimeError("boom")))
    ask(project, "What is the duplicate payment risk?")
    assert counted.count("query_llm_errors_api_error_total") == 3 and counted.count("query_llm_retries_total") == 2
    assert {"query_requests_total", "query_status_llm_unavailable_total", "query_reason_llm_failed_total"} <= set(counted)


def test_hosted_reranker_is_used_when_configured(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.2}]

    sent = {}
    monkeypatch.setattr(qp.settings, "query_reranker_base_url", "http://reranker")
    monkeypatch.setattr(qp.httpx, "post", lambda url, json, headers, timeout: sent.update(url=url, body=json) or Resp())
    a = qp.Source("chunk", "a", 0.9, text="duplicate invoice check")
    c = qp.Source("chunk", "c", 0.2, text="cafeteria menu")
    assert [s.key for s in qp.rerank("duplicate invoice", [a, c], 5)] == ["c", "a"]
    assert sent["url"] == "http://reranker/rerank" and sent["body"]["texts"] == [a.text, c.text]
    assert qp.reranker_name().startswith("cross-encoder")


SAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples" / "northwind-p2p" / "source-documents"


@pytest.mark.skipif(not SAMPLES.exists(), reason="sample documents not present")
@pytest.mark.parametrize("name", sorted(p.name for p in SAMPLES.glob("*")) if SAMPLES.exists() else [])
def test_sample_documents_parse_into_chunks(name):
    """Ingestion with the Northwind sample documents: real Docling (or plain text) -> numbered chunks."""
    data = (SAMPLES / name).read_bytes()
    parsed = DoclingParserService().parse_document(data, name)
    markdown = "\n\n".join(p["text"] for p in parsed["pages"])
    chunks = ingest.chunk_blocks(ingest.blocks_from_markdown(markdown)["blocks"])
    assert chunks and all(c["section"] for c in chunks), f"{name} produced no section passages"
    assert hashlib.sha256(data).hexdigest()
