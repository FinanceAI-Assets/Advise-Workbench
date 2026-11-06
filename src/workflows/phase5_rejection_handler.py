"""Phase 5 rejection handling - queue Phase 3 regeneration."""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.core.db.models import Run, utcnow
from src.workflows.run_queue.runtime import RunQueueRuntime
from src.core.config import settings

_log = logging.getLogger(__name__)
_queue_rt = RunQueueRuntime(settings)


async def queue_phase3_regeneration(
    run_id: str,
    artifact_type: str,
    rejected_slides: Optional[list[int]],
    approved_slides: Optional[list[int]],
    new_version: str,
    rejection_type: str,
    feedback: str,
    session: Session,
) -> dict:
    """
    Queue Phase 3 regeneration for rejected artifacts.

    Args:
        run_id: Run ID
        artifact_type: Which artifact was rejected (pptx, docx, etc)
        rejected_slides: For PPTX partial reject: list of slide indices to regenerate
        approved_slides: For PPTX partial reject: list of slide indices to keep
        new_version: New version being created (v2, v3, etc)
        rejection_type: "partial" (PPTX only) or "full"
        feedback: Hardcoded feedback for regeneration
        session: Database session

    Returns:
        Dict with status and messaging
    """

    print(f"\n[PHASE5-REJECT-HANDLER] Queuing Phase 3 regeneration")
    print(f"  - Artifact: {artifact_type}")
    print(f"  - Type: {rejection_type}")
    print(f"  - New version: {new_version}")

    try:
        # Get the run
        run = session.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Update run state to trigger Phase 3
        approval_data = json.loads(run.phase_5_approval_data or "{}")

        approval_data[artifact_type].update({
            "status": "regenerating",
            "regenerate_mode": rejection_type,  # "partial" or "full"
            "rejected_slides": rejected_slides or [],
            "approved_slides": approved_slides or [],
            "new_version": new_version,
            "feedback": feedback,
        })

        run.phase_5_approval_data = json.dumps(approval_data)
        session.commit()

        print(f"[PHASE5-REJECT-HANDLER] Run state updated: {artifact_type}={rejection_type}")
        print(f"[PHASE5-REJECT-HANDLER] Phase 3 will regenerate on next orchestrator cycle")

        return {
            "status": "queued",
            "artifact": artifact_type,
            "new_version": new_version,
            "regenerate_mode": rejection_type,
            "feedback": feedback
        }

    except Exception as e:
        _log.error(f"Failed to queue Phase 3 regeneration for {run_id}: {e}")
        raise


def get_regeneration_instruction(
    run: Run,
    artifact_type: str,
    session: Session,
) -> Optional[dict]:
    """
    Check if this run needs Phase 3 regeneration due to Phase 5 rejection.
    Called by Phase 3 to know what to regenerate.

    Returns:
        None if no regeneration needed
        Dict with regeneration parameters if needed
    """

    approval_data = json.loads(run.phase_5_approval_data or "{}")
    artifact_data = approval_data.get(artifact_type, {})

    if artifact_data.get("status") != "regenerating":
        return None

    return {
        "artifact_type": artifact_type,
        "regenerate_mode": artifact_data.get("regenerate_mode"),  # "partial" or "full"
        "rejected_slides": artifact_data.get("rejected_slides", []),
        "approved_slides": artifact_data.get("approved_slides", []),
        "new_version": artifact_data.get("new_version"),
        "feedback": artifact_data.get("feedback"),
    }
