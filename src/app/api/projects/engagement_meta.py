"""Additive engagement metadata + cross-project stats, layered on top of Project/Membership.

New routes only — no existing route, model, or orchestration logic is touched.
Mirrors the ProjectBrand-style side table pattern already used for project
branding, and reuses the exact auth helpers (`get_current_user`,
`require_project_role`) and query conventions used throughout
`src/app/api/projects/crud.py`.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.api.projects._router import router
from src.core.auth import get_current_user, require_project_role
from src.core.db.models import EngagementMeta, Membership, Project, Run, User, utcnow
from src.core.db.session import get_db

# Defaults returned when a project has no engagement_meta row yet, so every
# Project can be treated as a valid "Engagement" row without requiring a
# human to hand-seed metadata first.
_DEFAULT_STAGE = "Brief"
_DEFAULT_PROGRESS = 0


class UpdateEngagementMetaRequest(BaseModel):
    code: str | None = None
    type: str | None = None
    stage: str | None = None
    progress: int | None = None
    next_task: str | None = None
    due_date: str | None = None


def _engagement_meta_response(pid: str, row: EngagementMeta | None) -> dict:
    return {
        "project_id": pid,
        "code": (row.code if row else None) or pid.upper(),
        "type": (row.type if row else None) or "Advisory engagement",
        "stage": (row.stage if row else None) or _DEFAULT_STAGE,
        "progress": row.progress if row and row.progress is not None else _DEFAULT_PROGRESS,
        "next_task": (row.next_task if row else None) or "",
        "due_date": (row.due_date if row else None) or "",
    }


@router.get("/{pid}/engagement-meta")
def get_engagement_meta(
    pid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_project_role(pid, {"Owner", "Editor", "Viewer"}, user, db)
    row = db.scalar(select(EngagementMeta).where(EngagementMeta.project_id == pid))
    return _engagement_meta_response(pid, row)


@router.put("/{pid}/engagement-meta")
def update_engagement_meta(
    pid: str,
    body: UpdateEngagementMetaRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_project_role(pid, {"Owner", "Editor"}, user, db)
    row = db.scalar(select(EngagementMeta).where(EngagementMeta.project_id == pid))
    if row is None:
        row = EngagementMeta(id=f"em_{uuid.uuid4().hex[:10]}", project_id=pid)
        db.add(row)
    for field in ("code", "type", "stage", "progress", "next_task", "due_date"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, value)
    row.updated_at = utcnow()
    db.commit()
    return _engagement_meta_response(pid, row)


@router.get("/{pid}/members")
def list_project_members(
    pid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_project_role(pid, {"Owner", "Editor", "Viewer"}, user, db)
    rows = db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.project_id == pid)
    ).all()
    items = [
        {
            "id": membership.id,
            "name": member.email.split("@")[0],
            "roleAndAccess": membership.role,
        }
        for membership, member in rows
    ]
    return {"items": items}


@router.get("/engagements/stats")
def get_engagement_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate the 4 Engagements-list stat cards across the user's own projects.

    Pure additive read: joins Project/Membership (unchanged) with the new
    EngagementMeta side table. No existing endpoint's behavior changes.
    """
    project_ids = db.scalars(
        select(Project.id).join(Membership, Membership.project_id == Project.id).where(Membership.user_id == user.id)
    ).all()
    total = len(project_ids)
    if not project_ids:
        return {
            "activeEngagements": 0,
            "pendingApprovals": 0,
            "openRuns": 0,
            "totalProjects": 0,
        }
    meta_rows = db.scalars(select(EngagementMeta).where(EngagementMeta.project_id.in_(project_ids))).all()
    stage_by_project = {m.project_id: (m.stage or _DEFAULT_STAGE) for m in meta_rows}
    active = sum(1 for pid in project_ids if stage_by_project.get(pid, _DEFAULT_STAGE) != "Approved")
    pending_approvals = sum(1 for pid in project_ids if stage_by_project.get(pid, _DEFAULT_STAGE) == "In review")
    open_runs_count = len(
        db.scalars(
            select(Run.id).where(Run.project_id.in_(project_ids), Run.status.notin_(["done", "failed"]))
        ).all()
    )
    return {
        "activeEngagements": active,
        "pendingApprovals": pending_approvals,
        "openRuns": open_runs_count,
        "totalProjects": total,
    }
