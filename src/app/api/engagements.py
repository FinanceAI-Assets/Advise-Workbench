"""Engagements API for the workbench UI.

An engagement is a Project plus its optional EngagementMeta row. These routes
return the view models the new UI renders (camelCase keys, matching
frontend/types/api.ts) so each screen needs one request. `/api/projects` and
the project studio are unchanged.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.api.projects.crud import _ensure_workspace_safe
from src.core.auth import get_current_user, require_project_role
from src.core.db.models import (
    ActivityEvent,
    Conversation,
    ConversationMessage,
    EngagementMeta,
    Membership,
    Project,
    Review,
    Run,
    RunEvent,
    User,
    WorkbenchRecord,
    utcnow,
)
from src.core.db.session import get_db
from src.core.storage import workspace_path

router = APIRouter()

STAGES = ["Brief", "Sources", "Drafting", "In review", "Approved"]
_STEP_LABELS = ["Brief", "Sources", "Draft", "Review", "Export"]
_READ = {"Owner", "Editor", "Viewer"}
_WRITE = {"Owner", "Editor"}

# Workbench role shown in the UI -> (project role that enforces it, permission summary).
MEMBER_ROLES: dict[str, tuple[str, str]] = {
    "Engagement lead": ("Owner", "Edit · Submit"),
    "Independent reviewer": ("Editor", "Comment · Approve"),
    "Contributor": ("Editor", "Draft · Upload"),
    "Practice advisor": ("Editor", "Draft · Cite"),
    "Viewer": ("Viewer", "Read permitted content"),
}
_DEFAULT_TITLE = {"Owner": "Engagement lead", "Editor": "Contributor", "Viewer": "Viewer"}


def display_name(user: User | None) -> str:
    if user is None:
        return "—"
    return (user.full_name or "").strip() or user.email.split("@")[0]


def format_date(value: str | None, *, year: bool = True) -> str:
    """ISO dates are stored; the UI shows '12 Oct 2026'. Anything else passes through."""
    raw = (value or "").strip()
    if not raw:
        return "—"
    try:
        parsed = date.fromisoformat(raw[:10])
    except ValueError:
        return raw
    return f"{parsed.day:02d} {parsed.strftime('%b %Y' if year else '%b')}"


def format_timestamp(value: datetime) -> str:
    return f"{value.day:02d} {value.strftime('%b')} · {value.strftime('%H:%M')}"


def record_activity(db: Session, *, project_id: str | None, actor: str, kind: str, title: str, detail: str = "") -> None:
    db.add(ActivityEvent(project_id=project_id, actor=actor, kind=kind, title=title, detail=detail))


def records(db: Session, collection: str, *, project_id: str | None = None, user_id: str | None = None) -> list[dict]:
    stmt = select(WorkbenchRecord).where(WorkbenchRecord.collection == collection)
    if project_id is not None:
        stmt = stmt.where(WorkbenchRecord.project_id == project_id)
    if user_id is not None:
        stmt = stmt.where(WorkbenchRecord.user_id == user_id)
    rows = db.scalars(stmt.order_by(WorkbenchRecord.position, WorkbenchRecord.id)).all()
    return [{"id": r.record_id, **json.loads(r.payload_json or "{}")} for r in rows]


def member_project_ids(db: Session, user: User) -> list[str]:
    return list(db.scalars(select(Membership.project_id).where(Membership.user_id == user.id)).all())


def _stage(meta: EngagementMeta | None) -> str:
    stage = (meta.stage if meta else None) or "Brief"
    return stage if stage in STAGES else "Brief"


def _code(pid: str, meta: EngagementMeta | None) -> str:
    return (meta.code if meta else None) or pid.upper()


def _owners(db: Session, project_ids: list[str]) -> dict[str, str]:
    if not project_ids:
        return {}
    rows = db.execute(
        select(Membership.project_id, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.project_id.in_(project_ids), Membership.role == "Owner")
        .order_by(Membership.id)
    ).all()
    owners: dict[str, str] = {}
    for pid, owner in rows:
        owners.setdefault(pid, display_name(owner))
    return owners


def _metas(db: Session, project_ids: list[str]) -> dict[str, EngagementMeta]:
    if not project_ids:
        return {}
    rows = db.scalars(select(EngagementMeta).where(EngagementMeta.project_id.in_(project_ids))).all()
    return {m.project_id: m for m in rows}


def _row(project: Project, meta: EngagementMeta | None, owner: str) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "code": _code(project.id, meta),
        "type": (meta.type if meta else None) or "Advisory engagement",
        "stage": _stage(meta),
        "progress": meta.progress if meta and meta.progress is not None else 0,
        "owner": owner,
        "nextTask": (meta.next_task if meta else None) or "—",
        "dueDate": format_date(meta.due_date if meta else None),
    }


def _is_active(meta: EngagementMeta | None) -> bool:
    return ((meta.status if meta else None) or "active") != "archived"


@router.get("")
def list_engagements(
    q: str = "",
    status: str = "active",
    mine: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Project, Membership.role).join(Membership, Membership.project_id == Project.id)
    stmt = stmt.where(Membership.user_id == user.id)
    pairs = db.execute(stmt).all()
    project_ids = [p.id for p, _ in pairs]
    metas = _metas(db, project_ids)
    # Most recently worked on first.
    pairs = sorted(
        pairs,
        key=lambda pair: metas[pair[0].id].updated_at if pair[0].id in metas else pair[0].created_at,
        reverse=True,
    )
    owners = _owners(db, project_ids)
    needle = q.strip().lower()
    rows: list[dict] = []
    for project, role in pairs:
        meta = metas.get(project.id)
        if status == "active" and not _is_active(meta):
            continue
        if status == "archived" and _is_active(meta):
            continue
        if mine and role != "Owner":
            continue
        row = _row(project, meta, owners.get(project.id, "—"))
        if needle and needle not in f"{row['name']} {row['code']} {row['owner']}".lower():
            continue
        rows.append(row)
    start = (page - 1) * page_size
    return {"items": rows[start : start + page_size], "total": len(rows), "page": page, "pageSize": page_size}


@router.get("/stats")
def engagement_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    project_ids = member_project_ids(db, user)
    metas = _metas(db, project_ids)
    active = sum(1 for pid in project_ids if _is_active(metas.get(pid)) and _stage(metas.get(pid)) != "Approved")
    reviews = db.scalars(select(Review).where(Review.project_id.in_(project_ids))).all() if project_ids else []
    in_review = [r for r in reviews if r.state not in {"Approved", "Draft"}]
    need_response = sum(1 for r in in_review if r.owner_id == user.id and r.state == "Changes requested")
    need_response += sum(1 for r in in_review if r.reviewer_id == user.id and r.state != "Changes requested")
    approved = sum(1 for r in reviews if r.state == "Approved")
    open_milestones = [
        m
        for pid in project_ids
        for m in records(db, "milestones", project_id=pid)
        if m.get("status") != "Complete"
    ]
    return {
        "items": [
            {
                "id": "active",
                "label": "Active engagements",
                "value": active,
                "helper": f"Across {len(project_ids)} engagement{'' if len(project_ids) == 1 else 's'} you can access",
            },
            {
                "id": "in-review",
                "label": "Deliverables in review",
                "value": len(in_review),
                "helper": f"{need_response} need your response" if need_response else "Nothing waiting on you",
                "helperTone": "warning" if need_response else "default",
            },
            {
                "id": "ready",
                "label": "Ready to export",
                "value": approved,
                "helper": "Human-approved artifacts",
                "helperTone": "success",
            },
            {
                "id": "milestones",
                "label": "Upcoming milestones",
                "value": len(open_milestones),
                "helper": "Not yet complete",
            },
        ]
    }


def _review_action(review: Review, code: str, user: User, reviewer: str) -> dict | None:
    if review.state == "Approved":
        return None
    if review.owner_id == user.id and review.state == "Changes requested":
        title, label = f"Resolve review comments on {review.title}", "Open review"
    elif review.reviewer_id == user.id and review.state != "Changes requested":
        title, label = f"Review {review.title}", "Open review"
    else:
        return None
    return {
        "id": review.id,
        "title": title,
        "description": f"{code} · {review.id} · {review.version_label} · Reviewer: {reviewer}",
        "due": f"Due {format_date(review.due_date, year=False)}",
        "actionLabel": label,
        "href": f"/reviews/{review.id}",
        "icon": "review" if review.reviewer_id == user.id else "comment",
    }


@router.get("/next-actions")
def next_actions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Work waiting on the caller: open reviews they own or are assigned, and their milestones."""
    project_ids = member_project_ids(db, user)
    metas = _metas(db, project_ids)
    names = {u.id: display_name(u) for u in db.scalars(select(User)).all()}
    reviews = db.scalars(select(Review).where(Review.project_id.in_(project_ids))).all() if project_ids else []
    needs_action = []
    completed = []
    for review in reviews:
        code = _code(review.project_id or "", metas.get(review.project_id or ""))
        action = _review_action(review, code, user, names.get(review.reviewer_id or "", "—"))
        if action:
            needs_action.append(action)
        elif review.state == "Approved" and user.id in (review.owner_id, review.reviewer_id):
            completed.append(
                {
                    "id": review.id,
                    "title": f"{review.title} approved",
                    "description": f"{code} · {review.id} · {review.version_label}",
                    "due": "Approved",
                    "href": f"/reviews/{review.id}",
                    "icon": "review",
                }
            )
    upcoming = []
    me = display_name(user)
    for pid in project_ids:
        for milestone in records(db, "milestones", project_id=pid):
            if milestone.get("owner") != me:
                continue
            item = {
                "id": f"{pid}:{milestone['id']}",
                "title": milestone.get("name", ""),
                "description": f"{_code(pid, metas.get(pid))} · Milestone · {milestone.get('status', '')}",
                "due": f"Due {format_date(milestone.get('target'), year=False)}",
                "href": f"/engagements/{pid}",
                "icon": "comment",
            }
            (completed if milestone.get("status") == "Complete" else upcoming).append(item)
    return {"needsAction": needs_action, "upcoming": upcoming, "completed": completed}


def _activity_item(event: ActivityEvent) -> dict:
    return {
        "id": str(event.id),
        "title": event.title,
        "meta": f"{event.actor} · {format_timestamp(event.created_at)}",
        "detail": event.detail,
        "kind": event.kind,
        "icon": "library" if event.kind in {"library", "source"} else "deck",
    }


@router.get("/activity")
def recent_activity(
    limit: int = Query(5, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    project_ids = member_project_ids(db, user)
    if not project_ids:
        return {"items": []}
    events = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.project_id.in_(project_ids))
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .limit(limit)
    ).all()
    return {"items": [_activity_item(e) for e in events]}


class EngagementBriefFields(BaseModel):
    client_org: str | None = Field(None, alias="clientOrg", max_length=255)
    type: str | None = Field(None, max_length=64)
    brief: str | None = None
    sponsor_objective: str | None = Field(None, alias="sponsorObjective")
    scope: str | None = None
    success_measures: str | None = Field(None, alias="successMeasures")
    start_date: str | None = Field(None, alias="startDate", max_length=32)
    target_close: str | None = Field(None, alias="targetClose", max_length=32)
    classification: str | None = Field(None, max_length=64)

    model_config = {"populate_by_name": True}


class CreateEngagementRequest(EngagementBriefFields):
    name: str = Field(min_length=3, max_length=255)
    brief: str = Field(min_length=30)


class UpdateEngagementRequest(EngagementBriefFields):
    name: str | None = Field(None, min_length=3, max_length=255)
    stage: str | None = None
    progress: int | None = Field(None, ge=0, le=100)
    next_task: str | None = Field(None, alias="nextTask")
    due_date: str | None = Field(None, alias="dueDate", max_length=32)


_BRIEF_FIELDS = tuple(EngagementBriefFields.model_fields)


def _new_code(db: Session, name: str) -> str:
    letters = re.sub(r"[^A-Za-z ]", "", name).split()
    prefix = ("".join(w[0] for w in letters[:2]) if len(letters) > 1 else (letters[0][:2] if letters else "EN")).upper()
    count = db.scalar(select(func.count()).select_from(EngagementMeta)) or 0
    return f"{prefix}-{count + 1:03d}"


@router.post("", status_code=201)
def create_engagement(
    body: CreateEngagementRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    project = Project(id=f"p_{uuid.uuid4().hex[:10]}", name=body.name.strip(), created_by=user.id)
    db.add(project)
    db.flush()  # the membership and metadata rows reference the project
    db.add(Membership(id=f"m_{uuid.uuid4().hex[:10]}", project_id=project.id, user_id=user.id, role="Owner"))
    meta = EngagementMeta(
        id=f"em_{uuid.uuid4().hex[:10]}",
        project_id=project.id,
        code=_new_code(db, body.name),
        stage="Brief",
        progress=0,
        status="active",
        retention_days=180,
        next_task="Attach permitted sources",
    )
    for field in _BRIEF_FIELDS:
        setattr(meta, field, getattr(body, field))
    meta.classification = meta.classification or "Internal · Engagement-scoped"
    db.add(meta)
    record_activity(db, project_id=project.id, actor=display_name(user), kind="brief", title="Engagement created")
    db.commit()
    background_tasks.add_task(_ensure_workspace_safe, project.id)
    return {"id": project.id, "name": project.name, "code": meta.code}


def _steps(stage: str) -> list[dict]:
    current = STAGES.index(stage)
    steps = []
    for i, label in enumerate(_STEP_LABELS):
        state = "complete" if i < current else "in-progress" if i == current else "upcoming"
        helper = {"complete": "Complete", "in-progress": "In progress", "upcoming": "Upcoming"}[state]
        steps.append({"id": label.lower(), "index": i + 1, "label": label, "status": state, "helper": helper})
    return steps


def _member_rows(db: Session, pid: str) -> list[dict]:
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.project_id == pid)
        .order_by(Membership.id)
    ).all()
    titles = {r["id"]: r for r in records(db, "member_roles", project_id=pid)}
    items = []
    for membership, member in rows:
        title = titles.get(membership.id, {}).get("title") or _DEFAULT_TITLE.get(membership.role, membership.role)
        permission = MEMBER_ROLES.get(title, (membership.role, membership.role))[1]
        items.append(
            {
                "id": membership.id,
                "userId": member.id,
                "name": display_name(member),
                "email": member.email,
                "role": title,
                "permission": permission,
                "status": "Active",
                "roleAndAccess": f"{title} · {permission}",
            }
        )
    order = list(MEMBER_ROLES)
    return sorted(items, key=lambda m: order.index(m["role"]) if m["role"] in order else len(order))


def _documents(pid: str) -> list[str]:
    folder = workspace_path(pid) / "source_docs"
    return sorted(p.name for p in folder.glob("*") if p.is_file()) if folder.is_dir() else []


def _deliverables(db: Session, pid: str) -> list[dict]:
    reviews = db.scalars(select(Review).where(Review.project_id == pid).order_by(Review.created_at)).all()
    items = [
        {
            "id": r.id,
            "name": r.title,
            "meta": f"{r.artifact_type.upper()} · {r.version_label} · {format_date(r.updated_at.date().isoformat())}",
            "icon": "doc" if r.artifact_type == "docx" else "deck",
            "status": r.state,
        }
        for r in reviews
        if r.artifact_type in {"pptx", "docx"}
    ]
    if items:
        return items
    run = db.scalar(
        select(Run).where(Run.project_id == pid, Run.status != "failed").order_by(Run.created_at.desc()).limit(1)
    )
    if run is None:
        return []
    return [
        {
            "id": run.id,
            "name": "Latest draft",
            "meta": f"{run.output_types} · {format_date(run.created_at.date().isoformat())}",
            "icon": "deck",
            "status": "Draft",
        }
    ]


def _require_project(db: Session, pid: str) -> Project:
    project = db.scalar(select(Project).where(Project.id == pid))
    if project is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return project


@router.get("/{pid}")
def get_engagement(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_project_role(pid, _READ, user, db)
    project = _require_project(db, pid)
    meta = db.scalar(select(EngagementMeta).where(EngagementMeta.project_id == pid))
    members = _member_rows(db, pid)
    documents = _documents(pid)
    practices = records(db, "engagement_practices", project_id=pid)
    deliverables = _deliverables(db, pid)
    lead = next((m["name"] for m in members if m["role"] == "Engagement lead"), members[0]["name"] if members else "—")
    start, close = (meta.start_date if meta else None), (meta.target_close if meta else None)
    date_range = (
        f"{format_date(start, year=False)}–{format_date(close)}"
        if start and close
        else f"Created {format_date(project.created_at.date().isoformat())}"
    )
    sources = []
    if practices:
        sources.append({"id": "practices", "label": "Approved practice sources", "value": f"{len(practices)} verified"})
    sources.append({"id": "documents", "label": "Engagement documents", "value": f"{len(documents)} indexed"})
    updated = meta.updated_at if meta else project.created_at
    return {
        "id": pid,
        "code": _code(pid, meta),
        "name": project.name,
        "subtitle": (meta.type if meta else None) or "Advisory engagement",
        "clientOrg": (meta.client_org if meta else None) or "",
        "dateRange": date_range,
        "startDate": start or "",
        "targetClose": close or "",
        "stage": _stage(meta),
        "status": (meta.status if meta else None) or "active",
        "retentionDays": (meta.retention_days if meta else None) or 180,
        "lead": lead,
        "teamMemberCount": len(members),
        "steps": _steps(_stage(meta)),
        "tabCounts": {
            "sources": len(documents) + len(practices),
            "deliverables": len(deliverables),
            "team": len(members),
        },
        "brief": {
            "updated": f"Updated {format_date(updated.date().isoformat(), year=False)}",
            "summary": (meta.brief if meta else None) or "No brief captured yet for this engagement.",
            "context": "",
            "sponsorObjective": (meta.sponsor_objective if meta else None) or "—",
            "scope": (meta.scope if meta else None) or "—",
            "successMeasures": (meta.success_measures if meta else None) or "—",
            "classification": (meta.classification if meta else None) or "Internal · Engagement-scoped",
        },
        "milestones": [
            {**m, "target": format_date(m.get("target"), year=False)} for m in records(db, "milestones", project_id=pid)
        ],
        "teamMembers": members,
        "teamNote": f"{len(members)} member{'' if len(members) == 1 else 's'} · Engagement-scoped access",
        "evidenceSourceCount": len(documents) + len(practices),
        "evidenceSources": sources,
        "evidenceWarning": None,
        "deliverables": deliverables,
        "documents": documents,
        "practices": practices,
    }


@router.put("/{pid}")
def update_engagement(
    pid: str,
    body: UpdateEngagementRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_project_role(pid, _WRITE, user, db)
    project = _require_project(db, pid)
    if body.stage is not None and body.stage not in STAGES:
        raise HTTPException(status_code=422, detail=f"stage must be one of {', '.join(STAGES)}")
    meta = db.scalar(select(EngagementMeta).where(EngagementMeta.project_id == pid))
    if meta is None:
        meta = EngagementMeta(id=f"em_{uuid.uuid4().hex[:10]}", project_id=pid, code=_new_code(db, project.name))
        db.add(meta)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name"):
        project.name = changes.pop("name").strip()
    for field, value in changes.items():
        setattr(meta, field, value)
    meta.updated_at = utcnow()
    record_activity(db, project_id=pid, actor=display_name(user), kind="brief", title="Engagement brief updated")
    db.commit()
    return {"id": pid, "stage": _stage(meta)}


@router.get("/{pid}/members")
def list_members(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_project_role(pid, _READ, user, db)
    return {"items": _member_rows(db, pid), "roles": list(MEMBER_ROLES)}


class MemberRequest(BaseModel):
    email: str | None = None
    role: str


def _set_member_title(db: Session, pid: str, membership_id: str, title: str) -> None:
    row = db.scalar(
        select(WorkbenchRecord).where(
            WorkbenchRecord.collection == "member_roles", WorkbenchRecord.record_id == membership_id
        )
    )
    if row is None:
        row = WorkbenchRecord(collection="member_roles", record_id=membership_id, project_id=pid)
        db.add(row)
    row.payload_json = json.dumps({"title": title})
    row.updated_at = utcnow()


def _clear_role_cache(user_id: str, pid: str) -> None:
    from src.core.cache import cache_service

    cache_service.set(f"project_role:{user_id}:{pid}", {}, ttl_seconds=1)


@router.post("/{pid}/members", status_code=201)
def add_member(
    pid: str,
    body: MemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Add an existing organization account to the engagement. Only the lead can change access."""
    require_project_role(pid, {"Owner"}, user, db)
    if body.role not in MEMBER_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {', '.join(MEMBER_ROLES)}")
    member = db.scalar(select(User).where(User.email == (body.email or "").strip().lower()))
    if member is None:
        raise HTTPException(status_code=404, detail="No organization account with that email")
    existing = db.scalar(select(Membership).where(Membership.project_id == pid, Membership.user_id == member.id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already a member of this engagement")
    membership = Membership(
        id=f"m_{uuid.uuid4().hex[:10]}", project_id=pid, user_id=member.id, role=MEMBER_ROLES[body.role][0]
    )
    db.add(membership)
    _set_member_title(db, pid, membership.id, body.role)
    record_activity(
        db, project_id=pid, actor=display_name(user), kind="access", title=f"{display_name(member)} added as {body.role}"
    )
    db.commit()
    _clear_role_cache(member.id, pid)
    return {"id": membership.id}


def _membership(db: Session, pid: str, mid: str) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.id == mid, Membership.project_id == pid))
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return membership


def _guard_last_owner(db: Session, pid: str, membership: Membership) -> None:
    if membership.role != "Owner":
        return
    owners = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.project_id == pid, Membership.role == "Owner")
    )
    if (owners or 0) <= 1:
        raise HTTPException(status_code=409, detail="An engagement must keep at least one engagement lead")


@router.patch("/{pid}/members/{mid}")
def change_member_role(
    pid: str,
    mid: str,
    body: MemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_project_role(pid, {"Owner"}, user, db)
    if body.role not in MEMBER_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {', '.join(MEMBER_ROLES)}")
    membership = _membership(db, pid, mid)
    new_role = MEMBER_ROLES[body.role][0]
    if new_role != "Owner":
        _guard_last_owner(db, pid, membership)
    membership.role = new_role
    _set_member_title(db, pid, membership.id, body.role)
    db.commit()
    _clear_role_cache(membership.user_id, pid)
    return {"id": membership.id, "role": body.role}


@router.delete("/{pid}/members/{mid}")
def remove_member(
    pid: str,
    mid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_project_role(pid, {"Owner"}, user, db)
    membership = _membership(db, pid, mid)
    _guard_last_owner(db, pid, membership)
    member_id = membership.user_id
    db.delete(membership)
    record_activity(db, project_id=pid, actor=display_name(user), kind="access", title="Member removed")
    db.commit()
    _clear_role_cache(member_id, pid)
    return {"ok": True}


@router.get("/{pid}/activity")
def engagement_activity(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_project_role(pid, _READ, user, db)
    events = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.project_id == pid)
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .limit(100)
    ).all()
    return {"items": [_activity_item(e) for e in events]}


@router.get("/{pid}/export-readiness")
def export_readiness(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Export is allowed only when every reviewed artifact of the engagement is approved."""
    require_project_role(pid, _READ, user, db)
    reviews = db.scalars(select(Review).where(Review.project_id == pid).order_by(Review.created_at)).all()
    artifacts = [
        {
            "id": r.id,
            "name": r.title,
            "version": f"{r.artifact_type.upper()} {r.version_label}",
            "review": r.state,
            "export": "Available" if r.state == "Approved" else "Locked",
            "runId": r.run_id,
            "type": r.artifact_type,
        }
        for r in reviews
    ]
    blockers = [a["id"] for a in artifacts if a["export"] == "Locked"]
    return {
        "artifacts": artifacts,
        "ready": bool(artifacts) and not blockers,
        "blockers": blockers,
        "message": (
            "All artifacts are approved for export."
            if artifacts and not blockers
            else "No reviewed artifacts yet. Create drafts and submit them for review."
            if not artifacts
            else f"Resolve {', '.join(blockers)} and obtain independent approval before export."
        ),
    }


# Milestones of draft generation, in order, with the run events that show each one has been reached.
_RUN_STAGES: list[tuple[str, str, set[str]]] = [
    ("approved", "Plan approved", {"plan_approved", "execution_enqueued", "execution_started"}),
    ("research", "Reading sources and planning the content", {"coordinator_started", "fanout_start", "context_trace"}),
    ("drafting", "Drafting the content", {"fanout_stage_results", "coordinator_plan", "fanout_complete"}),
    ("building", "Building the PowerPoint and Word files", {"coordinator_completed", "skill.loading", "task.started"}),
    ("checks", "Running quality and evidence checks", {"visual_qa_report", "qa_report", "guardrail_report", "evaluator_pipeline"}),
    ("ready", "Ready for review", {"review_ready", "done"}),
]
_RUN_ACTIVE = {"approved", "running", "queued", "in_progress"}
_RUN_FINISHED = {"review_ready", "done"}


@router.get("/{pid}/run-progress")
def run_progress(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Where the engagement's latest draft generation stands, as ordered milestones."""
    require_project_role(pid, _READ, user, db)
    run = db.scalar(select(Run).where(Run.project_id == pid).order_by(Run.created_at.desc()).limit(1))
    if run is None:
        return {"run": None}
    events = db.scalars(select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.id)).all()
    seen: set[str] = set()
    for event in events:
        seen.add(event.event_type)
        if event.event_type == "step":
            payload = event.payload_json if isinstance(event.payload_json, dict) else {}
            inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
            if isinstance(inner.get("status"), str):
                seen.add(inner["status"])
    if run.status in _RUN_FINISHED:
        seen.add("review_ready")
    reached = [bool(seen & markers) for _, _, markers in _RUN_STAGES]
    last = max((i for i, hit in enumerate(reached) if hit), default=-1)
    active = run.status in _RUN_ACTIVE
    # Reached milestones are done; while the run is working, the next one is in progress.
    current = min(last + 1, len(_RUN_STAGES) - 1) if active else -1
    stages = [
        {"id": key, "label": label, "state": "current" if i == current else "done" if i <= last else "upcoming"}
        for i, (key, label, _) in enumerate(_RUN_STAGES)
    ]
    run_dir = workspace_path(pid) / "runs" / run.id
    outputs = [name for name in ("output.pptx", "output.docx") if (run_dir / name).is_file()]
    started = events[0].created_at if events else run.created_at
    latest = events[-1].created_at if events else run.created_at
    end = utcnow() if active else latest
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "instruction": (run.instruction or "")[:200],
            "active": active,
            "finished": run.status in _RUN_FINISHED,
            "failed": run.status == "failed",
            "needsApproval": run.status == "plan_ready",
            "error": run.error_message or "",
            "elapsedSeconds": max(0, int((end - started).total_seconds())),
            "lastUpdateSeconds": max(0, int((utcnow() - latest).total_seconds())) if active else 0,
            "eventCount": len(events),
            "outputs": [name.split(".")[-1] for name in outputs],
            "stages": stages,
        }
    }


def _own_conversations(db: Session, pid: str, user: User) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.project_id == pid, Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
        ).all()
    )


@router.get("/{pid}/conversations")
def list_conversations(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """The caller's conversations in this engagement. The first one is the active conversation."""
    require_project_role(pid, _READ, user, db)
    conversations = _own_conversations(db, pid, user)
    skills = {s["id"]: s for s in records(db, "skills")}
    published = [s for s in skills.values() if s.get("published")]
    active = conversations[0] if conversations else None
    skill = skills.get(active.skill_id or "") if active else None
    skill = skill or (published[0] if published else None)
    documents = _documents(pid)
    practices = records(db, "engagement_practices", project_id=pid)
    return {
        "items": [
            {
                "id": c.id,
                "label": c.title,
                "active": i == 0,
                "updated": format_timestamp(c.updated_at),
            }
            for i, c in enumerate(conversations)
        ],
        "skill": (
            {
                "id": skill["id"],
                "name": skill.get("name", ""),
                "version": skill.get("versionLabel", ""),
                "meta": skill.get("description", ""),
                "formats": [part.strip() for part in str(skill.get("formats", "")).split("+") if part.strip()],
            }
            if skill
            else None
        ),
        "skills": [
            {"id": s["id"], "name": s.get("name", ""), "version": s.get("versionLabel", ""), "formats": s.get("formats", "")}
            for s in published
        ],
        "sources": {
            "documents": documents,
            "practices": [{"id": p.get("practiceId"), "title": p.get("title")} for p in practices],
            "total": len(documents) + len(practices),
        },
    }


@router.get("/{pid}/conversations/usage")
def active_conversation_usage(pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Tokens, estimated cost and model for the caller's active conversation, including a reply in progress."""
    from src.app.api.projects._conversation_usage import conversation_usage

    require_project_role(pid, _READ, user, db)
    conversations = _own_conversations(db, pid, user)
    active = conversations[0] if conversations else None
    return conversation_usage(db, conversation_id=active.id if active else None, project_id=pid, user_id=user.id)


class ConversationRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)


@router.post("/{pid}/conversations", status_code=201)
def start_conversation(
    pid: str, body: ConversationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Start a new thread. Existing conversations are kept."""
    require_project_role(pid, _WRITE, user, db)
    previous = _own_conversations(db, pid, user)
    conversation = Conversation(
        id=f"conv_{uuid.uuid4().hex[:10]}",
        project_id=pid,
        user_id=user.id,
        title=body.title.strip(),
        skill_id=previous[0].skill_id if previous else None,
    )
    db.add(conversation)
    db.flush()
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="New conversation started. Ask a question grounded in this engagement's permitted sources.",
            metadata_json=json.dumps({"kind": "greeting"}),
        )
    )
    record_activity(db, project_id=pid, actor=display_name(user), kind="conversation",
                    title=f"Conversation started: {conversation.title}")
    db.commit()
    return {"id": conversation.id}


@router.post("/{pid}/conversations/{cid}/activate")
def activate_conversation(
    pid: str, cid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    require_project_role(pid, _READ, user, db)
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == cid, Conversation.project_id == pid, Conversation.user_id == user.id
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.updated_at = utcnow()
    db.commit()
    return {"id": conversation.id}
