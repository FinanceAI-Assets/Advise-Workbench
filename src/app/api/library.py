"""Catalog APIs for the workbench UI: the Leading Practice Library and the skills catalog.

The practice catalog (`lp_practices`) carries the taxonomy, maturity, version
and approval state the UI browses. Full-text retrieval over practice documents
stays in `lp_library.py`. Skills come from the built-in skill definitions under
`config/skills`, enriched with catalog metadata from `workbench_records`.
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.app.api.engagements import (
    _code,
    _metas,
    format_date,
    member_project_ids,
    record_activity,
    records,
    display_name,
)
from src.core.auth import get_current_user, require_project_role
from src.core.db.models import Conversation, LpPractice, Project, Run, SavedPractice, User, WorkbenchRecord, utcnow
from src.core.db.session import get_db

router = APIRouter()


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def _card(practice: LpPractice, saved: set[str]) -> dict:
    payload = json.loads(practice.payload_json or "{}")
    updated = payload.get("updatedMeta") or practice.owner
    return {
        "id": practice.id,
        "title": practice.title,
        "description": practice.description,
        "status": practice.status,
        "maturity": practice.maturity,
        "category": practice.category,
        "versionLabel": f"{practice.version_label} · {updated}".strip(" ·"),
        "saved": practice.id in saved,
    }


def _saved_ids(db: Session, user: User) -> set[str]:
    return set(db.scalars(select(SavedPractice.practice_id).where(SavedPractice.user_id == user.id)).all())


@router.get("/library")
def browse_library(
    q: str = "",
    category: str = "all",
    maturity: str = "",
    sort: str = "relevance",
    saved_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Approved practices only: candidates stay in the admin console until published."""
    approved = db.scalars(select(LpPractice).where(LpPractice.status == "Approved")).all()
    saved = _saved_ids(db, user)
    counts: dict[str, int] = {}
    for practice in approved:
        counts[practice.category] = counts.get(practice.category, 0) + 1
    categories = [{"id": "all", "label": "All practices", "count": len(approved)}] + [
        {"id": _slug(label), "label": label, "count": count} for label, count in sorted(counts.items())
    ]
    needle = q.strip().lower()
    matches = [
        p
        for p in approved
        if (category == "all" or _slug(p.category) == category)
        and (not maturity or p.maturity == maturity)
        and (not saved_only or p.id in saved)
        and (not needle or needle in f"{p.title} {p.description} {p.category}".lower())
    ]
    if sort == "title":
        matches.sort(key=lambda p: p.title.lower())
    elif sort == "updated":
        matches.sort(key=lambda p: p.updated_at, reverse=True)
    return {
        "totalPractices": len(approved),
        "categories": categories,
        "activeCategoryId": category,
        "matchingCount": len(matches),
        "maturities": sorted({p.maturity for p in approved if p.maturity}),
        "cards": [_card(p, saved) for p in matches],
        "savedCount": len(saved),
    }


def _practice(db: Session, practice_id: str) -> LpPractice:
    practice = db.scalar(select(LpPractice).where(LpPractice.id == practice_id.lower()))
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return practice


@router.get("/library/{practice_id}")
def get_practice(practice_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    practice = _practice(db, practice_id)
    payload = json.loads(practice.payload_json or "{}")
    return {
        "id": practice.id,
        "code": practice.id.upper(),
        "title": practice.title,
        "description": practice.description,
        "status": practice.status,
        "versionLabel": practice.version_label,
        "maturity": payload.get("maturity") or f"{practice.maturity} maturity",
        "recommendedWhen": payload.get("recommendedWhen", ""),
        "coreGuidance": payload.get("coreGuidance", []),
        "sourceAttribution": payload.get("sourceAttribution", ""),
        "practiceOwner": payload.get("practiceOwner") or practice.owner,
        "approvedMeta": payload.get("approvedMeta", ""),
        "sourceQuality": payload.get("sourceQuality", ""),
        "saved": practice.id in _saved_ids(db, user),
    }


@router.post("/library/{practice_id}/save")
def save_practice(practice_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    practice = _practice(db, practice_id)
    if practice.id not in _saved_ids(db, user):
        db.add(SavedPractice(user_id=user.id, practice_id=practice.id))
        db.commit()
    return {"id": practice.id, "saved": True}


@router.delete("/library/{practice_id}/save")
def unsave_practice(practice_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    practice = _practice(db, practice_id)
    db.execute(
        delete(SavedPractice).where(SavedPractice.user_id == user.id, SavedPractice.practice_id == practice.id)
    )
    db.commit()
    return {"id": practice.id, "saved": False}


class EngagementTarget(BaseModel):
    project_id: str = Field(alias="projectId")

    model_config = {"populate_by_name": True}


@router.post("/library/{practice_id}/add-to-engagement")
def add_practice_to_engagement(
    practice_id: str,
    body: EngagementTarget,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Put an approved practice in an engagement's source scope so conversations can cite it."""
    require_project_role(body.project_id, {"Owner", "Editor"}, user, db)
    practice = _practice(db, practice_id)
    if practice.status != "Approved":
        raise HTTPException(status_code=409, detail="Only approved practices can be added to an engagement")
    record_id = f"{body.project_id}:{practice.id}"
    existing = db.scalar(
        select(WorkbenchRecord).where(
            WorkbenchRecord.collection == "engagement_practices", WorkbenchRecord.record_id == record_id
        )
    )
    already = existing is not None or any(
        r.get("practiceId") == practice.id for r in records(db, "engagement_practices", project_id=body.project_id)
    )
    if not already:
        db.add(
            WorkbenchRecord(
                collection="engagement_practices",
                record_id=record_id,
                project_id=body.project_id,
                payload_json=json.dumps({"practiceId": practice.id, "title": practice.title}),
            )
        )
        record_activity(db, project_id=body.project_id, actor=display_name(user), kind="library",
                        title=f"{practice.title} added to sources", detail=f"{practice.id.upper()} · {practice.version_label}")
        db.commit()
    return {"id": practice.id, "projectId": body.project_id, "added": not already}


def _skill_cards(db: Session) -> list[dict]:
    return records(db, "skills")


@router.get("/skills")
def list_skills(q: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    cards = _skill_cards(db)
    needle = q.strip().lower()
    shown = [c for c in cards if not needle or needle in f"{c.get('name', '')} {c.get('description', '')}".lower()]
    return {
        "totalPublished": sum(1 for c in cards if c.get("published")),
        "cards": [{k: v for k, v in c.items() if k != "detail"} for c in shown],
        "skills": {c["id"]: c["detail"] for c in shown if c.get("detail")},
    }


@router.get("/skills/runs")
def skill_run_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Runs across the caller's engagements, newest first."""
    project_ids = member_project_ids(db, user)
    if not project_ids:
        return {"items": []}
    metas = _metas(db, project_ids)
    names = dict(db.execute(select(Project.id, Project.name).where(Project.id.in_(project_ids))).all())
    skills = {c["id"]: c for c in _skill_cards(db)}
    skill_by_project = {
        c.project_id: c.skill_id
        for c in db.scalars(select(Conversation).where(Conversation.project_id.in_(project_ids))).all()
        if c.skill_id
    }
    runs = db.scalars(
        select(Run).where(Run.project_id.in_(project_ids)).order_by(Run.created_at.desc()).limit(100)
    ).all()
    items = []
    for run in runs:
        skill = skills.get(skill_by_project.get(run.project_id, ""), {})
        try:
            outputs = " + ".join(str(o).upper() for o in json.loads(run.output_types or "[]"))
        except json.JSONDecodeError:
            outputs = run.output_types
        items.append(
            {
                "id": run.id,
                "projectId": run.project_id,
                "engagement": f"{names.get(run.project_id, run.project_id)} · {_code(run.project_id, metas.get(run.project_id))}",
                "skill": f"{skill.get('name', 'Conversation')} {skill.get('versionLabel', '')}".strip(),
                "outputs": outputs,
                "status": run.status,
                "when": format_date(run.created_at.date().isoformat()),
                "instruction": (run.instruction or "")[:160],
            }
        )
    return {"items": items}


class RunSkillRequest(EngagementTarget):
    pass


@router.post("/skills/{skill_id}/select")
def select_skill_for_engagement(
    skill_id: str,
    body: RunSkillRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Make a published skill the active skill of the caller's conversation in an engagement."""
    require_project_role(body.project_id, {"Owner", "Editor"}, user, db)
    skill = next((c for c in _skill_cards(db) if c["id"] == skill_id), None)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not skill.get("published"):
        raise HTTPException(status_code=409, detail="Only published skills can be run")
    from src.app.api.projects.conversation import _get_or_create_conversation

    conversation = _get_or_create_conversation(db, pid=body.project_id, user_id=user.id, user=user)
    conversation.skill_id = skill_id
    conversation.updated_at = utcnow()
    db.commit()
    return {"skillId": skill_id, "projectId": body.project_id, "href": f"/engagements/{body.project_id}/conversation"}
