"""Library ingestion monitoring API (admin console → Library management).

Mounted at /api/admin/library/documents; administrators only. Sources enter through Upload sources
(POST /api/admin/library/uploads); these routes follow the pipeline jobs and show what each store holds.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.auth import require_admin
from src.core.config import settings
from src.core.db.models import (
    ChunkArchive,
    ChunkEmbedding,
    DocumentChunkLink,
    DocumentFile,
    DocumentJob,
    ExtractedFact,
    ParsedDocument,
    User,
    WikiPageFinal,
)
from src.core.db.session import get_db
from src.core.storage.seaweedfs_client import get_seaweedfs_client
from src.core.vector_db.qdrant_client import get_qdrant_client
from src.workers.pipeline import KNOWLEDGE_STAGES, LIBRARY_SCOPE, SEARCH_STAGES, TERMINAL_STATUSES

router = APIRouter()
logger = logging.getLogger(__name__)


class JobCounts(BaseModel):
    chunks: int = 0
    embeddings: int = 0
    facts: int = 0
    wiki_pages: int = 0


class JobStatus(BaseModel):
    job_id: str
    status: str
    is_terminal: bool
    practice_id: Optional[str] = None  # set for sources uploaded through Library management (Upload sources)
    filename: str
    stages: list[str]
    current_stage_index: int  # -1 before the first stage; len(stages) when completed
    progress_percent: int
    document_file_id: Optional[str] = None
    counts: JobCounts
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    file_size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    parse_mode: Optional[str] = None
    text_length: Optional[int] = None
    failed_stage: Optional[str] = None
    error_message: Optional[str] = None


def _stages() -> list[str]:
    return SEARCH_STAGES + (KNOWLEDGE_STAGES if settings.knowledge_building_enabled else [])


def _wiki_pages_for(db: Session, document_file_id: str) -> list[WikiPageFinal]:
    pages = db.query(WikiPageFinal).filter(WikiPageFinal.project_id == LIBRARY_SCOPE).all()
    return [p for p in pages if document_file_id in (p.merge_info or {}).get("source_documents", [])]


def practice_document_key(practice_id: str, filename: str) -> str:
    """Pipeline document key of a practice source: versions of one practice replace each other in search."""
    return f"{practice_id}/{filename}"


def split_document_key(key: str) -> tuple[Optional[str], str]:
    """``<practice>/<JOB-n>/<file>`` -> (practice, file); a key without a practice is just the file name."""
    parts = key.split("/")
    return (parts[0], parts[-1]) if len(parts) > 1 else (None, key)


def ingestion_status(db: Session, job_id: str | None) -> dict[str, Any] | None:
    """JSON-ready pipeline status of one library ingestion job (None when there is no such job)."""
    if not job_id:
        return None
    job = db.query(DocumentJob).filter(DocumentJob.job_id == job_id, DocumentJob.project_id == LIBRARY_SCOPE).first()
    return _job_status(db, job).model_dump(mode="json") if job else None


def _job_status(db: Session, job: DocumentJob) -> JobStatus:
    stages = _stages()
    doc = db.query(DocumentFile).filter(DocumentFile.job_id == job.job_id).first()
    counts = JobCounts(chunks=job.chunk_count or 0)
    if doc is not None:
        parsed_ids = [p for (p,) in db.query(ParsedDocument.id).filter(ParsedDocument.document_file_id == doc.id)]
        links = db.query(DocumentChunkLink).filter(DocumentChunkLink.document_file_id == doc.id)
        counts.chunks = links.count()
        counts.embeddings = links.join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunkLink.chunk_id).count()
        if parsed_ids:
            counts.facts = db.query(ExtractedFact).filter(ExtractedFact.parsed_document_id.in_(parsed_ids)).count()
        counts.wiki_pages = len(_wiki_pages_for(db, doc.id))
    if job.status == "completed":
        index = len(stages)
    elif job.status in stages:
        index = stages.index(job.status)
    elif job.failed_stage in stages:
        index = stages.index(job.failed_stage)
    else:
        index = -1
    progress = 100 if job.status == "completed" else max(0, int(100 * max(index, 0) / max(len(stages), 1)))
    practice_id, filename = split_document_key(job.filename)
    return JobStatus(
        job_id=job.job_id,
        status=job.status,
        is_terminal=job.status in TERMINAL_STATUSES,
        practice_id=practice_id,
        filename=filename,
        stages=stages,
        current_stage_index=index,
        progress_percent=progress,
        document_file_id=doc.id if doc else None,
        counts=counts,
        chunk_count=job.chunk_count or 0,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        file_size_bytes=job.file_size_bytes,
        sha256=job.file_sha256,
        parse_mode=job.parse_mode,
        text_length=len(job.text_content) if job.text_content else None,
        failed_stage=job.failed_stage,
        error_message=job.error_message,
    )


def _job_for(job_id: str, db: Session) -> DocumentJob:
    job = (
        db.query(DocumentJob)
        .filter(DocumentJob.job_id == job_id, DocumentJob.project_id == LIBRARY_SCOPE)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.get("/status/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> JobStatus:
    """Poll one ingestion job: stage, progress, counts, failure details."""
    return _job_status(db, _job_for(job_id, db))


@router.get("/jobs", response_model=list[JobStatus])
def list_jobs(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[JobStatus]:
    """Latest ingestion job of every library document (newest first)."""
    latest: dict[str, DocumentJob] = {}
    for job in (
        db.query(DocumentJob).filter(DocumentJob.project_id == LIBRARY_SCOPE).order_by(DocumentJob.created_at.desc())
    ):
        latest.setdefault(job.filename, job)
    return [_job_status(db, j) for j in latest.values() if j.status != "deleted"]


@router.get("/wiki")
def list_wiki_pages(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Wiki pages the pipeline built from library documents (deduplicated across documents)."""
    pages = (
        db.query(WikiPageFinal)
        .filter(WikiPageFinal.project_id == LIBRARY_SCOPE)
        .order_by(WikiPageFinal.updated_at.desc())
        .all()
    )
    names = {d.id: d.filename for d in db.query(DocumentFile).filter(DocumentFile.project_id == LIBRARY_SCOPE)}
    return [
        {
            "id": p.id,
            "entity_name": p.entity_name,
            "entity_type": p.entity_type,
            "content": p.content,
            "aliases": p.aliases or [],
            "source_documents": [names.get(d, d) for d in (p.merge_info or {}).get("source_documents", [])],
            "merge_count": (p.merge_info or {}).get("merge_count", 0),
            "is_published": bool(p.is_published),
            "updated_at": p.updated_at,
        }
        for p in pages
    ]


@router.get("/{job_id}/details")
def get_job_details(
    job_id: str,
    chunk_limit: int = Query(20, ge=0, le=200),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """What the pipeline stored for this job in SeaweedFS (S3), Postgres and Qdrant."""
    job = _job_for(job_id, db)
    status = _job_status(db, job).model_dump()
    doc_file = db.query(DocumentFile).filter(DocumentFile.job_id == job.job_id).first()
    if doc_file is None:
        return {"job": status, "seaweedfs": None, "postgres": None, "qdrant": None, "knowledge": None}

    seaweedfs: dict[str, Any] = {"bucket": settings.s3_bucket, "key": doc_file.seaweedfs_file_id}
    try:
        seaweedfs["object"] = get_seaweedfs_client().head_file(doc_file.seaweedfs_file_id)
    except Exception as e:
        seaweedfs["error"] = str(e)

    parsed = db.query(ParsedDocument).filter(ParsedDocument.document_file_id == doc_file.id).first()
    chunks_q = (
        db.query(DocumentChunkLink, ChunkArchive)
        .join(ChunkArchive, ChunkArchive.id == DocumentChunkLink.chunk_id)
        .filter(DocumentChunkLink.document_file_id == doc_file.id)
    )
    postgres = {
        "document_file_id": doc_file.id,
        "parsed_document_id": parsed.id if parsed else None,
        "page_count": parsed.page_count if parsed else None,
        "table_count": parsed.table_count if parsed else None,
        "text_length": len(parsed.full_text or "") if parsed else None,
        "chunk_count": chunks_q.count(),
        "reused_chunk_count": chunks_q.filter(DocumentChunkLink.reused.is_(True)).count(),
        "chunks": [
            {
                "id": c.id,
                "chunk_number": link.chunk_number,
                "page_number": link.page_number,
                "source_type": c.source_type,
                "characters": c.character_count,
                "reused": link.reused,
                "preview": c.text[:200],
            }
            for link, c in chunks_q.order_by(DocumentChunkLink.chunk_number).limit(chunk_limit).all()
        ],
    }

    qdrant: dict[str, Any] = {}
    try:
        store = get_qdrant_client()
        qdrant = {
            "collection": store.collection_name,
            "points_for_document": store.count(document_id=doc_file.id),
            "sample": store.scroll(limit=3, document_id=doc_file.id),
        }
        wiki_store = get_qdrant_client(settings.qdrant_wiki_collection)
        qdrant["wiki_collection"] = wiki_store.collection_name
        qdrant["wiki_points_in_project"] = wiki_store.count(project_id=LIBRARY_SCOPE)
    except Exception as e:
        qdrant["error"] = str(e)

    facts = db.query(ExtractedFact).filter(ExtractedFact.parsed_document_id == parsed.id).all() if parsed else []
    knowledge = {
        "fact_count": len(facts),
        "facts": [
            {"type": f.fact_type, "name": f.fact_name, "confidence": f.confidence_score, "context": f.source_context}
            for f in facts[:30]
        ],
        "wiki_pages": [
            {
                "id": p.id,
                "entity_name": p.entity_name,
                "entity_type": p.entity_type,
                "merge_count": (p.merge_info or {}).get("merge_count", 0),
                "is_published": bool(p.is_published),
                "content": p.content,
            }
            for p in _wiki_pages_for(db, doc_file.id)
        ],
    }
    return {"job": status, "seaweedfs": seaweedfs, "postgres": postgres, "qdrant": qdrant, "knowledge": knowledge}
