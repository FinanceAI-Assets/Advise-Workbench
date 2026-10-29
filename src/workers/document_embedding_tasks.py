"""Pipeline stage: embed the passages of a document and index them in Qdrant.

Passages are stored once per unique text (see the chunking stage), so a passage that is already embedded is not
embedded again: its Qdrant point just gains this document and job in its ``document_id`` / ``job_id`` lists.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.config import settings
from src.core.db.models import ChunkArchive, ChunkEmbedding, DocumentChunkLink
from src.core.db.session import session_scope
from src.core.embeddings.embedding_service import get_embedding_service
from src.core.tz import ist_now
from src.core.vector_db.qdrant_client import get_qdrant_client, point_id_for
from src.workers.celery_app import app
from src.workers.pipeline import IngestionTask, PermanentIngestionError, complete_job, update_job

logger = logging.getLogger(__name__)

_PAYLOAD_TEXT_CHARS = 1000


@app.task(base=IngestionTask, stage="embedding")
def embed_chunks(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, document_file_id = ctx["job_id"], ctx["document_file_id"]
    with session_scope() as db:
        update_job(db, job_id, status="embedding")
        links = (
            db.query(DocumentChunkLink)
            .filter(DocumentChunkLink.document_file_id == document_file_id)
            .order_by(DocumentChunkLink.chunk_number)
            .all()
        )
        if not links:
            raise PermanentIngestionError(f"No passages stored for document {document_file_id}")
        passage_ids = list(dict.fromkeys(link.chunk_id for link in links))
        passages = {c.id: c for c in db.query(ChunkArchive).filter(ChunkArchive.id.in_(passage_ids))}
        stored = {e.chunk_id: e for e in db.query(ChunkEmbedding).filter(ChunkEmbedding.chunk_id.in_(passage_ids))}
        todo = [p for p in passage_ids if p not in stored]

        embedder = get_embedding_service()
        vectors = embedder.embed_batch([passages[p].text for p in todo], settings.embedding_batch_size) if todo else []
        if len(vectors) != len(todo):
            raise RuntimeError(f"Got {len(vectors)} embeddings for {len(todo)} passages")

        def record(passage_id: str, vector: list[float]) -> dict[str, Any]:
            p = passages[passage_id]
            return {
                "chunk_id": passage_id,
                "embedding": vector,
                "metadata": {
                    "chunk_id": passage_id,
                    "document_id": [document_file_id],
                    "job_id": [job_id],
                    "project_id": p.project_id,
                    "page_number": p.page_number,
                    "source_type": p.source_type,
                    "text": p.text[:_PAYLOAD_TEXT_CHARS],
                },
            }

        store = get_qdrant_client()
        reused = [p for p in passage_ids if p in stored]
        missing_points = store.add_to_lists(reused, document_id=document_file_id, job_id=job_id)
        # Points lost from Qdrant (e.g. a reset collection) are restored from the stored embedding, not re-embedded.
        restore = [record(p, stored[p].embedding) for p in missing_points]
        new = [record(p, v) for p, v in zip(todo, vectors)]
        indexed = store.store_embeddings_batch(new + restore)

        now = ist_now()
        for passage_id, vector in zip(todo, vectors):
            db.add(
                ChunkEmbedding(
                    id=f"emb_{passage_id}"[:64],
                    chunk_id=passage_id,
                    document_file_id=passages[passage_id].document_file_id,
                    project_id=passages[passage_id].project_id,
                    embedding=vector,
                    embedding_dimension=len(vector),
                    model_name=embedder.model_name[:50],
                    qdrant_point_id=point_id_for(passage_id),
                    embedding_generated_at=now,
                    created_at=now,
                )
            )
        db.commit()
        summary = f"{len(passage_ids)} passages: {len(todo)} embedded, {len(reused)} reused from the library"
        if not ctx.get("knowledge") and not ctx.get("library"):
            complete_job(db, ctx, summary)

    logger.info("[EMBED] job=%s %s (%d points written) in %s", job_id, summary, indexed, store.collection_name)
    return {
        **ctx,
        "embedded": len(todo),
        "reused_embeddings": len(reused),
        "qdrant_collection": store.collection_name,
    }
