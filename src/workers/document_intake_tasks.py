"""Pipeline stage 1: record the uploaded file, already stored in SeaweedFS (S3) by the API, in document_files."""

from __future__ import annotations

import logging
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


@app.task(base=IngestionTask, stage="uploading")
def upload_to_seaweedfs(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, project_id, filename, key = ctx["job_id"], ctx["project_id"], ctx["filename"], ctx["s3_key"]

    with session_scope() as db:
        update_job(db, job_id, status="uploading", error_message=None)
        stored = get_seaweedfs_client().head_file(key)
        if stored is None:
            raise PermanentIngestionError(f"Uploaded file is missing in S3: {key}")

        doc_file = db.query(DocumentFile).filter(DocumentFile.job_id == job_id).first()
        if doc_file is None:
            doc_file = DocumentFile(id=f"docfile_{uuid.uuid4().hex[:16]}", project_id=project_id, job_id=job_id)
            db.add(doc_file)
        doc_file.filename = ctx.get("doc_key") or filename
        doc_file.file_format = Path(filename).suffix.lstrip(".").lower()[:20] or None
        doc_file.file_size_bytes = stored["size"]
        doc_file.sha256_hash = ctx["sha256"]
        doc_file.seaweedfs_file_id = key
        doc_file.upload_source = "api_upload"
        db.commit()
        logger.info("[INTAKE] job=%s recorded s3://%s/%s as %s", job_id, settings.s3_bucket, key, doc_file.id)
        return {**ctx, "document_file_id": doc_file.id, "s3_bucket": settings.s3_bucket}
