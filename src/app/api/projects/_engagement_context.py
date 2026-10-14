"""What the engagement record already says, for the conversation with Sheldon.

An engagement's brief is captured when it is created (client, objective, scope,
success measures). The conversation uses it two ways: as discovery answers, so
Sheldon does not ask for details the user has already entered, and as context
text, so replies and plans are grounded in the brief.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.models import EngagementMeta, Project


def _load(db: Session, project_id: str) -> tuple[Project | None, EngagementMeta | None]:
    project = db.scalar(select(Project).where(Project.id == project_id))
    meta = db.scalar(select(EngagementMeta).where(EngagementMeta.project_id == project_id))
    return project, meta


def engagement_discovery(db: Session, project_id: str) -> dict:
    """Discovery slots (client, outcome, win themes) taken from the engagement brief.

    Only fields the user filled in are returned, so anything missing is still asked for.
    Answers given in the conversation are merged over these and take precedence.
    """
    _, meta = _load(db, project_id)
    if meta is None:
        return {}
    slots: dict[str, object] = {}
    client = (meta.client_org or "").strip()
    if client:
        slots["client"] = {"name": client}
    outcome = (meta.sponsor_objective or "").strip() or (meta.brief or "").strip()
    if outcome:
        slots["outcome"] = {"primary": outcome}
    themes = [t.strip() for t in re.split(r"[·;,\n]", meta.success_measures or "") if t.strip()]
    if themes:
        slots["win_themes"] = themes[:3]
    return slots


def engagement_brief_text(db: Session, project_id: str) -> str:
    """The engagement brief as a context block for the model. Empty when there is no brief."""
    project, meta = _load(db, project_id)
    if project is None or meta is None:
        return ""
    fields = [
        ("Engagement", f"{project.name} ({meta.code})" if meta.code else project.name),
        ("Client", meta.client_org),
        ("Type", meta.type),
        ("Brief", meta.brief),
        ("Sponsor objective", meta.sponsor_objective),
        ("Scope", meta.scope),
        ("Success measures", meta.success_measures),
        ("Timeline", f"{meta.start_date} to {meta.target_close}" if meta.start_date and meta.target_close else None),
        ("Classification", meta.classification),
    ]
    lines = [f"{label}: {str(value).strip()}" for label, value in fields if value and str(value).strip()]
    if len(lines) <= 1:
        return ""
    return "[EngagementBrief]\n" + "\n".join(lines)
