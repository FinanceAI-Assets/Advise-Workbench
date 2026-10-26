"""Text embeddings: the shared embedding service over HTTP, or a local sentence-transformers model."""

from __future__ import annotations

import logging

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class HttpEmbeddingService:
    """Text Embeddings Inference style API: POST {base}/embed {"inputs": [...], "normalize": true}."""

    def __init__(self, base_url: str, api_key: str, model_name: str, timeout_sec: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        headers = {"authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout_sec)

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t if t and t.strip() else " " for t in texts[i : i + batch_size]]
            resp = self._client.post("/embed", json={"inputs": batch, "normalize": True})
            resp.raise_for_status()
            out = resp.json()
            if len(out) != len(batch):
                raise RuntimeError(f"embedding service returned {len(out)} vectors for {len(batch)} inputs")
            vectors.extend(out)
        return vectors

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


class LocalEmbeddingService:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        logger.info("[EMBED] Loading local model %s", model_name)
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        batch = [t if t and t.strip() else " " for t in texts]
        return self.model.encode(batch, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False).tolist()

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


_embedding_service: HttpEmbeddingService | LocalEmbeddingService | None = None


def get_embedding_service() -> HttpEmbeddingService | LocalEmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        if settings.embedding_base_url:
            _embedding_service = HttpEmbeddingService(
                settings.embedding_base_url,
                settings.embedding_api_key,
                settings.embedding_model,
                settings.embedding_timeout_sec,
            )
        else:
            _embedding_service = LocalEmbeddingService(settings.embedding_model)
    return _embedding_service
