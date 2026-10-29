"""Admin console API. Every route requires a platform administrator.

Engagement, review, practice and audit data is read live from the database.
Governance reference content with no workflow of its own (policy set, role
matrix, risk register, ingestion pipeline, skill definitions) is stored in
`workbench_records` and seeded by `scripts/seed_demo.py`.

Administrative rights never bypass review: an administrator can route work,
adjust retention and archive, but cannot approve an artifact or publish a
practice that its independent reviewer has not approved.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.api import admin_library
from src.app.api.engagements import (
    MEMBER_ROLES,
    _code,
    _member_rows,
    _metas,
    _set_member_title,
    display_name,
    format_date,
    format_timestamp,
    record_activity,
    records,
)
from src.app.api.reviews import _notify, _type_label
from src.core.auth import PLATFORM_ROLES, require_admin
from src.core.db.models import (
    ActivityEvent,
    EngagementMeta,
    LpPractice,
    Membership,
    Project,
    Review,
    User,
    WorkbenchRecord,
    utcnow,
)
from src.core.db.session import get_db

router = APIRouter()


class UpdateUserRoleRequest(BaseModel):
    role: str


@router.get("/users")
def list_platform_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, str | bool]]:
    """List users and their platform roles for administrator access management."""
    rows = db.scalars(select(User).order_by(User.email.asc())).all()
    return [
        {
            "id": row.id,
            "email": row.email,
            "name": (row.full_name or "").strip() or row.email.split("@")[0],
            "role": "admin" if row.is_admin else (row.role or "user"),
            "isAdmin": bool(row.is_admin or row.role == "admin"),
        }
        for row in rows
    ]


@router.patch("/users/{user_id}/role")
def update_platform_user_role(
    user_id: str,
    body: UpdateUserRoleRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str | bool]:
    """Assign a platform role; admin access is never self-granted."""
    if body.role not in PLATFORM_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of: {', '.join(sorted(PLATFORM_ROLES))}")
    row = db.scalar(select(User).where(User.id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    if row.id == admin.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="Administrators cannot remove their own admin access")
    row.role = body.role
    row.is_admin = body.role == "admin"
    db.commit()
    return {
        "id": row.id,
        "email": row.email,
        "name": (row.full_name or "").strip() or row.email.split("@")[0],
        "role": row.role,
        "isAdmin": bool(row.is_admin),
    }

_OPEN = {"Approved", "Draft"}
_SEED_HINT = "Governance reference data is not loaded. Run `make seed.demo` to load the sample set."
# The library's sample walkthrough, shown for practices that have no uploaded source. It is the fixture the demo
# seed loads, read directly so the screen works on an unseeded database or one seeded before a section existed.
_LIBRARY_FIXTURE = Path(__file__).resolve().parents[3] / "data" / "seed" / "workbench" / "admin_library.json"


def _library_sample() -> dict:
    try:
        return json.loads(_LIBRARY_FIXTURE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _screen(db: Session, name: str, *, required: bool = False) -> dict:
    row = db.scalar(
        select(WorkbenchRecord).where(
            WorkbenchRecord.collection == "admin_screens", WorkbenchRecord.record_id == f"demo-{name}"
        )
    )
    if row is None:
        if required:
            raise HTTPException(status_code=404, detail=_SEED_HINT)
        return {}
    return json.loads(row.payload_json or "{}")


def _save_screen(db: Session, name: str, payload: dict) -> None:
    row = db.scalar(
        select(WorkbenchRecord).where(
            WorkbenchRecord.collection == "admin_screens", WorkbenchRecord.record_id == f"demo-{name}"
        )
    )
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.updated_at = utcnow()


def _names(db: Session) -> dict[str, str]:
    return {u.id: display_name(u) for u in db.scalars(select(User)).all()}


def _audit(db: Session, limit: int) -> list[dict]:
    events = db.scalars(
        select(ActivityEvent).order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc()).limit(limit)
    ).all()
    icons = {"review": "comment", "evidence": "check", "deck": "history", "access": "send", "admin": "send"}
    return [
        {
            "id": str(e.id),
            "title": f"{format_timestamp(e.created_at)} · {e.title}",
            "attribution": " · ".join(part for part in (e.actor, e.detail) if part),
            "icon": icons.get(e.kind, "history"),
        }
        for e in events
    ]


def _open_reviews(db: Session) -> list[Review]:
    reviews = db.scalars(select(Review).order_by(Review.due_date, Review.id)).all()
    return [r for r in reviews if r.state not in _OPEN]


@router.get("/overview")
def overview(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    screen = _screen(db, "overview")
    names = _names(db)
    metas = db.scalars(select(EngagementMeta)).all()
    active = sum(1 for m in metas if (m.status or "active") != "archived")
    pending = _open_reviews(db)
    approved_practices = len(db.scalars(select(LpPractice.id).where(LpPractice.status == "Approved")).all())
    risks = screen.get("riskQueue", [])
    latest = _audit(db, 1)
    return {
        **screen,
        "stats": [
            {"id": "engagements", "label": "Active engagements", "value": str(active),
             "helper": f"{len(metas)} in total"},
            {"id": "approvals", "label": "Pending approvals", "value": str(len(pending)),
             "helper": "Assigned to independent reviewers", "helperTone": "warning" if pending else "default"},
            {"id": "practices", "label": "Approved practices", "value": str(approved_practices),
             "helper": "Published to the library", "helperTone": "success"},
            {"id": "risks", "label": "Open risks", "value": str(len(risks)), "helper": "In the risk register"},
        ],
        "pendingApprovals": [
            {
                "id": r.id,
                "item": f"{r.title} · {r.id}",
                "typeVersion": _type_label(r),
                "assignedTo": names.get(r.reviewer_id or "", "Unassigned"),
                "due": format_date(r.due_date, year=False),
                "state": r.state,
            }
            for r in pending[:4]
        ],
        "pendingApprovalsTotal": len(pending),
        "ingestionHealth": screen.get("ingestionHealth", []),
        "ingestionUpdatedMeta": screen.get("ingestionUpdatedMeta", ""),
        "ingestionWarning": screen.get("ingestionWarning"),
        "riskQueue": risks,
        "riskQueueOpenCount": len(risks),
        "riskQueueFootnote": screen.get("riskQueueFootnote", ""),
        "controlsAudit": screen.get("controlsAudit", []),
        "controlsAuditEvent": latest[0]["title"] if latest else "",
        "ingestionJobs": records(db, "ingestion_jobs"),
    }


def _retention(meta: EngagementMeta | None) -> str:
    return f"{(meta.retention_days if meta else None) or 180} days after close"


def _control_state(meta: EngagementMeta | None, reviews: list[Review]) -> str:
    if meta and meta.status == "archived":
        return "Archived"
    if any("risk" in r.state.lower() or "blocked" in r.state.lower() for r in reviews):
        return "Access risk"
    if any(r.state == "Changes requested" for r in reviews):
        return "Export locked"
    if any(r.state not in _OPEN for r in reviews):
        return "Review pending"
    if reviews and all(r.state == "Approved" for r in reviews):
        return "Export ready"
    return "No artifacts"


def _lifecycle(reviews: list[Review]) -> list[dict]:
    return [
        {
            "id": r.id,
            "name": r.title,
            "meta": f"{_type_label(r)} · {r.id}",
            "state": r.state,
            "icon": "doc" if r.artifact_type == "docx" else "deck",
        }
        for r in reviews
        if r.artifact_type in {"pptx", "docx"}
    ]


@router.get("/engagements")
def engagement_oversight(
    q: str = "",
    selected: str = "",
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    metas = _metas(db, [p.id for p in projects])
    reviews_by_project: dict[str, list[Review]] = {}
    for review in db.scalars(select(Review).where(Review.project_id.is_not(None))).all():
        reviews_by_project.setdefault(review.project_id, []).append(review)
    names = _names(db)
    member_counts: dict[str, int] = {}
    owners: dict[str, str] = {}
    for membership in db.scalars(select(Membership)).all():
        member_counts[membership.project_id] = member_counts.get(membership.project_id, 0) + 1
        if membership.role == "Owner":
            owners.setdefault(membership.project_id, names.get(membership.user_id, "—"))
    needle = q.strip().lower()
    rows = []
    for project in projects:
        meta = metas.get(project.id)
        reviews = reviews_by_project.get(project.id, [])
        code = _code(project.id, meta)
        if needle and needle not in f"{project.name} {code}".lower():
            continue
        in_review = sum(1 for r in reviews if r.state not in _OPEN)
        drafts = sum(1 for r in reviews if r.state == "Draft")
        rows.append(
            {
                "id": project.id,
                "name": project.name,
                "code": code,
                "ownerAccess": f"{owners.get(project.id, '—')} · {member_counts.get(project.id, 0)} members",
                "classification": ((meta.classification if meta else None) or "Internal").split(" · ")[0],
                "retention": _retention(meta),
                "deliverables": f"{in_review} in review · {drafts} draft" if reviews else "None yet",
                "controlState": _control_state(meta, reviews),
            }
        )
    chosen = next((p for p in projects if p.id == selected), projects[0] if projects else None)
    detail = None
    if chosen is not None:
        meta = metas.get(chosen.id)
        detail = {
            "id": chosen.id,
            "code": _code(chosen.id, meta),
            "name": chosen.name,
            "accessGroup": f"{member_counts.get(chosen.id, 0)} members · engagement-scoped",
            "contentAccess": "Not granted by administrative role",
            "retentionPolicy": _retention(meta),
            "retentionDays": (meta.retention_days if meta else None) or 180,
            "scheduledDisposition": (
                f"{format_date(meta.target_close)} + {meta.retention_days or 180} days"
                if meta and meta.target_close
                else "Set a target close date to schedule disposition"
            ),
            "status": (meta.status if meta else None) or "active",
            "members": [
                {"id": m["id"], "name": m["name"], "role": m["role"], "permission": m["permission"]}
                for m in _member_rows(db, chosen.id)
            ],
            "archiveReady": all(r.state in _OPEN for r in reviews_by_project.get(chosen.id, [])),
        }
    artifacts = [r for rs in reviews_by_project.values() for r in rs if r.artifact_type in {"pptx", "docx"}]
    project_names = {p.id: p.name for p in projects}
    exceptions = records(db, "retention_exceptions")
    requests = records(db, "export_requests")
    return {
        "tabCounts": {
            "engagements": len(projects),
            "deliverables": len(artifacts),
            "retentionExceptions": len(exceptions),
            "exportRequests": len(requests),
        },
        "matchingCount": len(rows),
        "totalCount": len(projects),
        "rows": rows,
        "selected": detail,
        "deliverableLifecycle": _lifecycle(reviews_by_project.get(chosen.id, [])) if chosen else [],
        "deliverables": [
            {
                "id": r.id,
                "name": r.title,
                "engagement": project_names.get(r.project_id or "", ""),
                "version": _type_label(r),
                "owner": names.get(r.owner_id or "", "—"),
                "state": r.state,
            }
            for r in artifacts
        ],
        "retentionExceptions": exceptions,
        "exportRequests": requests,
        "roles": list(MEMBER_ROLES),
    }


class ReasonedRequest(BaseModel):
    reason: str = Field(min_length=5, description="Every administrative change needs a recorded reason")


class RetentionRequest(ReasonedRequest):
    days: int = Field(ge=30, le=3650)


def _meta_for(db: Session, pid: str) -> EngagementMeta:
    if db.scalar(select(Project.id).where(Project.id == pid)) is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    meta = db.scalar(select(EngagementMeta).where(EngagementMeta.project_id == pid))
    if meta is None:
        meta = EngagementMeta(id=f"em_{pid}", project_id=pid)
        db.add(meta)
    return meta


def _admin_event(db: Session, admin: User, *, project_id: str | None, title: str, reason: str) -> None:
    record_activity(db, project_id=project_id, actor=display_name(admin), kind="admin", title=title,
                    detail=f"Reason: {reason}")


@router.post("/engagements/{pid}/retention")
def adjust_retention(
    pid: str, body: RetentionRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    meta = _meta_for(db, pid)
    meta.retention_days = body.days
    _admin_event(db, admin, project_id=pid, title=f"Retention set to {body.days} days after close", reason=body.reason)
    db.commit()
    return {"id": pid, "retentionDays": body.days}


@router.post("/engagements/{pid}/archive")
def archive_engagement(
    pid: str, body: ReasonedRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Archiving is refused while any artifact is still in review."""
    meta = _meta_for(db, pid)
    blocking = [r.id for r in db.scalars(select(Review).where(Review.project_id == pid)).all() if r.state not in _OPEN]
    if blocking:
        raise HTTPException(status_code=409, detail=f"Open reviews block archiving: {', '.join(blocking)}")
    meta.status = "archived"
    _admin_event(db, admin, project_id=pid, title="Engagement archived", reason=body.reason)
    db.commit()
    return {"id": pid, "status": "archived"}


class AdminMemberRequest(ReasonedRequest):
    email: str
    role: str


@router.post("/engagements/{pid}/members", status_code=201)
def admin_add_member(
    pid: str, body: AdminMemberRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Grant an organization account scoped access to an engagement. This does not grant the administrator access."""
    _meta_for(db, pid)
    if body.role not in MEMBER_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {', '.join(MEMBER_ROLES)}")
    member = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if member is None:
        raise HTTPException(status_code=404, detail="No organization account with that email")
    if db.scalar(select(Membership).where(Membership.project_id == pid, Membership.user_id == member.id)):
        raise HTTPException(status_code=409, detail="Already a member of this engagement")
    membership = Membership(id=f"m_{pid[-6:]}_{member.id[-8:]}", project_id=pid, user_id=member.id,
                            role=MEMBER_ROLES[body.role][0])
    db.add(membership)
    _set_member_title(db, pid, membership.id, body.role)
    _admin_event(db, admin, project_id=pid, title=f"{display_name(member)} added as {body.role}", reason=body.reason)
    db.commit()
    return {"id": membership.id}


@router.get("/library")
def library_management(
    practice: str = "", admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Library pipeline for one practice: its latest upload when it has one, otherwise the sample walkthrough."""
    screen = {**_library_sample(), **_screen(db, "admin_library")}
    inventory = admin_library.inventory_rows(db)
    sections = admin_library.library_sections(db, practice.strip().lower() or None)
    view = {
        **screen,
        "selectedPracticeId": screen.get("qualityReview", {}).get("id", ""),
        "pipelineSource": "sample",
        **(sections or {}),
        "practiceInventoryTotal": f"{len(inventory)} practices",
        "practiceInventory": inventory,
        "ingestionJobs": admin_library.job_table_rows(db),
    }
    # Ingestion pipeline: the selected practice's latest upload (same object as each inventory row's
    # ``ingestion`` and /api/admin/library/documents/status/{job_id}), and uploads not yet attached to a practice.
    view["ingestion"] = admin_library.ingestion_for_practice(db, view.get("selectedPracticeId") or None)
    view["pendingUploads"] = admin_library.pending_uploads(db)
    return view


def _practice_review(db: Session, practice_id: str) -> tuple[LpPractice, Review | None]:
    practice = db.scalar(select(LpPractice).where(LpPractice.id == practice_id.lower()))
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    review = db.scalar(select(Review).where(Review.id == practice.id.upper(), Review.artifact_type == "practice"))
    return practice, review


class CorrectionRequest(ReasonedRequest):
    """`reason` is the required correction; the rest locates it for the practice owner."""

    assignee: str = Field(default="", max_length=120)
    source_location: str = Field(default="", max_length=300)
    severity: str = Field(default="", max_length=120)
    due: str = Field(default="", max_length=40)


@router.post("/library/{practice_id}/request-correction")
def request_practice_correction(
    practice_id: str, body: CorrectionRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    practice, review = _practice_review(db, practice_id)
    if practice.status != "Approved":  # a live practice stays served while its next version is corrected
        practice.status = "Correction requested"
    correction_id = f"CR-{practice.id.split('-')[-1].upper()}"
    detail = " · ".join(
        part
        for part in (
            body.source_location,
            body.severity,
            f"Assigned to {body.assignee}" if body.assignee else "",
            f"Due {body.due}" if body.due else "",
        )
        if part
    )
    message = f"{body.reason}\n{detail}" if detail else body.reason
    admin_library.record_correction(db, practice.id, {
        "id": correction_id, "reason": body.reason, "assignee": body.assignee, "sourceLocation": body.source_location,
        "severity": body.severity, "due": body.due, "requestedBy": display_name(admin),
    })
    if review is not None:
        review.state = "Changes requested"
        _notify(db, review.owner_id, kind="review", title=f"{correction_id} correction requested: {practice.title}",
                body=message, link=f"/reviews/{review.id}")
    _admin_event(db, admin, project_id=None, title=f"{correction_id} requested on {practice.id.upper()}", reason=message)
    db.commit()
    return {"id": practice.id, "status": practice.status, "correctionId": correction_id}


@router.post("/library/{practice_id}/publish")
def publish_practice(
    practice_id: str, body: ReasonedRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Publish only after the assigned approver has approved this version."""
    practice, review = _practice_review(db, practice_id)
    if review is None or review.state != "Approved":
        state = review.state if review else "not submitted for review"
        raise HTTPException(
            status_code=409,
            detail=f"{practice.id.upper()} cannot be published: its independent review is {state.lower()}.",
        )
    admin_library.release(db, practice, review, admin)
    practice.status = "Approved"
    practice.updated_at = utcnow()
    _admin_event(db, admin, project_id=None, title=f"{practice.id.upper()} {practice.version_label} published",
                 reason=body.reason)
    db.commit()
    return {"id": practice.id, "status": practice.status}


@router.get("/skills")
def skills_management(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return _screen(db, "admin_skills", required=True)


class SkillCandidateRequest(BaseModel):
    instruction_contract: list[str] = Field(alias="instructionContract", min_length=1)
    retrieval_scope: str = Field(alias="retrievalScope", min_length=3)
    evidence_threshold: str = Field(alias="evidenceThreshold", min_length=1)
    changelog: str = Field(min_length=5)

    model_config = {"populate_by_name": True}


@router.put("/skills/{skill_id}/candidate")
def save_skill_candidate(
    skill_id: str, body: SkillCandidateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Save the candidate definition. Published versions are immutable and are not touched."""
    screen = _screen(db, "admin_skills", required=True)
    definition = screen.get("definition", {})
    if definition.get("id") != skill_id:
        raise HTTPException(status_code=404, detail="No candidate definition for that skill")
    definition.update(
        {
            "instructionContract": [line.strip() for line in body.instruction_contract if line.strip()],
            "retrievalScope": body.retrieval_scope.strip(),
            "evidenceThreshold": body.evidence_threshold.strip(),
            "changelog": body.changelog.strip(),
            "approvalState": "Candidate saved · tests required",
        }
    )
    screen["definition"] = definition
    _save_screen(db, "admin_skills", screen)
    _admin_event(db, admin, project_id=None, title=f"{definition.get('code', skill_id)} candidate saved",
                 reason=body.changelog)
    db.commit()
    return screen


@router.post("/skills/{skill_id}/publish")
def publish_skill(
    skill_id: str, body: ReasonedRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Publish only when the stored tests pass and the independent reviewer approved the release."""
    screen = _screen(db, "admin_skills", required=True)
    tests = screen.get("testResults", {})
    if tests.get("passCount") != tests.get("totalCount"):
        raise HTTPException(status_code=409, detail="Tests must pass before a skill version can be published")
    review = db.scalar(select(Review).where(Review.id == skill_id.upper(), Review.artifact_type == "skill"))
    if review is None or review.state != "Approved":
        raise HTTPException(status_code=409, detail="The independent reviewer has not approved this release")
    _admin_event(db, admin, project_id=None, title=f"{skill_id.upper()} {review.version_label} published",
                 reason=body.reason)
    db.commit()
    return {"id": skill_id, "published": True}


@router.get("/reviews")
def review_governance(
    selected: str = "", admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    screen = _screen(db, "admin_reviews")
    names = _names(db)
    queue = _open_reviews(db)
    chosen = next((r for r in queue if r.id == selected), queue[0] if queue else None)
    risks = _screen(db, "overview").get("riskQueue", [])
    detail = None
    if chosen is not None:
        detail = {
            "id": chosen.id,
            "code": chosen.id,
            "title": chosen.title,
            "riskLevel": chosen.risk or "Low risk",
            "badges": [chosen.state, "Export locked"],
            "artifactOwner": f"{_type_label(chosen)} · {names.get(chosen.owner_id or '', '—')}",
            "assignedApprover": f"{names.get(chosen.reviewer_id or '', 'Unassigned')} · Due "
            f"{format_date(chosen.due_date, year=False)}",
            "reviewerId": chosen.reviewer_id,
            "ownerId": chosen.owner_id,
            "riskDescription": f"Current state: {chosen.state}. The assigned approver must resolve it before "
            "this version can be released.",
            "warning": {
                "title": "Approval is version-specific",
                "description": "Approval cannot carry over from a prior version or be granted by the artifact author.",
            },
            "footnote": "Your role: administrator. Approval decisions are restricted to the assigned independent reviewer.",
        }
    return {
        "tabCounts": {
            "reviewQueue": len(queue),
            "riskRegister": len(risks),
            "policies": len(screen.get("policyControls", [])),
        },
        "queue": [
            {
                "id": r.id,
                "itemReference": f"{r.title} · {r.id}",
                "reviewer": names.get(r.reviewer_id or "", "Unassigned"),
                "type": _type_label(r),
                "state": r.state,
                "due": format_date(r.due_date, year=False),
            }
            for r in queue
        ],
        "selectedReview": detail,
        "policyControls": screen.get("policyControls", []),
        "policyCode": screen.get("policyCode", ""),
        "exportPermissionsNote": screen.get("exportPermissionsNote", ""),
        "roleAccess": screen.get("roleAccess", []),
        "auditTrail": _audit(db, 4),
        "risks": risks,
        "fullAuditTrail": _audit(db, 100),
        "reviewers": [{"id": uid, "name": name} for uid, name in sorted(names.items(), key=lambda item: item[1])],
    }


class AssignReviewerRequest(ReasonedRequest):
    reviewer_id: str = Field(alias="reviewerId")

    model_config = {"populate_by_name": True}


@router.post("/reviews/{review_id}/assign")
def assign_reviewer(
    review_id: str, body: AssignReviewerRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Route a review to an independent reviewer. The artifact's owner cannot be its reviewer."""
    review = db.scalar(select(Review).where(Review.id == review_id))
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    reviewer = db.scalar(select(User).where(User.id == body.reviewer_id))
    if reviewer is None:
        raise HTTPException(status_code=404, detail="Reviewer not found")
    if reviewer.id == review.owner_id:
        raise HTTPException(status_code=422, detail="The artifact owner cannot review their own work")
    review.reviewer_id = reviewer.id
    review.updated_at = utcnow()
    _admin_event(db, admin, project_id=review.project_id,
                 title=f"{review.id} assigned to {display_name(reviewer)}", reason=body.reason)
    _notify(db, reviewer.id, kind="review", title=f"{review.title} assigned to you",
            body=f"{review.id} · Routed by {display_name(admin)}", link=f"/reviews/{review.id}")
    db.commit()
    return {"id": review.id, "reviewer": display_name(reviewer)}


@router.post("/export-requests/{request_id}/approve")
def approve_export_request(
    request_id: str, body: ReasonedRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Release a package only when its artifact version has independent approval. Content gates cannot be overridden."""
    row = db.scalar(
        select(WorkbenchRecord).where(
            WorkbenchRecord.collection == "export_requests", WorkbenchRecord.record_id == request_id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Export request not found")
    payload = json.loads(row.payload_json or "{}")
    review = db.scalar(select(Review).where(Review.id == payload.get("reviewId", "")))
    if review is None or review.state != "Approved":
        state = review.state.lower() if review else "missing"
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve the current version: review {payload.get('reviewId', '')} is {state}. "
            "An administrator cannot override content gates.",
        )
    payload["state"] = "Released"
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.updated_at = utcnow()
    _admin_event(db, admin, project_id=review.project_id, title=f"Export {request_id} approved", reason=body.reason)
    db.commit()
    return {"id": request_id, "state": "Released"}


def _csv(headers: list[str], rows: list[list[str]], filename: str) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/{name}.csv")
def export_csv(name: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    if name == "engagements":
        data = engagement_oversight(q="", selected="", admin=admin, db=db)
        rows = [
            [r["code"], r["name"], r["ownerAccess"], r["classification"], r["retention"], r["deliverables"],
             r["controlState"]]
            for r in data["rows"]
        ]
        headers = ["Code", "Engagement", "Owner / access", "Classification", "Retention", "Deliverables", "Control state"]
    elif name == "audit":
        rows = [[e["title"], e["attribution"]] for e in _audit(db, 1000)]
        headers = ["Event", "Attribution"]
    elif name == "reviews":
        names = _names(db)
        rows = [
            [r.id, r.title, _type_label(r), names.get(r.owner_id or "", ""), names.get(r.reviewer_id or "", ""),
             r.due_date, r.state]
            for r in db.scalars(select(Review).order_by(Review.id)).all()
        ]
        headers = ["Reference", "Item", "Type / version", "Owner", "Reviewer", "Due", "State"]
    else:
        raise HTTPException(status_code=404, detail="Unknown export")
    _admin_event(db, admin, project_id=None, title=f"Exported {name} report", reason="Administrative export")
    db.commit()
    return _csv(headers, rows, f"advise-workbench-{name}.csv")
