"""Reviews API: the queue, one review's detail, comments, revisions and the approval decision.

A review covers one artifact version. Engagement artifacts (PPTX, DOCX) belong
to a project and follow its membership; practice, skill and access reviews have
no project and are visible to their owner, their reviewer and administrators.
The reviewer is any member of the engagement. An author may review their own artifact (a
solo engagement needs this); the approval is then recorded as a self-review in the timeline
and audit trail so it stays visible to governance.
"""

from __future__ import annotations

import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.api.engagements import (
    STAGES,
    display_name,
    format_date,
    format_timestamp,
    member_project_ids,
    record_activity,
)
from src.core.auth import get_current_user, require_project_role
from src.core.db.models import (
    EngagementMeta,
    Membership,
    Notification,
    Project,
    Review,
    ReviewComment,
    Run,
    User,
    utcnow,
)
from src.core.db.session import get_db

router = APIRouter()

_READ = {"Owner", "Editor", "Viewer"}
_STEP_LABELS = ["Brief", "Sources", "Draft", "Review", "Export"]


def _users(db: Session) -> dict[str, User]:
    return {u.id: u for u in db.scalars(select(User)).all()}


def _is_admin(db: Session, user: User) -> bool:
    row = db.scalar(select(User).where(User.id == user.id))
    return bool(row and row.is_admin)


def _visible_reviews(db: Session, user: User) -> list[Review]:
    project_ids = member_project_ids(db, user)
    reviews = db.scalars(select(Review).order_by(Review.due_date, Review.id)).all()
    if _is_admin(db, user):
        return list(reviews)
    return [r for r in reviews if r.project_id in project_ids or user.id in (r.owner_id, r.reviewer_id)]


def _load(db: Session, review_id: str, user: User) -> Review:
    review = db.scalar(select(Review).where(Review.id == review_id))
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if user.id in (review.owner_id, review.reviewer_id) or _is_admin(db, user):
        return review
    if review.project_id:
        require_project_role(review.project_id, _READ, user, db)
        return review
    raise HTTPException(status_code=403, detail="You do not have access to this review")


def _type_label(review: Review) -> str:
    kind = {"pptx": "PPTX", "docx": "DOCX", "practice": "Practice", "skill": "Skill", "access": "Source access"}
    return f"{kind.get(review.artifact_type, review.artifact_type)} {review.version_label}".strip()


def _row(review: Review, users: dict[str, User], engagement: str) -> dict:
    return {
        "id": review.id,
        "title": review.title,
        "itemReference": f"{review.title} · {review.id}",
        "engagement": engagement,
        "projectId": review.project_id,
        "type": _type_label(review),
        "owner": display_name(users.get(review.owner_id or "")),
        "reviewer": display_name(users.get(review.reviewer_id or "")),
        "dueDate": format_date(review.due_date, year=False),
        "state": review.state,
        "risk": review.risk,
    }


@router.get("")
def list_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    reviews = [r for r in _visible_reviews(db, user) if r.state != "Draft"]
    users = _users(db)
    names = dict(db.execute(select(Project.id, Project.name)).all())
    rows = [_row(r, users, names.get(r.project_id or "", "Platform")) for r in reviews]
    mine = [r.id for r in reviews if user.id in (r.owner_id, r.reviewer_id) and r.state != "Approved"]
    return {"items": rows, "mine": mine, "total": len(rows)}


def _steps(state: str) -> list[dict]:
    current = 4 if state == "Approved" else 3
    steps = []
    for i, label in enumerate(_STEP_LABELS):
        status = "complete" if i < current else "in-progress" if i == current else "upcoming"
        helper = {"complete": "Complete", "in-progress": "In progress", "upcoming": "Upcoming"}[status]
        steps.append({"id": label.lower(), "index": i + 1, "label": label, "status": status, "helper": helper})
    return steps


def _comment(comment: ReviewComment) -> dict:
    attribution = f"{comment.author} · {format_timestamp(comment.created_at)}"
    return {
        "id": str(comment.id),
        "title": comment.title or "Comment",
        "status": comment.status,
        "attribution": f"{attribution} · {comment.anchor}" if comment.anchor else attribution,
        "body": comment.body,
    }


@router.get("/{review_id}")
def get_review(review_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    review = _load(db, review_id, user)
    users = _users(db)
    payload = json.loads(review.payload_json or "{}")
    comments = db.scalars(
        select(ReviewComment).where(ReviewComment.review_id == review.id).order_by(ReviewComment.id)
    ).all()
    open_count = sum(1 for c in comments if c.status == "Open")
    project = db.scalar(select(Project).where(Project.id == review.project_id)) if review.project_id else None
    is_owner, is_reviewer = user.id == review.owner_id, user.id == review.reviewer_id
    return {
        "id": review.id,
        "code": review.id,
        "projectId": review.project_id,
        "runId": review.run_id,
        "engagementName": project.name if project else "Platform",
        "artifactName": review.title,
        "artifactType": review.artifact_type,
        "versionLabel": _type_label(review),
        "owner": display_name(users.get(review.owner_id or "")),
        "reviewer": display_name(users.get(review.reviewer_id or "")),
        "dueDate": format_date(review.due_date),
        "state": review.state,
        "steps": _steps(review.state),
        "slide": payload.get("slide"),
        "slideCommentCount": open_count,
        "evidenceChecksRunMeta": payload.get("evidenceChecksRunMeta", ""),
        "evidenceChecks": payload.get("evidenceChecks", []),
        "comments": [_comment(c) for c in comments],
        "openCount": open_count,
        "resolvedCount": len(comments) - open_count,
        "approverName": display_name(users.get(review.reviewer_id or "")),
        "approverRole": (users[review.reviewer_id].job_title if review.reviewer_id in users else "") or "Reviewer",
        "approvalStatus": review.state,
        "approvalTimeline": payload.get("approvalTimeline", []),
        "canRevise": is_owner and review.state == "Changes requested",
        "canDecide": is_reviewer and review.state not in {"Approved", "Changes requested", "Draft"},
        "selfReview": review.owner_id is not None and review.owner_id == review.reviewer_id,
        "canComment": is_reviewer or is_owner,
    }


def _notify(db: Session, user_id: str | None, *, kind: str, title: str, body: str, link: str) -> None:
    if user_id:
        db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, link=link))


def _timeline(review: Review, title: str, actor: str, icon: str) -> None:
    payload = json.loads(review.payload_json or "{}")
    events = payload.get("approvalTimeline", [])
    events.append(
        {"id": uuid.uuid4().hex[:8], "title": title, "attribution": f"{actor} · {format_timestamp(utcnow())}", "icon": icon}
    )
    payload["approvalTimeline"] = events
    review.payload_json = json.dumps(payload, ensure_ascii=False)
    review.updated_at = utcnow()


def _set_stage(db: Session, project_id: str | None, stage: str) -> None:
    if not project_id:
        return
    meta = db.scalar(select(EngagementMeta).where(EngagementMeta.project_id == project_id))
    if meta is not None and stage in STAGES:
        meta.stage = stage


class CreateReviewRequest(BaseModel):
    project_id: str = Field(alias="projectId")
    run_id: str = Field(alias="runId")
    artifact_type: str = Field(alias="artifactType", pattern="^(pptx|docx)$")
    title: str = Field(min_length=3, max_length=255)
    reviewer_id: str = Field(alias="reviewerId")
    due_date: str = Field("", alias="dueDate", max_length=32)

    model_config = {"populate_by_name": True}


@router.post("", status_code=201)
def submit_for_review(
    body: CreateReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Submit a run's artifact for review. The reviewer is any member, including the author."""
    require_project_role(body.project_id, {"Owner", "Editor"}, user, db)
    run = db.scalar(select(Run).where(Run.id == body.run_id, Run.project_id == body.project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    is_member = db.scalar(
        select(Membership).where(Membership.project_id == body.project_id, Membership.user_id == body.reviewer_id)
    )
    if is_member is None:
        raise HTTPException(status_code=422, detail="The reviewer must be a member of this engagement")
    existing = db.scalar(
        select(Review).where(Review.run_id == body.run_id, Review.artifact_type == body.artifact_type)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"This artifact is already in review as {existing.id}")
    number = (db.scalar(select(func.count()).select_from(Review)) or 0) + 101
    review = Review(
        id=f"RV-{number}-{uuid.uuid4().hex[:4]}",
        project_id=body.project_id,
        run_id=body.run_id,
        title=body.title.strip(),
        artifact_type=body.artifact_type,
        version_label="v0.1",
        owner_id=user.id,
        reviewer_id=body.reviewer_id,
        due_date=body.due_date,
        state="Awaiting review",
    )
    db.add(review)
    _timeline(review, "Submitted for review", display_name(user), "edit")
    _set_stage(db, body.project_id, "In review")
    record_activity(db, project_id=body.project_id, actor=display_name(user), kind="review",
                    title=f"{review.title} submitted for review", detail=review.id)
    if body.reviewer_id != user.id:
        _notify(db, body.reviewer_id, kind="review", title=f"{review.title} assigned to you",
                body=f"{review.id} · Submitted by {display_name(user)}", link=f"/reviews/{review.id}")
    db.commit()
    return {"id": review.id}


class CommentRequest(BaseModel):
    title: str = Field("", max_length=255)
    body: str = Field(min_length=3)
    anchor: str = Field("", max_length=64)


@router.post("/{review_id}/comments", status_code=201)
def add_comment(
    review_id: str,
    body: CommentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    review = _load(db, review_id, user)
    if user.id not in (review.owner_id, review.reviewer_id):
        raise HTTPException(status_code=403, detail="Only the owner and the assigned reviewer can comment")
    comment = ReviewComment(
        review_id=review.id, author=display_name(user), title=body.title.strip(), body=body.body.strip(), anchor=body.anchor
    )
    db.add(comment)
    other = review.owner_id if user.id == review.reviewer_id else review.reviewer_id
    _notify(db, other, kind="mention", title=f"{display_name(user)} commented on {review.id}",
            body=body.body.strip()[:200], link=f"/reviews/{review.id}")
    db.commit()
    return {"id": str(comment.id)}


@router.post("/{review_id}/comments/{comment_id}/resolve")
def resolve_comment(
    review_id: str,
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    review = _load(db, review_id, user)
    if user.id not in (review.owner_id, review.reviewer_id):
        raise HTTPException(status_code=403, detail="Only the owner and the assigned reviewer can resolve comments")
    comment = db.scalar(
        select(ReviewComment).where(ReviewComment.id == comment_id, ReviewComment.review_id == review.id)
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    comment.status = "Resolved"
    _timeline(review, f"Comment addressed: {comment.title or 'Comment'}", display_name(user), "check")
    db.commit()
    return {"id": str(comment.id), "status": comment.status}


def _next_version(label: str) -> str:
    match = re.fullmatch(r"v(\d+)\.(\d+)", label.strip())
    return f"v{match.group(1)}.{int(match.group(2)) + 1}" if match else label


class RevisionRequest(BaseModel):
    note: str = ""


@router.post("/{review_id}/submit-revision")
def submit_revision(
    review_id: str,
    body: RevisionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """The owner resubmits after addressing every comment; the version moves on and review restarts."""
    review = _load(db, review_id, user)
    if user.id != review.owner_id:
        raise HTTPException(status_code=403, detail="Only the artifact owner can submit a revision")
    if review.state != "Changes requested":
        raise HTTPException(status_code=409, detail="A revision can be submitted only after changes are requested")
    open_comments = db.scalar(
        select(func.count()).select_from(ReviewComment).where(
            ReviewComment.review_id == review.id, ReviewComment.status == "Open"
        )
    )
    if open_comments:
        raise HTTPException(status_code=409, detail=f"Address the {open_comments} open comment(s) before resubmitting")
    review.version_label = _next_version(review.version_label)
    review.state = "In review"
    _timeline(review, f"Revised {_type_label(review)} submitted", display_name(user), "edit")
    record_activity(db, project_id=review.project_id, actor=display_name(user), kind="review",
                    title=f"{review.title} {review.version_label} submitted", detail=body.note or review.id)
    _notify(db, review.reviewer_id, kind="review", title=f"Revised draft ready: {review.title}",
            body=f"{review.id} · {_type_label(review)}", link=f"/reviews/{review.id}")
    db.commit()
    return {"id": review.id, "state": review.state, "versionLabel": _type_label(review)}


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|request_changes)$")
    note: str = ""


@router.post("/{review_id}/decision")
def decide(
    review_id: str,
    body: DecisionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Only the assigned reviewer decides. When that is the author, the decision is recorded as a self-review."""
    review = _load(db, review_id, user)
    if user.id != review.reviewer_id:
        raise HTTPException(status_code=403, detail="Only the assigned reviewer can approve or request changes")
    self_review = user.id == review.owner_id
    if review.state in {"Approved", "Draft"}:
        raise HTTPException(status_code=409, detail=f"This review is already {review.state.lower()}")
    actor = display_name(user)
    if body.decision == "approve":
        open_comments = db.scalar(
            select(func.count()).select_from(ReviewComment).where(
                ReviewComment.review_id == review.id, ReviewComment.status == "Open"
            )
        )
        if open_comments:
            raise HTTPException(status_code=409, detail="Resolve the open comments before approving")
        review.state = "Approved"
        _timeline(review, f"{'Self-approved' if self_review else 'Approved'} {_type_label(review)}", actor, "check")
        if review.project_id:
            others = db.scalars(
                select(Review).where(Review.project_id == review.project_id, Review.id != review.id)
            ).all()
            if all(r.state == "Approved" for r in others):
                _set_stage(db, review.project_id, "Approved")
    else:
        if not body.note.strip():
            raise HTTPException(status_code=422, detail="Say what needs to change")
        review.state = "Changes requested"
        db.add(ReviewComment(review_id=review.id, author=actor, title="Changes requested", body=body.note.strip()))
        _timeline(review, "Changes requested", actor, "comment")
        _set_stage(db, review.project_id, "Drafting")
    record_activity(db, project_id=review.project_id, actor=actor, kind="review",
                    title=f"{review.title}: {review.state}",
                    detail=f"{review.id} · Self-review by the author" if self_review else review.id)
    if not self_review:
        _notify(db, review.owner_id, kind="review", title=f"{review.state}: {review.title}",
                body=f"{review.id} · {actor}", link=f"/reviews/{review.id}")
    db.commit()
    return {"id": review.id, "state": review.state}
