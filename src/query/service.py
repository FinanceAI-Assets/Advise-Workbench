"""The query pipeline's one entry point: access check, then ``answer_question``.

Used by ``POST /api/query``, Sheldon's rag_agent (engagement Conversation) and Talk to data (Leading Practice
Library), so every caller gets the same answers, citations and "insufficient evidence" behaviour.

Access: the Leading Practice Library (released content) is readable by every signed-in user; an engagement's
documents only by its members (Owner, Editor or Viewer). Engagement uploads are searchable once the ingestion pipeline
has processed them; the ones still in progress are listed in ``retrieval["pending_documents"]``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.models import DocumentJob, Membership
from src.memory.knowledge.library_release import LIBRARY_SCOPE
from src.query.pipeline import QueryResult, QueryScope, answer_question, source_detail

ENGAGEMENT_ROLES = {"Owner", "Editor", "Viewer"}
_DONE = {"completed", "failed", "deleted"}  # ingestion job statuses that are final (src.workers.pipeline.TERMINAL_STATUSES)


class AccessDenied(Exception):
    """The user is not a member of the engagement."""


def can_read_engagement(db: Session, user_id: str, engagement_id: str) -> bool:
    role = db.scalar(select(Membership.role).where(Membership.project_id == engagement_id, Membership.user_id == user_id))
    return role in ENGAGEMENT_ROLES


def scope_for(*, engagement_id: str | None = None, include_library: bool = True, practice_ids: list[str] | None = None) -> QueryScope:
    return QueryScope(
        index=LIBRARY_SCOPE if include_library else None,
        engagement_id=engagement_id or None,
        practice_ids=tuple(dict.fromkeys(practice_ids or [])),
    )


def ask(
    db: Session,
    user_id: str,
    question: str,
    scope: QueryScope,
    *,
    history: list[dict[str, str]] | None = None,
    top_k: int | None = None,
) -> QueryResult:
    """Answer ``question`` from ``scope`` for ``user_id``. Raises ``AccessDenied`` for an engagement the user
    cannot read, and lets search outages (embedding service, Qdrant) propagate."""
    if scope.engagement_id and not can_read_engagement(db, user_id, scope.engagement_id):
        raise AccessDenied(scope.engagement_id)
    result = answer_question(db, scope, question, history or [], top_k)
    if scope.engagement_id:
        result.retrieval["pending_documents"] = pending_documents(db, scope.engagement_id)
    return result


def pending_documents(db: Session, engagement_id: str) -> list[str]:
    """Uploads of the engagement the ingestion pipeline is still processing (not searchable yet)."""
    latest: dict[str, str] = {}
    rows = db.query(DocumentJob.filename, DocumentJob.status).filter(DocumentJob.project_id == engagement_id)
    for filename, status in rows.order_by(DocumentJob.created_at.desc()):
        latest.setdefault(filename, status)
    return sorted(name for name, status in latest.items() if status not in _DONE)


def source(db: Session, user_id: str, kind: str, key: str, *, engagement_id: str | None = None) -> dict | None:
    """A cited source in full; None when it is gone or the user may not see it."""
    if engagement_id and not can_read_engagement(db, user_id, engagement_id):
        return None
    return source_detail(db, kind, key, engagement_id=engagement_id)
