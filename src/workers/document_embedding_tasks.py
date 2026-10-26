"""Pipeline stage 4: embed chunks, keep the vectors in chunk_embeddings and index them in Qdrant.

Chunks whose text is identical to a chunk of a previous version of the same file reuse that vector, so a
changed file only embeds what changed. Once the new version is indexed, older versions are removed.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from src.core.config import settings
from src.core.db.models import ChunkArchive, ChunkEmbedding
from src.core.db.session import session_scope
from src.core.embeddings.embedding_service import get_embedding_service
from src.core.tz import ist_now
from src.core.vector_db.qdrant_client import get_qdrant_client, point_id_for
from src.workers.celery_app import app
from src.workers.pipeline import (
    IngestionTask,
    PermanentIngestionError,
    complete_job,
    other_versions,
    purge_document_file,
    update_job,
)

logger = logging.getLogger(__name__)

_PAYLOAD_TEXT_CHARS = 1000


def _text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@app.task(base=IngestionTask, stage="embedding")
def embed_chunks(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, document_file_id = ctx["job_id"], ctx["document_file_id"]
    with session_scope() as db:
        update_job(db, job_id, status="embedding")
        chunks = (
            db.query(ChunkArchive)
            .filter(ChunkArchive.document_file_id == document_file_id)
            .order_by(ChunkArchive.chunk_number)
            .all()
        )
        if not chunks:
            raise PermanentIngestionError(f"No chunks stored for document {document_file_id}")

        embedder = get_embedding_service()
        previous = other_versions(db, ctx["project_id"], ctx["filename"], document_file_id)
        reusable: dict[str, list[float]] = {}
        if previous:
            rows = (
                db.query(ChunkArchive.text, ChunkEmbedding.embedding)
                .join(ChunkEmbedding, ChunkEmbedding.chunk_id == ChunkArchive.id)
                .filter(
                    ChunkEmbedding.document_file_id.in_([p.id for p in previous]),
                    ChunkEmbedding.model_name == embedder.model_name[:50],
                )
                .all()
            )
            reusable = {_text_key(text): vec for text, vec in rows}

        keys = [_text_key(c.text) for c in chunks]
        todo = [i for i, k in enumerate(keys) if k not in reusable]
        fresh = embedder.embed_batch([chunks[i].text for i in todo], settings.embedding_batch_size) if todo else []
        if len(fresh) != len(todo):
            raise RuntimeError(f"Got {len(fresh)} embeddings for {len(todo)} chunks")
        computed = dict(zip(todo, fresh))
        vectors = [computed[i] if i in computed else reusable[keys[i]] for i in range(len(chunks))]

        store = get_qdrant_client()
        store.delete_where(document_id=document_file_id)
        stored = store.store_embeddings_batch(
            [
                {
                    "chunk_id": c.id,
                    "embedding": v,
                    "metadata": {
                        "chunk_id": c.id,
                        "document_id": document_file_id,
                        "job_id": job_id,
                        "project_id": c.project_id,
                        "filename": ctx["filename"],
                        "chunk_number": c.chunk_number,
                        "page_number": c.page_number,
                        "source_type": c.source_type,
                        "text": c.text[:_PAYLOAD_TEXT_CHARS],
                    },
                }
                for c, v in zip(chunks, vectors)
            ]
        )

        db.query(ChunkEmbedding).filter(ChunkEmbedding.document_file_id == document_file_id).delete()
        now = ist_now()
        for c, v in zip(chunks, vectors):
            db.add(
                ChunkEmbedding(
                    id=f"emb_{c.id}"[:64],
                    chunk_id=c.id,
                    document_file_id=document_file_id,
                    project_id=c.project_id,
                    embedding=v,
                    embedding_dimension=len(v),
                    model_name=embedder.model_name[:50],
                    qdrant_point_id=point_id_for(c.id),
                    embedding_generated_at=now,
                    created_at=now,
                )
            )
        db.commit()

        # The new version is searchable now; drop older versions of the same file everywhere.
        for doc in previous:
            purge_document_file(db, doc)

        reused = len(chunks) - len(todo)
        summary = f"{len(chunks)} chunks, {stored} vectors ({reused} reused from the previous version)"
        if not ctx.get("knowledge"):
            complete_job(db, ctx, summary)

    logger.info(
        "[EMBED] job=%s indexed %d chunks (%d dims, %d reused) in Qdrant collection %s",
        job_id, stored, len(vectors[0]), reused, store.collection_name,
    )
    return {
        **ctx,
        "embedded": stored,
        "reused_embeddings": reused,
        "embedding_dimension": len(vectors[0]),
        "qdrant_collection": store.collection_name,
    }
