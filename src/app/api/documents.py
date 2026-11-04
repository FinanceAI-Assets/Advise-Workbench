import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from src.app.api.documents_async import job_status
from src.core.auth import get_current_user, require_project_role
from src.memory.documents.source_chunks import build_chunks_from_text
from src.core.security.upload_validation import validate_document_upload
from src.core.db.models import DocumentJob, User
from src.workers.pipeline import queue_document, queue_removal
from src.core.db.session import get_db
from src.core.cache import cache_service
from src.core.observability.langfuse_tracing import langfuse_span
from src.core.storage import ensure_workspace, workspace_path

router = APIRouter()

logger = logging.getLogger(__name__)

_SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_project_id_param(project_id: str) -> None:
    if not project_id or not _SAFE_PROJECT_ID.match(project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")


def _normalize_upload_filename(name: str | None) -> str:
    raw = name or "upload.bin"
    if "\x00" in raw or "/" in raw or "\\" in raw:
        raise HTTPException(status_code=400, detail="Invalid filename")
    p = Path(raw)
    if ".." in p.parts or p.is_absolute():
        raise HTTPException(status_code=400, detail="Invalid filename")
    base = p.name
    if not base or base in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return base


async def _extract_text_from_bytes(filename: str, content: bytes, timeout_sec: int = 30) -> tuple[str, str]:
    """Extract text via the canonical wiki_ingest parser (python-docx, sheet markers, etc.)."""
    from src.memory.knowledge.wiki_ingest import _extract_text_from_file

    lower = (filename or "").lower()
    parse_mode = "wiki_ingest"
    if lower.endswith(".pdf"):
        parse_mode = "wiki_ingest_pdf"
    elif lower.endswith((".xlsx", ".xls")):
        parse_mode = "wiki_ingest_xlsx"
    elif lower.endswith(".docx"):
        parse_mode = "wiki_ingest_docx"
    elif lower.endswith(".pptx"):
        parse_mode = "wiki_ingest_pptx"

    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(_extract_text_from_file, filename, content),
            timeout=timeout_sec,
        )
        return str(text or ""), parse_mode
    except TimeoutError:
        logger.warning("document text extraction timed out for %s", filename)
        return f"[Extraction timeout for {filename}]", "timeout_fallback"
    except Exception:
        logger.warning("document text extraction failed for %s", filename, exc_info=True)
        return f"[Unable to extract {filename}]", "error_fallback"


@router.post("/upload")
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
) -> dict:
    """Upload and parse a document.

    Timeout: 60 seconds for file reading + parsing.
    Supports: txt, md, csv, json, pdf, docx, pptx, xlsx, xls
    """
    _validate_project_id_param(project_id)
    require_project_role(project_id, {"Owner", "Editor"}, user, db)
    ensure_workspace(project_id)

    try:
        # Read file with timeout (30 sec for up to 100MB)
        content = await asyncio.wait_for(file.read(), timeout=30.0)
    except TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="File upload timeout. File may be too large or network too slow. Try smaller file (< 50MB)."
        ) from None

    safe_name = _normalize_upload_filename(file.filename)
    validate_document_upload(safe_name, content)
    if safe_name.lower().endswith(".pdf"):
        from src.core.config import settings
        from pypdf import PdfReader
        import io as _io

        try:
            page_count = len(PdfReader(_io.BytesIO(content)).pages)
        except Exception:
            logger.warning("could not read PDF page count for %s; skipping page-limit check", safe_name, exc_info=True)
            page_count = 0
        max_pages = int(getattr(settings, "pdf_max_pages", 200))
        if page_count > max_pages:
            raise HTTPException(
                status_code=400,
                detail=f"PDF has {page_count} pages; maximum allowed is {max_pages}",
            )
    digest = hashlib.sha256(content).hexdigest()

    cached = cache_service.get(f"parse:{digest}")
    text, parse_mode = None, None

    if cached and isinstance(cached.get("chunks"), list):
        text = cached.get("text", "")
        parse_mode = cached.get("parse_mode", "cached")
        raw_chunks = cached.get("chunks", [])
        if raw_chunks and isinstance(raw_chunks[0], str):
            chunks = build_chunks_from_text(text or "", doc_id=digest, filename=safe_name)
        else:
            chunks = raw_chunks
    else:
        try:
            # Extract text with 30-second timeout
            text, parse_mode = await asyncio.wait_for(
                _extract_text_from_bytes(safe_name, content, timeout_sec=30),
                timeout=35.0  # Slightly longer than internal timeout for margin
            )
        except TimeoutError:
            # Fall back to basic decode on timeout
            logger.warning("document parse timed out for %s in project %s", safe_name, project_id)
            text = content.decode("utf-8", errors="ignore")
            parse_mode = "timeout_fallback"

        langfuse_span(
            trace_id=project_id,
            name="document.upload",
            input_payload={"filename": safe_name, "bytes": len(content)},
            output_payload={"parse_mode": parse_mode, "text_len": len(text or "")},
            status_message=parse_mode if (parse_mode or "").endswith("fallback") else None,
        )

        chunks = build_chunks_from_text(
            text or "",
            doc_id=digest,
            filename=safe_name,
        )
        cached = {
            "status": "chunked",
            "chars": len(text),
            "chunk_count": len(chunks),
            "chunks": chunks,
            "text": text,
            "parse_mode": parse_mode,
        }
        cache_service.set(f"parse:{digest}", cached, ttl_seconds=3600)

    target = workspace_path(project_id) / "source_docs" / safe_name
    target.write_bytes(content)

    parsed_path = workspace_path(project_id) / "parsed_docs" / f"{digest}.json"
    parsed_payload = {
        "sha256": digest,
        "filename": safe_name,
        "chars": len(text or ""),
        "parse_mode": parse_mode,
        "text": text or "",
        "chunks": chunks,
    }
    parsed_path.write_text(json.dumps(parsed_payload, indent=2), encoding="utf-8")
    logger.info("[UPLOAD] project=%s file=%s %d bytes sha256=%s by user=%s; saved to the engagement workspace",
                project_id, safe_name, len(content), digest[:12], user.id)

    # Sheldon's answers search the ingestion pipeline's copy (SeaweedFS -> Docling -> chunks -> Qdrant), built by the
    # workers in the background; the document is searchable once ``ingestion.status`` is "completed".
    job = await asyncio.to_thread(
        queue_document, db, project_id=project_id, user_id=user.id, filename=safe_name, content=content,
        sha256=digest, size_bytes=len(content),
    )
    if job.status == "failed":
        logger.warning("[UPLOAD] project=%s file=%s not queued (job=%s): %s", project_id, safe_name, job.job_id,
                       job.error_message)
    else:
        logger.info("[UPLOAD] project=%s file=%s ingestion job=%s status=%s%s", project_id, safe_name, job.job_id,
                    job.status, " (content unchanged, already searchable)" if job.parse_mode == "unchanged" else "")

    return {
        "filename": safe_name,
        "sha256": digest,
        "parse": {
            "status": cached.get("status"),
            "chars": cached.get("chars"),
            "chunk_count": len(chunks),
            "mode": parse_mode
        },
        "path": str(target),
        "parsed_path": str(parsed_path),
        "ingestion": _ingestion(db, job),
    }


def _ingestion(db: Session, job: DocumentJob | None) -> dict | None:
    """The pipeline status of a document's latest job, as the upload, list and status endpoints return it."""
    if job is None:
        return None
    db.refresh(job)  # the workers update the job in their own sessions
    s = job_status(db, job)
    stage = s.stages[s.current_stage_index] if 0 <= s.current_stage_index < len(s.stages) else None
    return {
        "job_id": s.job_id,
        "status": s.status,
        "searchable": s.status == "completed",
        "is_terminal": s.is_terminal,
        "stage": stage,
        "stages": s.stages,
        "progress_percent": s.progress_percent,
        "chunk_count": s.counts.chunks,
        "failed_stage": s.failed_stage,
        "error": s.error_message if s.status == "failed" else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _latest_jobs(db: Session, project_id: str) -> dict[str, DocumentJob]:
    latest: dict[str, DocumentJob] = {}
    for job in db.query(DocumentJob).filter(DocumentJob.project_id == project_id).order_by(DocumentJob.created_at.desc()):
        latest.setdefault(job.filename, job)
    return latest


@router.get("/list")
def list_documents(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _validate_project_id_param(project_id)
    require_project_role(project_id, {"Owner", "Editor", "Viewer"}, user, db)
    ensure_workspace(project_id)
    docs = [d for d in sorted((workspace_path(project_id) / "source_docs").glob("*")) if d.is_file()]
    latest = _latest_jobs(db, project_id)
    return {
        "items": [str(d) for d in docs],
        "documents": [{"filename": d.name, "path": str(d), "ingestion": _ingestion(db, latest.get(d.name))} for d in docs],
    }


@router.get("/status/{job_id}")
def document_status(job_id: str, project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Poll one document's processing: stage, progress, chunk count, failure reason."""
    _validate_project_id_param(project_id)
    require_project_role(project_id, {"Owner", "Editor", "Viewer"}, user, db)
    job = db.query(DocumentJob).filter(DocumentJob.job_id == job_id, DocumentJob.project_id == project_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"filename": job.filename, "ingestion": _ingestion(db, job)}


@router.post("/reindex")
async def reindex_documents(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Queue every document of the engagement on the ingestion pipeline: documents uploaded before it existed, or
    after a failure. A document whose content is already processed completes at once."""
    _validate_project_id_param(project_id)
    require_project_role(project_id, {"Owner", "Editor"}, user, db)
    ensure_workspace(project_id)
    queued = []
    for path in sorted((workspace_path(project_id) / "source_docs").glob("*")):
        if not path.is_file():
            continue
        content = path.read_bytes()
        job = await asyncio.to_thread(
            queue_document, db, project_id=project_id, user_id=user.id, filename=path.name, content=content,
            sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
        )
        queued.append({"filename": path.name, "ingestion": _ingestion(db, job)})
    logger.info("[UPLOAD] project=%s reindex: %d document(s) queued: %s", project_id, len(queued),
                ", ".join(f"{d['filename']}={d['ingestion']['status']}" for d in queued) or "-")
    return {"documents": queued}


@router.delete("/delete")
def delete_document(
    project_id: str,
    filename: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _validate_project_id_param(project_id)
    require_project_role(project_id, {"Owner", "Editor"}, user, db)
    ensure_workspace(project_id)
    source_dir = workspace_path(project_id) / "source_docs"
    safe_fn = _normalize_upload_filename(filename)
    target = source_dir / safe_fn
    try:
        resolved_target = target.resolve()
        resolved_source = source_dir.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found") from None
    if resolved_source not in resolved_target.parents:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not resolved_target.exists() or not resolved_target.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    # Best effort cleanup of parsed chunk file via content hash.
    content = resolved_target.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    parsed_path = workspace_path(project_id) / "parsed_docs" / f"{digest}.json"
    resolved_target.unlink(missing_ok=True)
    parsed_path.unlink(missing_ok=True)
    queue_removal(project_id, safe_fn)  # the pipeline's copy: S3 object, chunks and vectors
    logger.info("[UPLOAD] project=%s file=%s deleted from the workspace; removal from SeaweedFS, Postgres and Qdrant "
                "queued", project_id, safe_fn)
    return {"deleted": True, "filename": safe_fn}
