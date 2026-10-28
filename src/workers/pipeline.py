"""Document ingestion pipeline orchestration.

A project file that is added or changed runs, as one Celery chain:

  uploading -> parsing -> chunking -> embedding -> extracting_facts -> generating_wiki -> deduplicating
  -> indexing_wiki -> completed

(the four knowledge stages only when KNOWLEDGE_BUILDING_ENABLED). Each stage receives the context dict
returned by the previous one and records its progress on ``DocumentJob.status``. A failing stage is
retried (``retrying``); when it gives up the job becomes ``failed`` with ``failed_stage`` and
``error_message``, a ``task_failures`` row and an in-app notification. Re-uploading identical content
completes at once without work; a changed file reuses embeddings of unchanged chunks and then replaces the
previous version everywhere. Deleting a file removes it from S3, Postgres and Qdrant.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from celery import Task, chain
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.db.models import (
    ChunkArchive,
    ChunkEmbedding,
    DocumentChunkLink,
    DocumentFile,
    DocumentJob,
    EmbeddingsMetadata,
    ExtractedFact,
    ParsedDocument,
    TaskFailure,
    WikiPageDraft,
    WikiPageFinal,
)
from src.core.db.session import session_scope
from src.core.notifications.notification_service import notify_in_app
from src.core.observability.otel_tracing import start_span
from src.core.tz import ist_now
from src.workers.celery_app import app

logger = logging.getLogger(__name__)

LIBRARY_SCOPE = "library"  # scope id of Leading Practice Library sources (stored in the project_id columns)

SEARCH_STAGES = ["intake", "uploading", "parsing", "chunking", "embedding", "library_validation"]
KNOWLEDGE_STAGES = ["extracting_facts", "generating_wiki", "deduplicating", "indexing_wiki"]
TERMINAL_STATUSES = {"completed", "failed", "deleted"}


class PermanentIngestionError(ValueError):
    """A failure that retrying cannot fix (bad file, nothing to index, file replaced)."""


def update_job(db: Session, job_id: str, **fields: Any) -> DocumentJob:
    job = db.query(DocumentJob).filter(DocumentJob.job_id == job_id).first()
    if job is None:
        raise PermanentIngestionError(f"DocumentJob {job_id} not found")
    for key, value in fields.items():
        setattr(job, key, value)
    job.updated_at = ist_now()
    db.commit()
    return job


class IngestionTask(Task):
    """Base for pipeline stages: retry policy, a trace span per stage, failure bookkeeping."""

    stage = "unknown"
    autoretry_for = (Exception,)
    dont_autoretry_for = (PermanentIngestionError,)
    max_retries = settings.celery_task_max_retries
    retry_backoff = 5
    retry_backoff_max = 60
    retry_jitter = False

    def __call__(self, *args, **kwargs):
        ctx = args[0] if args else {}
        attrs = {"job_id": ctx.get("job_id", ""), "project_id": ctx.get("project_id", ""), "stage": self.stage}
        with start_span(f"ingestion.{self.stage}", attributes=attrs):
            return super().__call__(*args, **kwargs)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        ctx = args[0] if args else {}
        try:
            with session_scope() as db:
                update_job(db, ctx["job_id"], status="retrying", error_message=f"{self.stage}: {exc}"[:1000])
        except Exception:
            logger.exception("[PIPELINE] Could not mark job %s as retrying", ctx.get("job_id"))

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        ctx = args[0] if args else {}
        job_id = ctx.get("job_id")
        logger.error("[PIPELINE] %s failed for job %s: %s", self.stage, job_id, exc)
        try:
            with session_scope() as db:
                db.add(
                    TaskFailure(
                        id=f"failure_{uuid.uuid4().hex[:16]}",
                        task_name=self.name.rsplit(".", 1)[-1],
                        document_file_id=ctx.get("document_file_id") or "",
                        project_id=ctx.get("project_id", ""),
                        error_message=str(exc)[:500],
                        error_type=type(exc).__name__,
                        retry_count=self.request.retries,
                        max_retries=self.max_retries,
                        is_final_failure=True,
                    )
                )
                if job_id:
                    update_job(db, job_id, status="failed", failed_stage=self.stage, error_message=str(exc)[:1000])
                if ctx.get("library_job_id"):
                    from src.app.api.admin_library import fail_source

                    fail_source(db, ctx, self.stage, str(exc))
                if ctx.get("user_id") and ctx.get("project_id"):
                    notify_in_app(
                        db,
                        user_id=ctx["user_id"],
                        project_id=ctx["project_id"],
                        notification_type="failure",
                        title=f"Processing failed: {ctx.get('filename', '')}",
                        message=f"Stage '{self.stage}' failed: {str(exc)[:300]}",
                        document_file_id=ctx.get("document_file_id"),
                    )
        except Exception:
            logger.exception("[PIPELINE] Could not record failure for job %s", job_id)


def complete_job(db: Session, ctx: dict[str, Any], summary: str) -> None:
    update_job(db, ctx["job_id"], status="completed", completed_at=ist_now(), error_message=None, failed_stage=None)
    notify_in_app(
        db,
        user_id=ctx["user_id"],
        project_id=ctx["project_id"],
        notification_type="success",
        title=f"Ready for search: {ctx['filename']}",
        message=summary,
        document_file_id=ctx.get("document_file_id"),
    )
    logger.info("[PIPELINE] job %s completed: %s", ctx["job_id"], summary)


# ------------------------------------------------------------------------------------- versions
def other_versions(db: Session, project_id: str, filename: str, exclude_id: str | None) -> list[DocumentFile]:
    q = db.query(DocumentFile).filter(DocumentFile.project_id == project_id, DocumentFile.filename == filename)
    if exclude_id:
        q = q.filter(DocumentFile.id != exclude_id)
    return q.all()


def purge_document_file(db: Session, doc: DocumentFile, *, delete_object: bool = True) -> None:
    """Remove everything one stored version produced: S3 object, chunks, vectors, facts, wiki contributions."""
    from src.core.storage.seaweedfs_client import get_seaweedfs_client
    from src.core.vector_db.qdrant_client import get_qdrant_client

    store = get_qdrant_client()
    # Passages are shared across versions/documents: drop only this document's links; a passage (row, vector and
    # point) is deleted once nothing links to it any more.
    passage_ids = {c for (c,) in db.query(DocumentChunkLink.chunk_id).filter(DocumentChunkLink.document_file_id == doc.id)}
    db.query(DocumentChunkLink).filter(DocumentChunkLink.document_file_id == doc.id).delete(synchronize_session=False)
    db.flush()
    still_used = (
        {c for (c,) in db.query(DocumentChunkLink.chunk_id).filter(DocumentChunkLink.chunk_id.in_(passage_ids)).distinct()}
        if passage_ids else set()
    )
    orphaned = sorted(passage_ids - still_used)
    store.remove_from_lists(sorted(passage_ids & still_used), document_id=doc.id, job_id=doc.job_id)
    store.delete_keys(orphaned)
    store.delete_where(document_id=doc.id)  # points of documents ingested before passages were shared
    if delete_object and doc.seaweedfs_file_id:
        get_seaweedfs_client().delete_file(doc.seaweedfs_file_id)

    parsed_ids = [p.id for p in db.query(ParsedDocument.id).filter(ParsedDocument.document_file_id == doc.id)]
    if orphaned:
        db.query(ChunkEmbedding).filter(ChunkEmbedding.chunk_id.in_(orphaned)).delete(synchronize_session=False)
        db.query(ChunkArchive).filter(ChunkArchive.id.in_(orphaned)).delete(synchronize_session=False)
    # Unshared rows of documents ingested before passages were shared.
    legacy = [c for (c,) in db.query(ChunkArchive.id).filter(ChunkArchive.document_file_id == doc.id) if c not in still_used]
    if legacy:
        db.query(ChunkEmbedding).filter(ChunkEmbedding.chunk_id.in_(legacy)).delete(synchronize_session=False)
        db.query(ChunkArchive).filter(ChunkArchive.id.in_(legacy)).delete(synchronize_session=False)
    if parsed_ids:
        db.query(ExtractedFact).filter(ExtractedFact.parsed_document_id.in_(parsed_ids)).delete(synchronize_session=False)
        db.query(WikiPageDraft).filter(WikiPageDraft.parsed_document_id.in_(parsed_ids)).delete(synchronize_session=False)
    remove_wiki_contributions(db, doc.project_id, doc.id)
    db.commit()
    logger.info("[PIPELINE] purged derived data of %s (%s)", doc.id, doc.filename)


def remove_wiki_contributions(db: Session, project_id: str, document_file_id: str) -> None:
    """Drop a document from the wiki pages it contributed to; delete pages no other document supports."""
    from src.core.vector_db.qdrant_client import get_qdrant_client

    orphaned: list[str] = []
    for page in db.query(WikiPageFinal).filter(WikiPageFinal.project_id == project_id).all():
        info = dict(page.merge_info or {})
        sources = [s for s in info.get("source_documents", []) if s != document_file_id]
        if len(sources) == len(info.get("source_documents", [])):
            continue
        if sources:
            info["source_documents"] = sources
            page.merge_info = info
            page.updated_at = ist_now()
        else:
            orphaned.append(page.id)
    if orphaned:
        db.query(EmbeddingsMetadata).filter(EmbeddingsMetadata.wiki_id.in_(orphaned)).delete(synchronize_session=False)
        db.query(WikiPageFinal).filter(WikiPageFinal.id.in_(orphaned)).delete(synchronize_session=False)
        get_qdrant_client(settings.qdrant_wiki_collection).delete_keys(orphaned)


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def remove_document(self, project_id: str, filename: str) -> dict[str, Any]:
    """A project file was deleted: remove every stored version from S3, Postgres and Qdrant."""
    try:
        with session_scope() as db:
            versions = other_versions(db, project_id, filename, None)
            for doc in versions:
                purge_document_file(db, doc)
                job = db.query(DocumentJob).filter(DocumentJob.job_id == doc.job_id).first()
                if job and job.status not in {"failed"}:
                    job.status = "deleted"
                    job.updated_at = ist_now()
            db.commit()
        logger.info("[PIPELINE] removed %d stored version(s) of %s/%s", len(versions), project_id, filename)
        return {"project_id": project_id, "filename": filename, "versions_removed": len(versions)}
    except Exception as exc:
        raise self.retry(exc=exc)


# --------------------------------------------------------------------------------------- queueing
def start_pipeline(ctx: dict[str, Any]) -> str:
    """Queue the stages as one Celery chain; returns the Celery id of the chain."""
    from src.workers.document_embedding_tasks import embed_chunks
    from src.workers.document_intake_tasks import upload_to_seaweedfs
    from src.workers.document_knowledge_tasks import (
        deduplicate_wiki_pages,
        extract_facts_from_chunks,
        generate_wiki_pages,
        index_wiki_pages,
    )
    from src.workers.document_parsing_tasks import chunk_parsed_content, parse_document_with_docling
    from src.workers.library_tasks import library_intake, library_validation

    steps = [
        library_intake.s(ctx),
        upload_to_seaweedfs.s(),
        parse_document_with_docling.s(),
        chunk_parsed_content.s(),
        embed_chunks.s(),
        library_validation.s(),
    ]
    if ctx.get("knowledge"):
        steps += [
            extract_facts_from_chunks.s(),
            generate_wiki_pages.s(),
            deduplicate_wiki_pages.s(),
            index_wiki_pages.s(),
        ]
    # retry=False: fail fast when RabbitMQ is down instead of blocking the HTTP request.
    return chain(*steps).apply_async(retry=False).id


def _unchanged_job(db: Session, project_id: str, filename: str, sha256: str) -> DocumentJob | None:
    """The latest completed job for exactly this content, if there is one."""
    return (
        db.query(DocumentJob)
        .join(DocumentFile, DocumentFile.job_id == DocumentJob.job_id)
        .filter(
            DocumentFile.project_id == project_id,
            DocumentFile.filename == filename,
            DocumentFile.sha256_hash == sha256,
            DocumentJob.status == "completed",
        )
        .order_by(DocumentJob.completed_at.desc())
        .first()
    )


def queue_document(
    db: Session,
    *,
    project_id: str,
    user_id: str,
    filename: str,
    local_path: Path,
    sha256: str,
    size_bytes: int,
    library: dict[str, Any] | None = None,
) -> DocumentJob:
    """Create the DocumentJob for a file saved under the workspace and queue the pipeline (unless unchanged).

    ``library`` carries the Library management upload form (owner, rights, taxonomy, target practice); the
    ``intake`` stage turns it into the practice and library job. Library uploads are never "unchanged": every
    upload is a new version that goes through review.
    """
    now = ist_now()
    job = DocumentJob(
        id=f"doc_{uuid.uuid4().hex[:12]}",
        job_id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=user_id,
        filename=filename,
        status="pending",
        file_sha256=sha256,
        file_size_bytes=size_bytes,
        created_at=now,
        updated_at=now,
    )
    previous = None if library is not None else _unchanged_job(db, project_id, filename, sha256)
    if previous is not None:
        job.status = "completed"
        job.parse_mode = "unchanged"
        job.chunk_count = previous.chunk_count
        job.completed_at = now
        job.error_message = f"Content unchanged since job {previous.job_id}; nothing to update"
        db.add(job)
        db.commit()
        logger.info("[PIPELINE] %s/%s unchanged (same as job %s)", project_id, filename, previous.job_id)
        return job

    db.add(job)
    db.commit()
    ctx = {
        "job_id": job.job_id,
        "project_id": project_id,
        "user_id": user_id,
        "filename": filename,
        "local_path": str(local_path.resolve()),
        "sha256": sha256,
        "knowledge": bool(settings.knowledge_building_enabled),
        "library": library,
    }
    try:
        start_pipeline(ctx)
    except Exception as e:
        db.refresh(job)
        if job.status == "pending":  # no stage ran, so the message never reached the broker
            job.status = "failed"
            job.failed_stage = "queue"
            job.error_message = f"Could not queue the ingestion pipeline (is RabbitMQ running?): {e}"[:1000]
            job.updated_at = ist_now()
            db.commit()
        logger.error("[PIPELINE] Queueing job %s failed: %s", job.job_id, e)
    else:
        logger.info("[PIPELINE] Queued job %s for %s", job.job_id, filename)
    return job


def queue_removal(project_id: str, filename: str) -> None:
    """Queue removal of a deleted file; if the broker is down, remove it in-process."""
    try:
        remove_document.apply_async(args=(project_id, filename), retry=False)
    except Exception as e:
        logger.warning("[PIPELINE] Could not queue removal of %s (%s); removing now", filename, e)
        remove_document.apply(args=(project_id, filename))
