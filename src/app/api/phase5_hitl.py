"""Phase 5 HITL Review API endpoints for artifact approval/rejection."""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.auth import get_current_user
from src.core.db.models import Run, ArtifactApprovalRecord, utcnow
from src.core.db.session import SessionLocal
from src.workflows.phase5_rejection_handler import queue_phase3_regeneration

router = APIRouter(prefix="/api/runs", tags=["phase5"])


class RejectRequest(BaseModel):
    """Request to reject artifact(s) for regeneration."""
    artifact_type: str  # pptx, docx, xlsx, pdf, sop, narrative, drawio
    rejected_slides: Optional[list[int]] = None  # None = full reject, [2, 4] = partial
    approved_slides: Optional[list[int]] = None  # For PPTX partial reject
    user_feedback: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Response from approval/rejection endpoints."""
    status: str
    message: str
    new_version: Optional[str] = None
    attempt: Optional[str] = None  # e.g., "1/3"


class ApprovalStatusResponse(BaseModel):
    """Current approval state for an artifact."""
    artifact_type: str
    version: str
    status: str
    attempt_count: int
    is_current: bool
    approved_slides: list[int]
    rejected_slides: list[int]
    total_slides: Optional[int] = None


def get_session() -> Session:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{run_id}/phase5/approve-all", response_model=ApprovalResponse)
async def approve_all(
    run_id: str,
    session: Session = Depends(get_session),
    # current_user: str = Depends(get_current_user),  # TODO: re-enable after testing
):
    """
    User approves all artifacts → move to Phase 6 (Remember).

    Marks all current approval records as approved + immutable.
    Sets Run.phase_5_status = "approved".
    """
    print(f"\n[PHASE5-API] POST /phase5/approve-all called")
    print(f"[PHASE5-API]   run_id: {run_id}")
    # print(f"[PHASE5-API]   user: {current_user}")  # TODO: re-enable after testing

    run = session.query(Run).filter(Run.id == run_id).first()
    if not run:
        print(f"[PHASE5-API] ERROR: Run {run_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )

    print(f"[PHASE5-API] Found run, status: {run.phase_5_status}")

    # Mark all current artifacts as approved + immutable
    approvals = session.query(ArtifactApprovalRecord).filter(
        ArtifactApprovalRecord.run_id == run_id,
        ArtifactApprovalRecord.is_current == True
    ).all()

    print(f"[PHASE5-API] Found {len(approvals)} artifacts to approve")

    if not approvals:
        print(f"[PHASE5-API] ERROR: No artifacts found for approval")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No artifacts to approve"
        )

    for approval in approvals:
        approval.status = "approved"
        approval.is_immutable = True
        approval.updated_at = utcnow()

    run.phase_5_status = "approved"
    session.commit()

    return ApprovalResponse(
        status="ok",
        message=f"All {len(approvals)} artifact(s) approved. Moving to Phase 6.",
        new_version=None,
        attempt=None
    )


@router.post("/{run_id}/phase5/reject", response_model=ApprovalResponse)
async def submit_rejection(
    run_id: str,
    request: RejectRequest,
    session: Session = Depends(get_session),
    # current_user: str = Depends(get_current_user),  # TODO: re-enable after testing
):
    """
    User rejects artifact(s) → create new version, queue regeneration.

    For PPTX partial reject:
    - rejected_slides: [2, 4] → regenerate only these slides
    - approved_slides: [1, 3, 5] → keep these from v1

    For full reject:
    - rejected_slides: null → regenerate entire artifact
    """
    run = session.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )

    if run.phase_5_status == "max_rejections_reached":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max rejections (3/3) reached. Must approve."
        )

    # Get current approval record for this artifact
    current_approval = session.query(ArtifactApprovalRecord).filter(
        ArtifactApprovalRecord.run_id == run_id,
        ArtifactApprovalRecord.artifact_type == request.artifact_type,
        ArtifactApprovalRecord.is_current == True
    ).first()

    if not current_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No current approval record for {request.artifact_type}"
        )

    # Calculate new version
    current_version_num = int(current_approval.version[1:])  # v1 → 1
    new_version = f"v{current_version_num + 1}"  # v2

    # Mark old approval as history
    current_approval.is_current = False
    current_approval.is_immutable = True
    current_approval.replaced_by = new_version
    current_approval.replaced_at = utcnow()

    # Calculate new attempt count
    new_attempt = current_approval.attempt_count + 1

    # Create new approval record
    new_approval = ArtifactApprovalRecord(
        id=str(uuid.uuid4()),
        run_id=run_id,
        project_id=run.project_id,
        artifact_type=request.artifact_type,
        version=new_version,
        is_current=True,
        is_immutable=False,
        status="regenerating",
        attempt_count=new_attempt,
        total_slides=current_approval.total_slides,
        approved_slides=json.dumps(request.approved_slides or []),
        rejected_slides=json.dumps(request.rejected_slides or []),
        user_feedback=request.user_feedback,
        rejected_by="test_user",  # TODO: use current_user after auth is enabled
        rejected_at=utcnow(),
    )
    session.add(new_approval)

    # Determine rejection type
    rejection_type = "partial" if request.rejected_slides else "full"

    # Check hard fail (3/3 rejections)
    if new_attempt >= 3:
        run.phase_5_status = "max_rejections_reached"
        session.commit()
        return ApprovalResponse(
            status="max_rejections",
            message=f"Max rejections (3/3) reached. Must approve to proceed.",
            new_version=new_version,
            attempt=f"{new_attempt}/3"
        )

    # Queue Phase 3 regeneration
    await queue_phase3_regeneration(
        run_id=run_id,
        artifact_type=request.artifact_type,
        rejected_slides=request.rejected_slides,
        approved_slides=request.approved_slides,
        new_version=new_version,
        rejection_type=rejection_type,
        feedback="improve more better in context of design quality perspective",
        session=session
    )

    return ApprovalResponse(
        status="regenerating",
        message=f"{request.artifact_type.upper()} queued for regeneration",
        new_version=new_version,
        attempt=f"{new_attempt}/3"
    )


@router.get("/{run_id}/phase5/approval-status/{artifact_type}", response_model=ApprovalStatusResponse)
async def get_approval_status(
    run_id: str,
    artifact_type: str,
    session: Session = Depends(get_session),
    # current_user: str = Depends(get_current_user),  # TODO: re-enable after testing
):
    """Get current approval state for an artifact."""
    approval = session.query(ArtifactApprovalRecord).filter(
        ArtifactApprovalRecord.run_id == run_id,
        ArtifactApprovalRecord.artifact_type == artifact_type,
        ArtifactApprovalRecord.is_current == True
    ).first()

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approval record for {artifact_type} in run {run_id}"
        )

    return ApprovalStatusResponse(
        artifact_type=approval.artifact_type,
        version=approval.version,
        status=approval.status,
        attempt_count=approval.attempt_count,
        is_current=approval.is_current,
        approved_slides=json.loads(approval.approved_slides or "[]"),
        rejected_slides=json.loads(approval.rejected_slides or "[]"),
        total_slides=approval.total_slides
    )


@router.get("/{run_id}/phase5/approval-status")
async def get_all_approval_status(
    run_id: str,
    session: Session = Depends(get_session),
    # current_user: str = Depends(get_current_user),  # TODO: re-enable after testing
):
    """Get approval status for all artifacts in this run."""
    approvals = session.query(ArtifactApprovalRecord).filter(
        ArtifactApprovalRecord.run_id == run_id,
        ArtifactApprovalRecord.is_current == True
    ).all()

    if not approvals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approvals found for run {run_id}"
        )

    return {
        "run_id": run_id,
        "artifacts": [
            {
                "artifact_type": a.artifact_type,
                "version": a.version,
                "status": a.status,
                "attempt_count": a.attempt_count,
                "approved_slides": json.loads(a.approved_slides or "[]"),
                "rejected_slides": json.loads(a.rejected_slides or "[]"),
            }
            for a in approvals
        ]
    }
