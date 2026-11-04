"""Header features of the workbench UI: notifications and search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.app.api.engagements import _code, _metas, display_name, format_timestamp, member_project_ids
from src.core.auth import get_current_user
from src.core.db.models import LpPractice, Notification, Project, Review, User, utcnow
from src.core.db.session import get_db
from src.llm.config import PROVIDERS, load_llm_config
from src.llm.gateway import is_enabled, provider_name

router = APIRouter()

_FILTERS = {"all", "unread", "mentions", "system"}


@router.get("/settings/models")
def model_settings(user: User = Depends(get_current_user)) -> dict:
    """Expose non-secret model configuration status for the Settings screen."""
    config = load_llm_config()
    return {
        "providers": list(PROVIDERS),
        "provider": provider_name(),
        "model": config.models.get("default", ""),
        "planning_model": config.models.get("planning", ""),
        "critique_model": config.models.get("critique", ""),
        "base_url": config.base_url,
        "api_key_configured": bool(config.api_key),
        "enabled": is_enabled(),
    }


def _matches(notification: Notification, filter_: str) -> bool:
    if filter_ == "unread":
        return notification.read_at is None
    if filter_ == "mentions":
        return notification.kind == "mention"
    if filter_ == "system":
        return notification.kind == "system"
    return True


@router.get("/notifications")
def list_notifications(
    filter_: str = Query("all", alias="filter"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if filter_ not in _FILTERS:
        raise HTTPException(status_code=422, detail=f"filter must be one of {', '.join(sorted(_FILTERS))}")
    rows = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(200)
    ).all()
    return {
        "items": [
            {
                "id": n.id,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "read": n.read_at is not None,
                "when": format_timestamp(n.created_at),
            }
            for n in rows
            if _matches(n, filter_)
        ],
        "counts": {name: sum(1 for n in rows if _matches(n, name)) for name in sorted(_FILTERS)},
    }


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read_at = row.read_at or utcnow()
    db.commit()
    return {"ok": True}


@router.get("/search")
def search(
    q: str = Query("", max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Search what the caller may see: their engagements, approved practices and their engagements' artifacts."""
    needle = q.strip().lower()
    if len(needle) < 2:
        return {"query": q, "engagements": [], "practices": [], "artifacts": []}
    project_ids = member_project_ids(db, user)
    metas = _metas(db, project_ids)
    projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all() if project_ids else []
    engagements = [
        {
            "id": p.id,
            "title": p.name,
            "meta": f"{_code(p.id, metas.get(p.id))} · {(metas[p.id].stage if p.id in metas else None) or 'Brief'}",
            "href": f"/engagements/{p.id}",
        }
        for p in projects
        if needle in f"{p.name} {_code(p.id, metas.get(p.id))}".lower()
    ]
    practices = [
        {
            "id": p.id,
            "title": p.title,
            "meta": f"{p.id.upper()} · {p.version_label} · {p.category}",
            "href": f"/library?practice={p.id}",
        }
        for p in db.scalars(select(LpPractice).where(LpPractice.status == "Approved")).all()
        if needle in f"{p.title} {p.description} {p.category}".lower()
    ]
    names = {p.id: p.name for p in projects}
    owners = {u.id: display_name(u) for u in db.scalars(select(User)).all()}
    reviews = db.scalars(select(Review).where(Review.project_id.in_(project_ids))).all() if project_ids else []
    artifacts = [
        {
            "id": r.id,
            "title": r.title,
            "meta": f"{names.get(r.project_id or '', '')} · {r.artifact_type.upper()} {r.version_label} · "
            f"{owners.get(r.owner_id or '', '—')} · {r.state}",
            "href": f"/reviews/{r.id}" if r.state != "Draft" else f"/engagements/{r.project_id}/deliverables",
        }
        for r in reviews
        if needle in f"{r.title} {r.id}".lower()
    ]
    return {"query": q, "engagements": engagements, "practices": practices, "artifacts": artifacts}
