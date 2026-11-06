"""Phase 5: Human-In-The-Loop Design Review - Main orchestration."""

import copy
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from src.core.db.models import ArtifactApprovalRecord, Run, utcnow
from src.workflows.phase5_rejection_handler import (
    output_type_for,
    regeneration_plan,
    reviewed_artifact_types,
)

_log = logging.getLogger(__name__)

MAX_WAIT_SECONDS = 3600  # one hour without a decision fails the run
POLL_INTERVAL_SECONDS = 5


def _current_records(session: Session, run_id: str) -> list[ArtifactApprovalRecord]:
    return (
        session.query(ArtifactApprovalRecord)
        .filter(ArtifactApprovalRecord.run_id == run_id, ArtifactApprovalRecord.is_current == True)  # noqa: E712
        .all()
    )


def _read_slides(run_dir) -> list[dict[str, Any]]:
    path = run_dir / "pptx_slides.json"
    try:
        slides = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, ValueError):
        return []
    return [s for s in slides if isinstance(s, dict)] if isinstance(slides, list) else []


def _regenerate(job, records: list[ArtifactApprovalRecord]) -> tuple[bool, str] | None:
    """Run one generate pass for the rejected artifacts only, then put their new versions up for review.

    Returns the generate phase's outcome when it ended the run (for example a budget or abort stop).
    """
    from src.workflows.orchestrator import _phase_generate, append_run_event, workspace_path

    run_id, project_id = job.run_id, job.project_id
    run: Run = job.vars["run"]
    session: Session = job.vars["session"]
    run_dir = workspace_path(project_id) / "runs" / run_id
    approval_data = json.loads(run.phase_5_approval_data or "{}")
    regenerating = {r.artifact_type: approval_data.get(r.artifact_type, {}) for r in records}
    types = sorted(regenerating)
    _log.info("phase5: regenerating %s for run %s", types, run_id)
    append_run_event(session, run_id, "design_review_regeneration_started", {"artifacts": types})
    session.commit()

    # Narrow the generate pass to the rejected outputs and the reviewer's feedback, then restore the run's
    # own inputs so Phase 6 and any later regeneration see the original plan.
    saved = {name: job.vars.get(name) for name in ("requested", "init_state", "plan_payload_obj", "state")}
    plan = regeneration_plan(saved["plan_payload_obj"] or {}, regenerating, _read_slides(run_dir) if "pptx" in regenerating else None)
    requested = [output_type_for(t) for t in types]
    init_state = copy.deepcopy(saved["init_state"] or {})
    init_state.update({"plan_payload": plan, "requested_outputs": requested})
    job.vars.update({"requested": requested, "init_state": init_state, "plan_payload_obj": plan})
    try:
        outcome = _phase_generate(job)
    finally:
        new_state = job.vars.get("state") if isinstance(job.vars.get("state"), dict) else {}
        job.vars.update({k: v for k, v in saved.items() if k != "state"})
        job.vars["state"] = {**(saved["state"] or {}), **new_state}
    if outcome is not None:
        return outcome

    # The new versions are ready for review.
    session.refresh(run)
    approval_data = json.loads(run.phase_5_approval_data or "{}")
    for record in records:
        record.status = "pending"
        record.updated_at = utcnow()
        if record.artifact_type == "pptx":
            record.total_slides = len(_read_slides(run_dir)) or record.total_slides
        approval_data.setdefault(record.artifact_type, {}).update(
            {"status": "pending", "current_version": record.version, "attempt": record.attempt_count}
        )
    run.phase_5_approval_data = json.dumps(approval_data)
    append_run_event(session, run_id, "design_review_regeneration_done", {"artifacts": types})
    session.commit()
    return None


def _phase_hitl_review(job):  # Avoid circular import: don't type-hint RunJob
    """
    Phase 5: Human-In-The-Loop Design Approval

    BLOCKS until the user decides, through the API:
    - POST /api/runs/{run_id}/phase5/approve-all → continue to Phase 6 (remember)
    - POST /api/runs/{run_id}/phase5/reject → regenerate that artifact here, then wait again

    Each artifact can be rejected MAX_REJECTIONS times; after that it can only be approved.
    Returns None to continue to Phase 6, or a failure outcome on timeout or when regeneration ends the run.
    """
    run_id = job.run_id
    project_id = job.project_id
    run = job.vars.get("run")
    session = job.vars.get("session")

    try:
        # STEP 1: Review exactly the artifacts this run produced.
        artifact_types = reviewed_artifact_types(job.vars.get("requested") or json.loads(run.output_types or "[]"))
        if not artifact_types:
            _log.info("phase5: run %s produced nothing to review; skipping design review", run_id)
            return None

        approval_data = json.loads(run.phase_5_approval_data or "{}")
        for artifact_type in artifact_types:
            approval_data.setdefault(
                artifact_type, {"current_version": "v1", "attempt": 1, "status": "pending", "regenerate_mode": None}
            )
        run.phase_5_status = "pending"
        run.phase_5_started_at = run.phase_5_started_at or utcnow()
        run.phase_5_approval_data = json.dumps(approval_data)

        # STEP 2: A v1 approval record per artifact (kept when the phase resumes after a restart).
        from src.workflows.orchestrator import workspace_path

        slide_count = len(_read_slides(workspace_path(project_id) / "runs" / run_id))
        existing = {r.artifact_type for r in _current_records(session, run_id)}
        for artifact_type in artifact_types:
            if artifact_type in existing:
                continue
            session.add(
                ArtifactApprovalRecord(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    project_id=project_id,
                    artifact_type=artifact_type,
                    version="v1",
                    is_current=True,
                    is_immutable=False,
                    status="pending",
                    attempt_count=1,
                    total_slides=slide_count or None if artifact_type == "pptx" else None,
                    approved_slides=json.dumps([]),
                    rejected_slides=json.dumps([]),
                )
            )
        session.commit()
        _log.info("phase5: run %s waiting for design review of %s", run_id, artifact_types)

        # STEP 3: BLOCK AND POLL for the user's decision. Time spent regenerating does not count.
        waited = 0.0
        while waited < MAX_WAIT_SECONDS:
            # Decisions arrive through the API's own sessions: drop cached rows so the run and records are re-read.
            session.expire_all()
            if run.abort_requested:
                run.status = "failed"
                run.error_message = run.error_message or "Aborted during design review."
                session.commit()
                return False, run.error_message

            if run.phase_5_status == "approved":
                _log.info("phase5: run %s approved; moving to Phase 6", run_id)
                return None

            regenerating = [r for r in _current_records(session, run_id) if r.status == "regenerating"]
            if regenerating:
                outcome = _regenerate(job, regenerating)
                if outcome is not None:
                    return outcome
                waited = 0.0  # a fresh version restarts the review clock
                continue

            time.sleep(POLL_INTERVAL_SECONDS)
            waited += POLL_INTERVAL_SECONDS

        # TIMEOUT
        run.status = "failed"
        run.error_message = f"HITL approval timeout ({MAX_WAIT_SECONDS}s)"
        run.phase_5_status = "timed_out"
        session.commit()
        _log.warning("phase5: run %s timed out waiting for design review", run_id)
        return False, run.error_message

    finally:
        from src.workflows.orchestrator import _keep
        _keep(job, locals())


def initialize_approval_records(run_id: str, project_id: str, session: Session, artifact_types: list[str]) -> None:
    """Create a pending v1 approval record for each artifact type that has none."""
    existing = {r.artifact_type for r in _current_records(session, run_id)}
    for artifact_type in artifact_types:
        if artifact_type in existing:
            continue
        session.add(
            ArtifactApprovalRecord(
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
        )
    session.commit()
