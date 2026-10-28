"""In-process stand-ins for the ingestion pipeline's external services (S3, Qdrant, embeddings) + eager Celery."""

from __future__ import annotations

import hashlib

import pytest
from qdrant_client import QdrantClient

from src.core.config import settings
from src.core.vector_db.qdrant_client import QdrantVectorStore


class FakeS3:
    bucket = "aw-test"

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def upload_file(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data
        return {"bucket": self.bucket, "key": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "etag": "e"}

    def get_file(self, key):
        return self.objects[key]

    def head_file(self, key):
        return {"size": len(self.objects[key])} if key in self.objects else None

    def delete_file(self, key):
        self.objects.pop(key, None)


class FakeEmbedder:
    model_name = "fake-32"

    def __init__(self):
        self.embedded = 0

    def embed_batch(self, texts, batch_size=32):
        self.embedded += len(texts)
        return [[b / 255 - 0.5 for b in hashlib.sha256(t.encode()).digest()] for t in texts]


def install(monkeypatch: pytest.MonkeyPatch, *, knowledge: bool = False) -> dict:
    """Run the whole pipeline in-process (eager Celery) against fakes; returns the fakes for assertions."""
    from src.app.api import documents_async
    from src.core.embeddings import embedding_service as embedding_module
    from src.core.storage import seaweedfs_client as s3_module
    from src.core.vector_db import qdrant_client as qdrant_module
    from src.query import pipeline as query_pipeline
    from src.workers import (
        document_embedding_tasks,
        document_intake_tasks,
        document_knowledge_tasks,
        document_parsing_tasks,
    )
    from src.workers.celery_app import app

    monkeypatch.setattr(app.conf, "task_always_eager", True)
    monkeypatch.setattr(app.conf, "task_eager_propagates", False)
    monkeypatch.setattr(settings, "knowledge_building_enabled", knowledge)
    s3, embedder = FakeS3(), FakeEmbedder()
    stores: dict[str, QdrantVectorStore] = {}

    def get_store(collection_name=None, url=None):
        name = collection_name or "document_chunks"
        if name not in stores:
            stores[name] = QdrantVectorStore("http://unused", None, f"test_{name}")
            stores[name].client = QdrantClient(location=":memory:")
        return stores[name]

    for module in (document_intake_tasks, document_parsing_tasks, s3_module, documents_async):
        monkeypatch.setattr(module, "get_seaweedfs_client", lambda: s3)
    for module in (document_embedding_tasks, document_knowledge_tasks, qdrant_module, documents_async, query_pipeline):
        monkeypatch.setattr(module, "get_qdrant_client", get_store)
    for module in (document_embedding_tasks, document_knowledge_tasks, embedding_module, query_pipeline):
        monkeypatch.setattr(module, "get_embedding_service", lambda: embedder)
    return {"s3": s3, "embedder": embedder, "get_store": get_store}
