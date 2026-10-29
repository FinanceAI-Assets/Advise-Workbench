"""Library management stages of the ingestion pipeline.

intake (first): checks the staged source, rejects duplicates, creates/attaches the practice and its library job.
library_validation (after embedding): the Library's quality checks on the pipeline's own chunks, so review,
approval and publishing read the same passages that search uses.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.db.models import ParsedDocument
from src.core.db.session import session_scope
from src.workers.celery_app import app
from src.workers.pipeline import IngestionTask, complete_job, update_job

logger = logging.getLogger(__name__)


@app.task(base=IngestionTask, stage="intake")
def library_intake(ctx: dict[str, Any]) -> dict[str, Any]:
    from src.app.api.admin_library import intake_source

    with session_scope() as db:
        update_job(db, ctx["job_id"], status="intake")
        result = intake_source(db, ctx)
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
