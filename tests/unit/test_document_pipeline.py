"""Ingestion pipeline (Library management): every stage, knowledge building, failures, deletion, and its clients."""

import hashlib
import json
import re
import uuid

import httpx
import pytest
from botocore.stub import Stubber
from qdrant_client import QdrantClient

from src.core.config import settings
from src.core.db.models import (
    ChunkArchive,
    ChunkEmbedding,
    DocumentFile,
    DocumentJob,
    ExtractedFact,
    InAppNotification,
    LpPractice,
    TaskFailure,
    User,
    WikiPageFinal,
    WorkbenchRecord,
)
from src.core.db.session import session_scope
from src.core.embeddings.embedding_service import HttpEmbeddingService
from src.core.storage.seaweedfs_client import SeaweedFSClient
from src.core.vector_db.qdrant_client import QdrantVectorStore, point_id_for
from src.memory.facts import fact_extraction
from src.memory.wiki import wiki_page_generator
from src.memory.wiki.deduplication import Candidate, assign_drafts
from src.workers import document_parsing_tasks, pipeline
from src.workers.pipeline import LIBRARY_SCOPE
from tests.unit import _pipeline_fakes

BODY = "The buyer issues a purchase order after vendor validation. " * 30
MARKDOWN_P1 = f"# Vendor onboarding\n\n## 1 Screening\n\n{BODY}\n\n## 2 Terms\n\nAgree payment terms [1].\n"
MARKDOWN_P2 = "## References\n\n[1] Institute of Supply Management, Risk guide, 2024, https://example.org/risk\n"


class FakeParser:
    def __init__(self, pages):
        self.pages = pages

    def parse_document(self, file_bytes, filename):
        return {"filename": filename, "full_text": "\n\n".join(p["text"] for p in self.pages), "pages": self.pages,
                "tables": [], "images": [], "page_count": len(self.pages), "table_count": 0, "image_count": 0}


def fake_llm(*, system, user, **_):
    if '"facts"' in user:
        return {"facts": [
            {"type": "role", "name": "Buyer", "value": "Issues purchase orders", "confidence": 0.9, "context": "buyer"},
            {"type": "risk", "name": "Late vendor validation", "value": "Delays orders", "confidence": 0.7, "context": "x"},
            {"type": "nonsense", "name": "dropped", "confidence": 1},
        ]}
    found = re.findall(r"^- (.+) \((\w+)\):$", user, flags=re.M)
    return {"pages": [{"entity_name": n, "entity_type": t, "content": f"# {n}\nOverview of {n}."} for n, t in found]}


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(settings, "lp_library_local_path", "")
    fakes = _pipeline_fakes.install(monkeypatch, knowledge=True)
    monkeypatch.setattr(fact_extraction, "claude_generate_json", fake_llm)
    monkeypatch.setattr(wiki_page_generator, "claude_generate_json", fake_llm)
    parser = {"value": FakeParser([{"page_number": 1, "text": MARKDOWN_P1}, {"page_number": 2, "text": MARKDOWN_P2}])}
    monkeypatch.setattr(document_parsing_tasks, "get_docling_parser", lambda: parser["value"])
    with session_scope() as db:
        # The library scope is shared across tests in this database; start each test without wiki pages.
        from src.core.db.models import EmbeddingsMetadata, WikiPageDraft

        db.query(EmbeddingsMetadata).filter(EmbeddingsMetadata.project_id == LIBRARY_SCOPE).delete()
        db.query(WikiPageFinal).filter(WikiPageFinal.project_id == LIBRARY_SCOPE).delete()
        db.query(WikiPageDraft).filter(WikiPageDraft.project_id == LIBRARY_SCOPE).delete()
        uid = f"u_{uuid.uuid4().hex[:8]}"
        db.add(User(id=uid, email=f"{uid}@example.com", hashed_password="x", is_admin=True))

    def upload(content: bytes = None, filename: str = "vendor.md") -> str:
        content = content or f"# source {uuid.uuid4().hex}".encode()
        staged = tmp_path / uuid.uuid4().hex / filename
        staged.parent.mkdir(parents=True)
        staged.write_bytes(content)
        form = {"owner": "Maya Patel", "classification": "Internal", "rights": "Internal reuse permitted",
                "title": "", "category": "Procurement", "maturity": "", "version": "", "practice_id": ""}
        with session_scope() as db:
            return pipeline.queue_document(db, project_id=LIBRARY_SCOPE, user_id=uid, filename=filename,
                                           local_path=staged, sha256=hashlib.sha256(content).hexdigest(),
                                           size_bytes=len(content), library=form).job_id

    return {**fakes, "upload": upload, "uid": uid, "parser": parser}


def _job(db, job_id):
    return db.query(DocumentJob).filter(DocumentJob.job_id == job_id).one()


def _doc(db, job_id):
    return db.query(DocumentFile).filter(DocumentFile.job_id == job_id).one()


def _library_job(db, job):
    practice_id, library_job_id, _ = job.filename.split("/", 2)
    row = db.query(WorkbenchRecord).filter(WorkbenchRecord.collection == "ingestion_jobs",
                                           WorkbenchRecord.record_id == library_job_id).one()
    return practice_id, library_job_id, json.loads(row.payload_json)


def test_upload_runs_every_stage(env):
    job_id = env["upload"]()
    with session_scope() as db:
        job, doc = _job(db, job_id), _doc(db, job_id)
        practice_id, library_job_id, payload = _library_job(db, job)
        chunks = db.query(ChunkArchive).filter(ChunkArchive.document_file_id == doc.id).order_by(ChunkArchive.chunk_number).all()
        assert job.status == "completed" and job.completed_at is not None
        # intake: practice + library job; the S3 object is the stored source
        assert db.query(LpPractice).filter(LpPractice.id == practice_id).one().status == "Quality review"
        assert payload["stage"] == "Quality review" and payload["readable"] and payload["ingestionJobId"] == job_id
        assert doc.seaweedfs_file_id in env["s3"].objects
        # one chunker: section-aware passages with pages, numbered, mirrored in library_chunks
        assert [c.chunk_number for c in chunks] == list(range(1, len(chunks) + 1))
        assert all(c.source_type == "section" for c in chunks) and {c.page_number for c in chunks} <= {1, 2}
        stored = json.loads(db.query(WorkbenchRecord).filter(WorkbenchRecord.collection == "library_chunks",
                                                             WorkbenchRecord.record_id == library_job_id).one().payload_json)
        assert [c["chunkId"] for c in stored["chunks"]] == [c.id for c in chunks]
        assert all(c["section"] and c["quality"] for c in stored["chunks"])
        assert payload["citations"]["references"] == [1] and payload["validation"]["total"] == len(chunks)
        # embeddings in Postgres and Qdrant, then knowledge building
        assert db.query(ChunkEmbedding).filter(ChunkEmbedding.document_file_id == doc.id).count() == len(chunks)
        assert env["get_store"]().count(document_id=doc.id) == len(chunks)
        assert {f.fact_name for f in db.query(ExtractedFact).filter(ExtractedFact.project_id == LIBRARY_SCOPE)} >= {"Buyer"}
        assert env["get_store"]("wiki_pages").count(project_id=LIBRARY_SCOPE) >= 2
        assert db.query(InAppNotification).filter(InAppNotification.user_id == env["uid"]).one().notification_type == "success"


def test_status_lists_every_stage_in_order(env):
    from src.app.api.documents_async import ingestion_status

    job_id = env["upload"]()
    with session_scope() as db:
        status = ingestion_status(db, job_id)
    assert status["stages"] == ["intake", "uploading", "parsing", "chunking", "embedding", "library_validation",
                                "extracting_facts", "generating_wiki", "deduplicating", "indexing_wiki"]
    assert status["current_stage_index"] == len(status["stages"]) and status["practice_id"]
    assert status["counts"]["chunks"] == status["counts"]["embeddings"] > 0


def test_wiki_pages_are_deduplicated_across_documents(env):
    env["upload"](filename="a.md")
    second = env["upload"](filename="b.md")
    with session_scope() as db:
        pages = db.query(WikiPageFinal).filter(WikiPageFinal.project_id == LIBRARY_SCOPE).all()
        b_id = _doc(db, second).id
        assert len(pages) == 2
        assert all(p.merge_info["merge_count"] == 1 and b_id in p.merge_info["source_documents"] for p in pages)


def test_removing_a_document_removes_it_everywhere(env):
    job_id = env["upload"]()
    with session_scope() as db:
        doc = _doc(db, job_id)
        doc_id, key, name = doc.id, doc.seaweedfs_file_id, doc.filename
    pipeline.remove_document.apply(args=(LIBRARY_SCOPE, name)).get()
    with session_scope() as db:
        assert _job(db, job_id).status == "deleted"
        assert db.query(ChunkArchive).filter(ChunkArchive.document_file_id == doc_id).count() == 0
        assert db.query(WikiPageFinal).filter(WikiPageFinal.project_id == LIBRARY_SCOPE).count() == 0
    assert key not in env["s3"].objects and env["get_store"]().count(document_id=doc_id) == 0


def test_document_without_text_fails_and_the_library_job_says_so(env):
    env["parser"]["value"] = FakeParser([{"page_number": 1, "text": "# Only a title\n"}])
    job_id = env["upload"]()
    with session_scope() as db:
        job = _job(db, job_id)
        practice_id, _, payload = _library_job(db, job)
        assert job.status == "failed" and job.failed_stage == "chunking" and "no text" in job.error_message
        assert payload["outcome"] == "No readable text" and payload["readable"] is False
        assert db.query(LpPractice).filter(LpPractice.id == practice_id).one().status == "Not eligible"
        assert db.query(TaskFailure).filter(TaskFailure.project_id == LIBRARY_SCOPE).count() >= 1
        assert db.query(InAppNotification).filter(InAppNotification.user_id == env["uid"]).one().notification_type == "failure"


def test_assign_drafts_prefers_existing_pages_then_earlier_drafts():
    existing = [Candidate("wiki_1", "role", "buyer", [1.0, 0.0])]
    drafts = [
        Candidate("d1", "role", "buyer", [0.0, 1.0]),
        Candidate("d2", "risk", "late payment", [0.0, 1.0]),
        Candidate("d3", "risk", "delayed payment", [0.0, 0.99]),
    ]
    assert assign_drafts(drafts, existing, 0.85) == [("existing", "wiki_1"), ("new", None), ("draft", "d2")]


def test_fact_batches_respect_size_and_call_limit():
    batches = fact_extraction.batch_texts(["x" * 100] * 10, max_chars=250, max_batches=3)
    assert len(batches) == 3 and all(len(b) <= 250 for b in batches)


def test_s3_client_uploads_with_safe_checksum_mode():
    client = SeaweedFSClient("http://seaweed.test", "key", "secret", "aw-bucket")
    data = b"hello pdf"
    with Stubber(client._s3) as stub:
        stub.add_response(
            "put_object",
            {"ETag": '"abc"'},
            {"Bucket": "aw-bucket", "Key": "document_intake/p/j/a.pdf", "Body": data,
             "ContentType": "application/pdf", "Metadata": {"sha256": hashlib.sha256(data).hexdigest()}},
        )
        out = client.upload_file("document_intake/p/j/a.pdf", data, "application/pdf")
    assert out["etag"] == "abc" and out["size"] == len(data)
    assert client._s3.meta.config.request_checksum_calculation == "when_required"


def test_http_embeddings_batches_with_bearer_token():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append((request.url.path, request.headers["authorization"], len(body["inputs"]), body["normalize"]))
        return httpx.Response(200, json=[[0.1, 0.2, 0.3] for _ in body["inputs"]])

    svc = HttpEmbeddingService("https://emb.test/", "tok", "bge-small")
    svc._client = httpx.Client(base_url=svc.base_url, headers={"authorization": "Bearer tok"},
                               transport=httpx.MockTransport(handler))
    assert len(svc.embed_batch(["a", "", "c", "d", "e"], batch_size=2)) == 5
    assert calls == [("/embed", "Bearer tok", 2, True), ("/embed", "Bearer tok", 2, True), ("/embed", "Bearer tok", 1, True)]


def test_http_embeddings_rejects_short_response():
    svc = HttpEmbeddingService("https://emb.test", "", "m")
    svc._client = httpx.Client(base_url=svc.base_url, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[[1.0]])))
    with pytest.raises(RuntimeError, match="returned 1 vectors for 2 inputs"):
        svc.embed_batch(["a", "b"])


def test_qdrant_ids_stable_dimension_checked_and_https_port_kept():
    assert point_id_for("x_c00001") == point_id_for("x_c00001") != point_id_for("x_c00002")
    store = QdrantVectorStore("http://unused", None, "dims")
    store.client = QdrantClient(location=":memory:")
    store.ensure_collection(8)
    with pytest.raises(ValueError, match="holds 8-dim vectors"):
        store.ensure_collection(384)
    assert QdrantVectorStore("https://q.trycloudflare.com", "k", "c").client._client.rest_uri == "https://q.trycloudflare.com"
