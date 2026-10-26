"""Qdrant vector store for document chunks and wiki pages."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from src.core.config import settings

logger = logging.getLogger(__name__)

_POINT_NAMESPACE = uuid.UUID("5b6d3f0e-6a8e-4c43-9a8e-2f1d6c0b7a11")


def point_id_for(key: str) -> str:
    """Stable Qdrant point id for a chunk/wiki id, so re-runs overwrite instead of duplicating."""
    return str(uuid.uuid5(_POINT_NAMESPACE, key))


def _match(**fields: str) -> Filter:
    return Filter(must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in fields.items()])


class QdrantVectorStore:
    def __init__(self, url: str, api_key: str | None, collection_name: str, timeout_sec: int = 60):
        self.url = url
        self.collection_name = collection_name
        # qdrant-client appends :6333 to a URL without a port; tunnel/proxy links serve on the scheme's port.
        port = urlparse(url).port or (6333 if urlparse(url).scheme == "http" else None)
        self.client = QdrantClient(
            url=url, port=port, api_key=api_key or None, timeout=timeout_sec, check_compatibility=False
        )

    def ensure_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.collection_name):
            existing = self.client.get_collection(self.collection_name).config.params.vectors
            size = getattr(existing, "size", None)
            if size is not None and size != vector_size:
                raise ValueError(
                    f"Qdrant collection {self.collection_name} holds {size}-dim vectors but the embedding "
                    f"model produces {vector_size}; use another collection name or delete the collection"
                )
            return
        logger.info("[QDRANT] Creating collection %s (%d dims, cosine)", self.collection_name, vector_size)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        for field in ("project_id", "document_id"):
            self.client.create_payload_index(
                self.collection_name, field_name=field, field_schema=PayloadSchemaType.KEYWORD
            )

    def store_embeddings_batch(self, embeddings: list[dict[str, Any]]) -> int:
        """embeddings: [{"chunk_id": str, "embedding": list[float], "metadata": dict}]"""
        if not embeddings:
            return 0
        self.ensure_collection(len(embeddings[0]["embedding"]))
        points = [
            PointStruct(id=point_id_for(item["chunk_id"]), vector=item["embedding"], payload=item["metadata"])
            for item in embeddings
        ]
        for i in range(0, len(points), 256):
            self.client.upsert(collection_name=self.collection_name, points=points[i : i + 256], wait=True)
        logger.info("[QDRANT] Upserted %d points into %s", len(points), self.collection_name)
        return len(points)

    def search(
        self,
        query_embedding: list[float],
        project_id: str | None = None,
        limit: int = 5,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=_match(project_id=project_id) if project_id else None,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {"chunk_id": p.payload.get("chunk_id"), "score": p.score, "text": p.payload.get("text"), "metadata": p.payload}
            for p in res.points
        ]

    def count(self, **fields: str) -> int:
        if not self.client.collection_exists(self.collection_name):
            return 0
        flt = _match(**fields) if fields else None
        return self.client.count(self.collection_name, count_filter=flt, exact=True).count

    def scroll(self, limit: int = 5, **fields: str) -> list[dict[str, Any]]:
        if not self.client.collection_exists(self.collection_name):
            return []
        points, _ = self.client.scroll(
            self.collection_name, scroll_filter=_match(**fields) if fields else None, limit=limit, with_payload=True
        )
        return [{"id": str(p.id), "payload": p.payload} for p in points]

    def get_vectors(self, keys: list[str]) -> dict[str, list[float]]:
        """Stored vectors for the given chunk/wiki ids (missing ids are left out)."""
        if not keys or not self.client.collection_exists(self.collection_name):
            return {}
        by_point = {point_id_for(k): k for k in keys}
        points = self.client.retrieve(self.collection_name, ids=list(by_point), with_vectors=True, with_payload=False)
        return {by_point[str(p.id)]: list(p.vector) for p in points if p.vector is not None}

    def delete_keys(self, keys: list[str]) -> None:
        if keys and self.client.collection_exists(self.collection_name):
            self.client.delete(self.collection_name, points_selector=[point_id_for(k) for k in keys], wait=True)

    def delete_where(self, **fields: str) -> None:
        if self.client.collection_exists(self.collection_name):
            self.client.delete(self.collection_name, points_selector=FilterSelector(filter=_match(**fields)), wait=True)

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.warning("[QDRANT] Health check failed: %s", e)
            return False


def get_qdrant_client(collection_name: str | None = None, url: str | None = None) -> QdrantVectorStore:
    """Collection names get QDRANT_COLLECTION_PREFIX (your namespace on the shared Qdrant)."""
    name = f"{settings.qdrant_collection_prefix}{collection_name or settings.qdrant_collection}"
    return QdrantVectorStore(url or settings.qdrant_url, settings.qdrant_api_key, name)
