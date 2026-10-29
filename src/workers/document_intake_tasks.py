"""Pipeline stage 1: store the uploaded file in SeaweedFS (S3) and record it in document_files."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.db.models import DocumentFile
from src.core.db.session import session_scope
from src.core.storage.seaweedfs_client import get_seaweedfs_client
from src.workers.celery_app import app
from src.workers.pipeline import IngestionTask, PermanentIngestionError, update_job

logger = logging.getLogger(__name__)


def s3_key_for(project_id: str, job_id: str, filename: str) -> str:
    return f"{settings.s3_intake_prefix.strip('/')}/{project_id}/{job_id}/{filename}"


@app.task(base=IngestionTask, stage="uploading")
def upload_to_seaweedfs(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, project_id, filename = ctx["job_id"], ctx["project_id"], ctx["filename"]
    path = Path(ctx["local_path"])
    if not path.is_file():
        raise PermanentIngestionError(f"Uploaded file is missing on disk: {path}")

    with session_scope() as db:
        update_job(db, job_id, status="uploading", error_message=None)
        data = path.read_bytes()
        if ctx.get("sha256") and hashlib.sha256(data).hexdigest() != ctx["sha256"]:
            raise PermanentIngestionError(
                f"{filename} was replaced by a newer upload before this job started; the newer job processes it"
            )
        key = s3_key_for(project_id, job_id, filename)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        stored = get_seaweedfs_client().upload_file(key, data, content_type)

        doc_file = db.query(DocumentFile).filter(DocumentFile.job_id == job_id).first()
        if doc_file is None:
            doc_file = DocumentFile(id=f"docfile_{uuid.uuid4().hex[:16]}", project_id=project_id, job_id=job_id)
            db.add(doc_file)
        doc_file.filename = ctx.get("doc_key") or filename
        doc_file.file_format = path.suffix.lstrip(".").lower()[:20] or None
        doc_file.file_size_bytes = stored["size"]
        doc_file.sha256_hash = stored["sha256"]
        doc_file.seaweedfs_file_id = key
        doc_file.upload_source = "api_upload"
        db.commit()
        logger.info("[INTAKE] job=%s stored s3://%s/%s as %s", job_id, stored["bucket"], key, doc_file.id)
        return {**ctx, "document_file_id": doc_file.id, "s3_bucket": stored["bucket"], "s3_key": key}
