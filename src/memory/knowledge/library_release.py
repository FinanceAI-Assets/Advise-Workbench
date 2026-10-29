"""Which ingested Library content users may retrieve: the released version of each Approved practice.

The ingestion pipeline indexes every uploaded version (so reviewers can inspect candidates); user-facing search
(Leading Practice search/Ask, /api/query) only serves the version that was published.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.models import DocumentFile, LpPractice, WorkbenchRecord

JOBS = "ingestion_jobs"
CHUNKS = "library_chunks"


def _number(value: str) -> int:
    match = re.search(r"(\d+)$", value or "")
    return int(match.group(1)) if match else 0


def released_jobs(db: Session) -> dict[str, dict[str, Any]]:
    """practice id -> latest released library job payload (with ``id``), for Approved practices only."""
    approved = set(db.scalars(select(LpPractice.id).where(LpPractice.status == "Approved")).all())
    latest: dict[str, dict[str, Any]] = {}
    for row in db.scalars(select(WorkbenchRecord).where(WorkbenchRecord.collection == JOBS)).all():
        payload = json.loads(row.payload_json or "{}")
        practice_id = payload.get("practiceId")
        if not practice_id or practice_id not in approved or not payload.get("release"):
            continue
        current = latest.get(practice_id)
        if current is None or _number(row.record_id) > _number(current["id"]):
            latest[practice_id] = {"id": row.record_id, **payload}
    return latest


def released_document_ids(db: Session) -> set[str]:
    """document_files ids of the released versions (what users may retrieve from Qdrant)."""
    ingestion_ids = [j["ingestionJobId"] for j in released_jobs(db).values() if j.get("ingestionJobId")]
    if not ingestion_ids:
        return set()
    return {d for (d,) in db.query(DocumentFile.id).filter(DocumentFile.job_id.in_(ingestion_ids))}


def published_passages(db: Session) -> list[dict[str, Any]]:
    """Passages of every released practice, from the pipeline's chunks (no re-chunking).

    ``job_id`` is set when the release went through the ingestion pipeline, so its vectors live in Qdrant;
    releases from before the pipeline have no ``job_id`` and are embedded locally by the caller.
    """
    passages: list[dict[str, Any]] = []
    for practice_id, job in released_jobs(db).items():
        row = db.scalar(
            select(WorkbenchRecord).where(WorkbenchRecord.collection == CHUNKS, WorkbenchRecord.record_id == job["id"])
        )
        stored = json.loads(row.payload_json or "{}") if row is not None else {}
        for chunk in stored.get("chunks", []):
            section = re.sub(r"^§\d+(?:\.\d+)*\s*", "", str(chunk.get("section") or "")).strip()
            passages.append(
                {
                    "id": chunk.get("chunkId") or f"{job['id']}-{chunk.get('code', '')}",
                    "path": f"published/{practice_id}",
                    "heading": f"{job.get('title', practice_id)} · {section}"[:120] if section else job.get("title", "")[:120],
                    "text": chunk.get("text", ""),
                    "source": "published",
                    "practice_id": practice_id,
                    "job_id": job.get("ingestionJobId"),
                }
            )
    return passages
