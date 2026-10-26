"""Query pipeline: understanding, retrieval with verification + reranking, cited answers, no-result and LLM failure."""

import hashlib
import uuid
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from src.core.db.models import ChunkArchive, DocumentFile, DocumentJob, ParsedDocument, Project, User, WikiPageFinal
from src.core.db.session import session_scope
from src.core.parsing.chunking_service import ChunkingService
from src.core.parsing.docling_parser import DoclingParserService
from src.core.vector_db.qdrant_client import QdrantVectorStore
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
        db.add(ParsedDocument(id=f"parsed_{doc.id}", document_file_id=doc.id, project_id=pid))
        db.flush()
        records = []
        for n, text in TEXTS.items():
            cid = f"{doc.id}_c{n:05d}"
            db.add(ChunkArchive(id=cid, document_file_id=doc.id, parsed_document_id=f"parsed_{doc.id}", project_id=pid,
                                chunk_number=n, text=text, page_number=n, source_type="main_text"))
            records.append({"chunk_id": cid, "embedding": vec(text),
                            "metadata": {"chunk_id": cid, "project_id": pid, "document_id": doc.id, "text": text}})
        get_store().store_embeddings_batch(records)
        ghost = "ghost_chunk"  # in Qdrant but no longer in Postgres -> must be dropped by verification
        get_store().store_embeddings_batch([{"chunk_id": ghost, "embedding": vec("duplicate payment risk"),
                                             "metadata": {"chunk_id": ghost, "project_id": pid, "text": "stale"}}])
        db.add(WikiPageFinal(id=f"wiki_{pid}", project_id=pid, entity_name="Duplicate payment", entity_type="risk",
                             content="Duplicate payment risk is controlled by the duplicate check.", is_published=True))
        get_store("wiki_pages").store_embeddings_batch([{"chunk_id": f"wiki_{pid}", "embedding": vec("duplicate payment risk"),
                                                         "metadata": {"wiki_id": f"wiki_{pid}", "project_id": pid}}])
    return {"pid": pid, "calls": calls}


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


def test_router_accepts_question_intent():
    from src.workflows.task_router import conversation_router as cr

    assert "question" in cr._VALID_INTENTS


def test_expand_and_follow_up_detection():
    assert qp.expand("What are the key risks in procurement?")[1] == "key risks procurement"
    assert not qp.needs_rewrite("what about it?", [])
    assert qp.needs_rewrite("what about it?", [{"role": "user", "content": "x"}])


SAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples" / "northwind-p2p" / "source-documents"


@pytest.mark.skipif(not SAMPLES.exists(), reason="sample documents not present")
@pytest.mark.parametrize("name", sorted(p.name for p in SAMPLES.glob("*")) if SAMPLES.exists() else [])
def test_sample_documents_parse_into_chunks(name):
    """Ingestion with the Northwind sample documents: real Docling (or plain text) -> numbered chunks."""
    data = (SAMPLES / name).read_bytes()
    parsed = DoclingParserService().parse_document(data, name)
    groups = ChunkingService(1024, 204).create_chunks_from_parsed(parsed)
    assert groups["total_chunks"] > 0, f"{name} produced no chunks"
    assert hashlib.sha256(data).hexdigest()
