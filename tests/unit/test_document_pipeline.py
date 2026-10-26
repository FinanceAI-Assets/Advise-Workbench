"""Document ingestion pipeline: all stages, file lifecycle (add / unchanged / change / delete), failures, clients."""

import hashlib
import json
import re
import uuid

import httpx
import pytest
from botocore.stub import Stubber
from qdrant_client import QdrantClient

from src.core.db.models import (
    ChunkArchive,
    ChunkEmbedding,
    DocumentFile,
    DocumentJob,
    ExtractedFact,
    InAppNotification,
    Project,
    TaskFailure,
    User,
    WikiPageFinal,
)
from src.core.db.session import session_scope
from src.core.embeddings.embedding_service import HttpEmbeddingService
from src.core.parsing.chunking_service import ChunkingService
from src.core.storage import seaweedfs_client as s3_module
from src.core.storage.seaweedfs_client import SeaweedFSClient
from src.core.vector_db import qdrant_client as qdrant_module
from src.core.vector_db.qdrant_client import QdrantVectorStore, point_id_for
from src.memory.facts import fact_extraction
from src.memory.wiki import wiki_page_generator
from src.memory.wiki.deduplication import Candidate, assign_drafts
from src.workers import (
    document_embedding_tasks,
    document_intake_tasks,
    document_knowledge_tasks,
    document_parsing_tasks,
    pipeline,
)
from src.workers.celery_app import app

PAGE_TEXT = "The buyer issues a purchase order after vendor validation. " * 40


class FakeS3:
    bucket = "aw-test"

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def upload_file(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data
        return {"bucket": self.bucket, "key": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "etag": "e"}

    def get_file(self, key):
        return self.objects[key]

    def delete_file(self, key):
        self.objects.pop(key, None)


class FakeParser:
    def __init__(self, pages, tables=True):
        self.pages, self.tables = pages, tables

    def parse_document(self, file_bytes, filename):
        tables = [{"page_number": 2, "table_index": 1, "markdown": "| Role | Control |\n|---|---|\n| Buyer | 3-way match |"}]
        return {
            "filename": filename,
            "full_text": "\n\n".join(p["text"] for p in self.pages),
            "pages": self.pages,
            "tables": tables if self.tables else [],
            "images": [],
            "page_count": len(self.pages),
            "table_count": 1 if self.tables else 0,
            "image_count": 0,
        }


class FakeEmbedder:
    model_name = "fake-32"

    def __init__(self):
        self.embedded = 0

    def embed_batch(self, texts, batch_size=32):
        self.embedded += len(texts)
        return [[b / 255 - 0.5 for b in hashlib.sha256(t.encode()).digest()] for t in texts]


def fake_llm(*, system, user, **_):
    if '"facts"' in user:
        return {
            "facts": [
                {"type": "role", "name": "Buyer", "value": "Issues purchase orders", "confidence": 0.9, "context": "buyer"},
                {"type": "risk", "name": "Late vendor validation", "value": "Delays orders", "confidence": 0.7, "context": "x"},
                {"type": "nonsense", "name": "dropped", "confidence": 1},
            ]
        }
    found = re.findall(r"^- (.+) \((\w+)\):$", user, flags=re.M)
    return {"pages": [{"entity_name": n, "entity_type": t, "content": f"# {n}\nOverview of {n}."} for n, t in found]}


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(app.conf, "task_always_eager", True)
    monkeypatch.setattr(app.conf, "task_eager_propagates", False)
    monkeypatch.setattr(pipeline.settings, "knowledge_building_enabled", True)
    s3, embedder = FakeS3(), FakeEmbedder()
    stores: dict[str, QdrantVectorStore] = {}

    def get_store(collection_name=None, url=None):
        name = collection_name or "document_chunks"
        if name not in stores:
            stores[name] = QdrantVectorStore("http://unused", None, f"test_{name}")
            stores[name].client = QdrantClient(location=":memory:")
        return stores[name]

    for module in (document_intake_tasks, document_parsing_tasks, s3_module):
        monkeypatch.setattr(module, "get_seaweedfs_client", lambda: s3)
    for module in (document_embedding_tasks, document_knowledge_tasks, qdrant_module):
        monkeypatch.setattr(module, "get_qdrant_client", get_store)
    for module in (document_embedding_tasks, document_knowledge_tasks):
        monkeypatch.setattr(module, "get_embedding_service", lambda: embedder)
    monkeypatch.setattr(fact_extraction, "claude_generate_json", fake_llm)
    monkeypatch.setattr(wiki_page_generator, "claude_generate_json", fake_llm)
    parser = {"value": FakeParser([{"page_number": 1, "text": PAGE_TEXT}, {"page_number": 2, "text": "Approvals on page two."}])}
    monkeypatch.setattr(document_parsing_tasks, "get_docling_parser", lambda: parser["value"])

    with session_scope() as db:
        uid, pid = f"u_{uuid.uuid4().hex[:8]}", f"p_{uuid.uuid4().hex[:8]}"
        db.add(User(id=uid, email=f"{uid}@example.com", hashed_password="x"))
        db.flush()
        db.add(Project(id=pid, name="pipeline", created_by=uid))

    def upload(content: bytes = b"%PDF-1.4 v1", filename: str = "report.pdf") -> str:
        path = tmp_path / filename
        path.write_bytes(content)
        with session_scope() as db:
            return pipeline.queue_document(
                db, project_id=pid, user_id=uid, filename=filename, local_path=path,
                sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
            ).job_id

    return {"upload": upload, "s3": s3, "get_store": get_store, "embedder": embedder, "pid": pid, "uid": uid, "parser": parser}


def _job(db, job_id):
    return db.query(DocumentJob).filter(DocumentJob.job_id == job_id).one()


def _doc(db, job_id):
    return db.query(DocumentFile).filter(DocumentFile.job_id == job_id).one()


def test_upload_runs_every_stage(env):
    job_id = env["upload"]()
    with session_scope() as db:
        job, doc = _job(db, job_id), _doc(db, job_id)
        chunks = db.query(ChunkArchive).filter(ChunkArchive.document_file_id == doc.id).order_by(ChunkArchive.chunk_number).all()
        assert job.status == "completed" and job.completed_at is not None
        assert env["s3"].objects[doc.seaweedfs_file_id] == b"%PDF-1.4 v1"
        assert [c.chunk_number for c in chunks] == list(range(1, len(chunks) + 1))
        assert {c.page_number for c in chunks if c.source_type == "main_text"} == {1, 2}
        assert db.query(ChunkEmbedding).filter(ChunkEmbedding.document_file_id == doc.id).count() == len(chunks)
        assert env["get_store"]().count(document_id=doc.id) == len(chunks)
        names = {f.fact_name for f in db.query(ExtractedFact).filter(ExtractedFact.project_id == env["pid"])}
        assert names == {"Buyer", "Late vendor validation"}
        finals = db.query(WikiPageFinal).filter(WikiPageFinal.project_id == env["pid"]).all()
        assert sorted(p.entity_name for p in finals) == ["Buyer", "Late vendor validation"]
        assert all(p.is_published and p.merge_info["source_documents"] == [doc.id] for p in finals)
        assert env["get_store"]("wiki_pages").count(project_id=env["pid"]) == 2
        note = db.query(InAppNotification).filter(InAppNotification.user_id == env["uid"]).one()
        assert note.notification_type == "success"


def test_unchanged_reupload_does_nothing(env):
    env["upload"]()
    embedded = env["embedder"].embedded
    second = env["upload"]()
    with session_scope() as db:
        job = _job(db, second)
        assert job.status == "completed" and job.parse_mode == "unchanged"
        assert db.query(DocumentFile).filter(DocumentFile.job_id == second).count() == 0
    assert env["embedder"].embedded == embedded


def test_changed_file_reuses_vectors_and_replaces_old_version(env):
    first = env["upload"](b"%PDF v1")
    with session_scope() as db:
        old = _doc(db, first)
        old_id, old_key = old.id, old.seaweedfs_file_id
        old_chunks = db.query(ChunkArchive).filter(ChunkArchive.document_file_id == old_id).count()
    env["parser"]["value"] = FakeParser([{"page_number": 1, "text": PAGE_TEXT}, {"page_number": 2, "text": "Changed two."}])
    before = env["embedder"].embedded
    second = env["upload"](b"%PDF v2")
    with session_scope() as db:
        new = _doc(db, second)
        assert _job(db, second).status == "completed"
        assert db.query(ChunkArchive).filter(ChunkArchive.document_file_id == old_id).count() == 0
        assert env["get_store"]().count(document_id=old_id) == 0
        assert old_key not in env["s3"].objects
        assert env["get_store"]().count(document_id=new.id) == old_chunks
        pages = db.query(WikiPageFinal).filter(WikiPageFinal.project_id == env["pid"]).all()
        assert pages and all(p.merge_info["source_documents"] == [new.id] for p in pages)
    # only the changed chunk (+ wiki texts) is embedded again; the identical chunks reuse their vectors
    assert env["embedder"].embedded - before < old_chunks + 4


def test_wiki_pages_are_deduplicated_across_documents(env):
    env["upload"](b"%PDF a", "a.pdf")
    second = env["upload"](b"%PDF b", "b.pdf")
    with session_scope() as db:
        pages = db.query(WikiPageFinal).filter(WikiPageFinal.project_id == env["pid"]).all()
        b_id = _doc(db, second).id
        assert len(pages) == 2
        assert all(p.merge_info["merge_count"] == 1 and b_id in p.merge_info["source_documents"] for p in pages)


def test_deleting_a_file_removes_it_everywhere(env):
    job_id = env["upload"]()
    with session_scope() as db:
        doc = _doc(db, job_id)
        doc_id, key = doc.id, doc.seaweedfs_file_id
    pipeline.remove_document.apply(args=(env["pid"], "report.pdf")).get()
    with session_scope() as db:
        assert _job(db, job_id).status == "deleted"
        assert db.query(ChunkArchive).filter(ChunkArchive.document_file_id == doc_id).count() == 0
        assert db.query(ChunkEmbedding).filter(ChunkEmbedding.document_file_id == doc_id).count() == 0
        assert db.query(WikiPageFinal).filter(WikiPageFinal.project_id == env["pid"]).count() == 0
    assert key not in env["s3"].objects
    assert env["get_store"]().count(document_id=doc_id) == 0
    assert env["get_store"]("wiki_pages").count(project_id=env["pid"]) == 0


def test_document_without_text_fails_with_notification(env):
    env["parser"]["value"] = FakeParser([{"page_number": 1, "text": " "}], tables=False)
    job_id = env["upload"]()
    with session_scope() as db:
        job = _job(db, job_id)
        assert job.status == "failed" and job.failed_stage == "chunking"
        assert "no text" in (job.error_message or "")
        assert db.query(TaskFailure).filter(TaskFailure.project_id == env["pid"]).one().is_final_failure
        note = db.query(InAppNotification).filter(InAppNotification.user_id == env["uid"]).one()
        assert note.notification_type == "failure"


def test_search_only_mode_completes_after_embedding(env, monkeypatch):
    monkeypatch.setattr(pipeline.settings, "knowledge_building_enabled", False)
    job_id = env["upload"]()
    with session_scope() as db:
        assert _job(db, job_id).status == "completed"
        assert db.query(ExtractedFact).filter(ExtractedFact.project_id == env["pid"]).count() == 0


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


def test_chunks_are_numbered_across_pages_and_tables():
    groups = ChunkingService(200, 40).create_chunks_from_parsed(
        {
            "pages": [{"page_number": 1, "text": "Alpha sentence. " * 30}, {"page_number": 3, "text": "Beta. " * 5}],
            "tables": [{"page_number": 3, "table_index": 1, "markdown": "| a | b |"}],
        }
    )
    every = groups["main_text"] + groups["table_text"]
    assert [c["chunk_number"] for c in every] == list(range(1, groups["total_chunks"] + 1))
    assert {c["source"]["page_number"] for c in groups["main_text"]} == {1, 3}


def test_qdrant_ids_stable_dimension_checked_and_https_port_kept():
    assert point_id_for("x_c00001") == point_id_for("x_c00001") != point_id_for("x_c00002")
    store = QdrantVectorStore("http://unused", None, "dims")
    store.client = QdrantClient(location=":memory:")
    store.ensure_collection(8)
    with pytest.raises(ValueError, match="holds 8-dim vectors"):
        store.ensure_collection(384)
    assert QdrantVectorStore("https://q.trycloudflare.com", "k", "c").client._client.rest_uri == "https://q.trycloudflare.com"
