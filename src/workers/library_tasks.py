"""Library management stages of the ingestion pipeline.

intake (first): checks the source the API stored in S3, rejects duplicates, creates/attaches the practice and its library job.
library_validation (after embedding): the Library's quality checks on the pipeline's own chunks, so review,
approval and publishing read the same passages that search uses.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.db.models import ParsedDocument
from src.core.db.session import session_scope
from src.workers.celery_app import app
from src.workers.pipeline import IngestionTask, PermanentIngestionError, complete_job, update_job

logger = logging.getLogger(__name__)


@app.task(base=IngestionTask, stage="intake")
def library_intake(ctx: dict[str, Any]) -> dict[str, Any]:
    from src.app.api.admin_library import intake_source
    from src.core.storage.seaweedfs_client import get_seaweedfs_client

    with session_scope() as db:
        update_job(db, ctx["job_id"], status="intake")
        try:
            result = intake_source(db, ctx)
        except PermanentIngestionError:
            # Rejected source: nothing will ever read the stored upload. Transient errors keep it for the retry.
            try:
                get_seaweedfs_client().delete_file(ctx["s3_key"])
            except Exception:
                logger.warning("[INTAKE] job=%s could not remove rejected upload %s", ctx["job_id"], ctx["s3_key"])
            raise
        update_job(db, ctx["job_id"], filename=result["doc_key"])
    logger.info("[INTAKE] job=%s -> %s %s", ctx["job_id"], result["practice_id"], result["library_job_id"])
    return {**ctx, **result}


@app.task(base=IngestionTask, stage="library_validation")
def library_validation(ctx: dict[str, Any]) -> dict[str, Any]:
    from src.app.api.admin_library import complete_validation

    with session_scope() as db:
        update_job(db, ctx["job_id"], status="library_validation")
        parsed = db.get(ParsedDocument, ctx["parsed_document_id"])
        stored = (parsed.content_json or {}).get("library") or {} if parsed else {}
        outcome = complete_validation(db, ctx, stored.get("blocks", []), stored.get("chunks", []), stored.get("pages", 0))
        if not ctx.get("knowledge"):
            complete_job(db, ctx, outcome)
    logger.info("[VALIDATE] job=%s %s", ctx["job_id"], outcome)
    return {**ctx, "library_outcome": outcome}
