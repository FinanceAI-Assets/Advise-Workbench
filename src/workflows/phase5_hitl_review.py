"""Phase 5: Human-In-The-Loop Design Review - Main orchestration."""

import json
import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from src.core.db.models import Run, ArtifactApprovalRecord, utcnow

_log = logging.getLogger(__name__)


def _phase_hitl_review(job):  # Avoid circular import: don't type-hint RunJob
    """
    Phase 5: Human-In-The-Loop Design Approval

    BLOCKS until user makes decision:
    - Approve all artifacts → move to Phase 6 (remember)
    - Reject some → queue Phase 3 regeneration → back to Phase 5
    - Max 3 rejections → hard fail, user must approve

    Returns: None (continue to Phase 6) when approved
    Returns: RunOutcome (fail) if hard fail reached

    This phase uses polling to wait for user decisions via the API:
    - POST /api/runs/{run_id}/phase5/approve-all
    - POST /api/runs/{run_id}/phase5/reject
    """

    run_id = job.run_id
    project_id = job.project_id
    run = job.vars.get("run")
    session = job.vars.get("session")

    print(f"\n{'='*80}\n[PHASE-HITL] STARTED for run_id={run_id}\n{'='*80}\n")
    print(f"[PHASE-HITL] DEBUG: This is Phase 5 - Human-In-The-Loop Design Review")
    print(f"[PHASE-HITL] DEBUG: Run will BLOCK here and poll for user approval via API")
    print(f"[PHASE-HITL] DEBUG: API endpoints to test:")
    print(f"[PHASE-HITL] DEBUG:   GET  /api/runs/{run_id}/phase5/approval-status")
    print(f"[PHASE-HITL] DEBUG:   POST /api/runs/{run_id}/phase5/approve-all")
    print(f"[PHASE-HITL] DEBUG:   POST /api/runs/{run_id}/phase5/reject\n")

    try:
        # STEP 1: Initialize Phase 5 state
        print(f"[PHASE-HITL] 1. Initializing Phase 5 HITL state...")

        run.phase_5_status = "pending"
        run.phase_5_started_at = utcnow()

        # Initialize approval data if not already present
        approval_data = json.loads(run.phase_5_approval_data or "{}")
        if not approval_data:
            # Create initial approval records for all generated artifacts
            artifact_types = ["pptx", "docx", "xlsx", "pdf", "sop", "narrative", "drawio"]
            for artifact_type in artifact_types:
                if artifact_type not in approval_data:
                    approval_data[artifact_type] = {
                        "current_version": "v1",
                        "attempt": 1,
                        "status": "pending",
                        "regenerate_mode": None
                    }

        run.phase_5_approval_data = json.dumps(approval_data)
        session.commit()

        print(f"[PHASE-HITL] 1a. Phase 5 initialized: status=pending")

        # STEP 2: Create initial approval records if they don't exist
        print(f"[PHASE-HITL] 2. Ensuring approval records exist for all artifacts...")

        for artifact_type in approval_data.keys():
            existing = session.query(ArtifactApprovalRecord).filter(
                ArtifactApprovalRecord.run_id == run_id,
                ArtifactApprovalRecord.artifact_type == artifact_type,
                ArtifactApprovalRecord.is_current == True
            ).first()

            if not existing:
                # Create initial v1 approval record
                import uuid
                approval = ArtifactApprovalRecord(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    project_id=project_id,
                    artifact_type=artifact_type,
                    version="v1",
                    is_current=True,
                    is_immutable=False,
                    status="pending",
                    attempt_count=1,
                    approved_slides=json.dumps([]),
                    rejected_slides=json.dumps([]),
                )
                session.add(approval)

        session.commit()
        print(f"[PHASE-HITL] 2a. Approval records ready for user review")

        # STEP 3: BLOCK AND POLL for user approval decision
        print(f"[PHASE-HITL] 3. Waiting for user approval via API...")
        print(f"[PHASE-HITL] 3a. User can call:")
        print(f"[PHASE-HITL]     - POST /api/runs/{run_id}/phase5/approve-all")
        print(f"[PHASE-HITL]     - POST /api/runs/{run_id}/phase5/reject")

        max_wait_seconds = 3600  # 1 hour timeout
        poll_interval = 5  # Check every 5 seconds
        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < max_wait_seconds:
            # Refresh run state from database
            session.refresh(run)
            poll_count += 1

            # Check for user decision
            if run.phase_5_status == "approved":
                print(f"[PHASE-HITL] 3b. User approved all artifacts (poll #{poll_count})")
                print(f"[PHASE-HITL] [OK] PHASE COMPLETE - moving to Phase 6 (remember)\n")
                return None  # Continue to Phase 6

            if run.phase_5_status == "max_rejections_reached":
                print(f"[PHASE-HITL] 3c. User hit max rejections (3/3) - hard fail")
                run.status = "failed"
                run.error_message = "Max design rejections (3/3) reached - user must approve"
                session.commit()
                print(f"[PHASE-HITL] [FAIL] Hard fail - max rejections reached\n")
                return False, "Max rejections reached"

            # Check for regeneration in progress
            approval_data = json.loads(run.phase_5_approval_data or "{}")
            regenerating = any(
                data.get("status") == "regenerating"
                for data in approval_data.values()
            )

            if regenerating:
                # Regeneration triggered, will go to Phase 3
                # Don't continue polling, let orchestrator handle phase transition
                print(f"[PHASE-HITL] 3d. Regeneration triggered (poll #{poll_count})")
                print(f"[PHASE-HITL]     Routing to Phase 3 for regeneration...")
                # Phase will continue after Phase 3 completes
                # For now, just sleep a bit and re-check

            # Still waiting
            if poll_count % 60 == 1:  # Log every 60 polls (5 min)
                elapsed = int(time.time() - start_time)
                print(f"[PHASE-HITL] 3e. Still waiting for approval ({elapsed}s elapsed, poll #{poll_count})")

            time.sleep(poll_interval)

        # TIMEOUT
        print(f"[PHASE-HITL] 3f. TIMEOUT - No approval decision within {max_wait_seconds}s")
        run.status = "failed"
        run.error_message = f"HITL approval timeout ({max_wait_seconds}s)"
        session.commit()
        print(f"[PHASE-HITL] [FAIL] Approval timeout\n")
        return False, "Approval timeout"

    except Exception as phase_exception:
        print(f"\n{'='*80}")
        print(f"[PHASE-HITL] [ERROR] EXCEPTION CAUGHT:")
        print(f"   Type: {type(phase_exception).__name__}")
        print(f"   Message: {phase_exception}")
        import traceback
        print(f"   Traceback:\n{traceback.format_exc()}")
        print(f"{'='*80}\n")
        raise

    finally:
        from src.workflows.orchestrator import _keep
        _keep(job, locals())


def initialize_approval_records(
    run_id: str,
    project_id: str,
    session: Session
) -> None:
    """Initialize approval records for all artifact types."""
    import uuid
    from src.core.db.models import ArtifactApprovalRecord

    artifact_types = ["pptx", "docx", "xlsx", "pdf", "sop", "narrative", "drawio"]

    for artifact_type in artifact_types:
        existing = session.query(ArtifactApprovalRecord).filter(
            ArtifactApprovalRecord.run_id == run_id,
            ArtifactApprovalRecord.artifact_type == artifact_type,
        ).first()

        if not existing:
            approval = ArtifactApprovalRecord(
                id=str(uuid.uuid4()),
                run_id=run_id,
                project_id=project_id,
                artifact_type=artifact_type,
                version="v1",
                is_current=True,
                is_immutable=False,
                status="pending",
                attempt_count=1,
                approved_slides=json.dumps([]),
                rejected_slides=json.dumps([]),
            )
            session.add(approval)

    session.commit()
