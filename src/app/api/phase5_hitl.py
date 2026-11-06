"""Phase 5 HITL Review API endpoints for artifact approval/rejection.

While a run waits in design review, project members can read its artifacts' approval state; Owners and
Editors approve every artifact or send one back for regeneration (a deck slide by slide).
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.auth import get_current_user, require_project_role
from src.core.db.models import ArtifactApprovalRecord, Run, User, utcnow
from src.core.db.session import get_db
from src.workflows.phase5_rejection_handler import (
    DEFAULT_FEEDBACK,
    MAX_REJECTIONS,
    queue_phase3_regeneration,
    rejections_used,
)

router = APIRouter(prefix="/api/runs", tags=["phase5"])

_READ_ROLES = {"Owner", "Editor", "Viewer"}
_DECIDE_ROLES = {"Owner", "Editor"}


class RejectRequest(BaseModel):
    """Request to reject artifact(s) for regeneration."""
    artifact_type: str  # pptx, docx, xlsx, pdf, sop, narrative, drawio
    rejected_slides: list[int] | None = None  # None = full reject, [2, 4] = partial
    approved_slides: list[int] | None = None  # For PPTX partial reject
    user_feedback: str | None = Field(default=None, max_length=2000)


class ApprovalResponse(BaseModel):
    """Response from approval/rejection endpoints."""
    status: str
    message: str
    new_version: str | None = None
    attempt: str | None = None  # rejections used, e.g. "1/3"


class ApprovalStatusResponse(BaseModel):
    """Current approval state for an artifact."""
    artifact_type: str
    version: str
    status: str
    attempt_count: int
    rejections_used: int
    max_rejections: int
    is_current: bool
    approved_slides: list[int]
    rejected_slides: list[int]
    total_slides: int | None = None


def _run_for(run_id: str, roles: set[str], user: User, db: Session) -> Run:
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    require_project_role(run.project_id, roles, user, db)
    return run


def _require_waiting(run: Run) -> None:
    # Decisions only count while the run's Phase 5 is waiting for them.
    if run.phase_5_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This run is not waiting for design review",
        )


def _current(db: Session, run_id: str) -> list[ArtifactApprovalRecord]:
    return (
        db.query(ArtifactApprovalRecord)
        .filter(ArtifactApprovalRecord.run_id == run_id, ArtifactApprovalRecord.is_current == True)  # noqa: E712
        .all()
    )


def _status_of(a: ArtifactApprovalRecord) -> ApprovalStatusResponse:
    return ApprovalStatusResponse(
        artifact_type=a.artifact_type,
        version=a.version,
        status=a.status,
        attempt_count=a.attempt_count,
        rejections_used=rejections_used(a.attempt_count),
        max_rejections=MAX_REJECTIONS,
        is_current=a.is_current,
        approved_slides=json.loads(a.approved_slides or "[]"),
        rejected_slides=json.loads(a.rejected_slides or "[]"),
        total_slides=a.total_slides,
    )


@router.post("/{run_id}/phase5/approve-all", response_model=ApprovalResponse)
def approve_all(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve every artifact's current version; the waiting run moves on to Phase 6 (Remember)."""
    run = _run_for(run_id, _DECIDE_ROLES, user, db)
    _require_waiting(run)
    approvals = _current(db, run_id)
    if not approvals:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No artifacts to approve")
    if any(a.status == "regenerating" for a in approvals):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An artifact is still being regenerated; approve once it is ready",
        )

    for approval in approvals:
        approval.status = "approved"
        approval.is_immutable = True
        approval.updated_at = utcnow()
    run.phase_5_status = "approved"
    db.commit()

    return ApprovalResponse(status="ok", message=f"All {len(approvals)} artifact(s) approved. Moving to Phase 6.")


class ApproveRequest(BaseModel):
    artifact_type: str


@router.post("/{run_id}/phase5/approve", response_model=ApprovalResponse)
def approve_artifact(
    run_id: str,
    request: ApproveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve one artifact's current version. Once every artifact is approved the run moves on to Phase 6."""
    run = _run_for(run_id, _DECIDE_ROLES, user, db)
    _require_waiting(run)
    approvals = _current(db, run_id)
    approval = next((a for a in approvals if a.artifact_type == request.artifact_type), None)
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No current approval record for {request.artifact_type}",
        )
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{request.artifact_type.upper()} is {approval.status}; only a version awaiting review can be approved",
        )

    approval.status = "approved"
    approval.is_immutable = True
    approval.updated_at = utcnow()
    remaining = [a.artifact_type for a in approvals if a.status != "approved"]
    if not remaining:
        run.phase_5_status = "approved"
    db.commit()

    if remaining:
        return ApprovalResponse(
            status="ok",
            message=f"{request.artifact_type.upper()} approved. Still awaiting: {', '.join(t.upper() for t in remaining)}.",
        )
    return ApprovalResponse(status="ok", message="Every artifact is approved. Moving to Phase 6.")


@router.post("/{run_id}/phase5/reject", response_model=ApprovalResponse)
def submit_rejection(
    run_id: str,
    request: RejectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reject an artifact's current version: record a new version and have the waiting run regenerate it.

    For PPTX partial reject:
    - rejected_slides: [2, 4] → regenerate only these slides
    - approved_slides: [1, 3, 5] → keep these unchanged

    For full reject:
    - rejected_slides: null → regenerate entire artifact
    """
    run = _run_for(run_id, _DECIDE_ROLES, user, db)
    _require_waiting(run)

    current_approval = (
        db.query(ArtifactApprovalRecord)
        .filter(
            ArtifactApprovalRecord.run_id == run_id,
            ArtifactApprovalRecord.artifact_type == request.artifact_type,
            ArtifactApprovalRecord.is_current == True,  # noqa: E712
        )
        .first()
    )
    if not current_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No current approval record for {request.artifact_type}",
        )
    if current_approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{request.artifact_type.upper()} is {current_approval.status}; only a version awaiting review can be rejected",
        )
    used = rejections_used(current_approval.attempt_count)
    if used >= MAX_REJECTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Max rejections ({MAX_REJECTIONS}/{MAX_REJECTIONS}) reached for {request.artifact_type.upper()}. Must approve.",
        )

    # Only a deck can be rejected slide by slide; anything else, or every slide chosen, is a full rebuild.
    slides = sorted({n for n in request.rejected_slides or [] if n >= 1})
    total = current_approval.total_slides
    if total:
        slides = [n for n in slides if n <= total]
    partial = request.artifact_type == "pptx" and bool(slides) and not (total and len(slides) >= total)
    rejected_slides = slides if partial else []
    if not partial:
        approved_slides: list[int] = []
    elif total:
        approved_slides = [n for n in range(1, total + 1) if n not in slides]
    else:
        approved_slides = sorted(set(request.approved_slides or []) - set(slides))
    feedback = (request.user_feedback or "").strip()

    new_version = f"v{int(current_approval.version[1:]) + 1}"
    current_approval.is_current = False
    current_approval.is_immutable = True
    current_approval.replaced_by = new_version
    current_approval.replaced_at = utcnow()

    new_attempt = current_approval.attempt_count + 1
    db.add(
        ArtifactApprovalRecord(
            id=str(uuid.uuid4()),
            run_id=run_id,
            project_id=run.project_id,
            artifact_type=request.artifact_type,
            version=new_version,
            is_current=True,
            is_immutable=False,
            status="regenerating",
            attempt_count=new_attempt,
            total_slides=total,
            approved_slides=json.dumps(approved_slides),
            rejected_slides=json.dumps(rejected_slides),
            user_feedback=feedback or None,
            rejected_by=user.id,
            rejected_at=utcnow(),
        )
    )
    queue_phase3_regeneration(
        run_id=run_id,
        artifact_type=request.artifact_type,
        rejected_slides=rejected_slides or None,
        approved_slides=approved_slides or None,
        new_version=new_version,
        rejection_type="partial" if partial else "full",
        feedback=feedback or DEFAULT_FEEDBACK,
        session=db,
    )
    db.commit()

    return ApprovalResponse(
        status="regenerating",
        message=f"{request.artifact_type.upper()} queued for regeneration",
        new_version=new_version,
        attempt=f"{used + 1}/{MAX_REJECTIONS}",
    )


@router.get("/{run_id}/phase5/approval-status/{artifact_type}", response_model=ApprovalStatusResponse)
def get_approval_status(
    run_id: str,
    artifact_type: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current approval state for an artifact."""
    _run_for(run_id, _READ_ROLES, user, db)
    approval = next((a for a in _current(db, run_id) if a.artifact_type == artifact_type), None)
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approval record for {artifact_type} in run {run_id}",
        )
    return _status_of(approval)


@router.get("/{run_id}/phase5/approval-status")
def get_all_approval_status(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get approval status for all artifacts in this run, and whether the run is waiting for a decision."""
    run = _run_for(run_id, _READ_ROLES, user, db)
    approvals = _current(db, run_id)
    if not approvals:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No approvals found for run {run_id}")
    return {
        "run_id": run_id,
        "phase_5_status": run.phase_5_status,
        "max_rejections": MAX_REJECTIONS,
        "artifacts": [_status_of(a).model_dump() for a in approvals],
    }
