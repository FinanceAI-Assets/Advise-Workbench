"""Stuck-run detection & recovery: watchdog, startup-reconcile, and the /active health endpoint."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from src.core.config import settings
from src.core.db.models import Project, Run, RunEvent, User, utcnow
from src.core.db.session import SessionLocal, init_db
from src.app.main import app
from src.workflows import orchestrator as run_worker
def _seed_run(session, *, run_id: str, project_id: str, status: str, last_event_age_sec: float | None) -> None:
    session.add(
        Run(
            id=run_id,
            project_id=project_id,
            status=status,
            output_types="[]",
            instruction="x",
            plan_payload="{}",
            approved_by=None,
            approved_at=utcnow(),
        )
    )
    if last_event_age_sec is not None:
        session.add(
            RunEvent(
                run_id=run_id,
                event_type="step",
                payload="{}",
                created_at=utcnow() - timedelta(seconds=last_event_age_sec),
            )
        )


def test_auto_fail_stuck_runs_fails_stale_leaves_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    monkeypatch.setattr(settings, "run_stuck_timeout_sec", 300)
    session = SessionLocal()
    try:
        session.add(User(id="u_stuck", email="stuck@test.local", hashed_password="x"))
        session.add(Project(id="p_stuck", name="StuckWatch", created_by="u_stuck"))
        _seed_run(session, run_id="r_stuck_hung", project_id="p_stuck", status="running", last_event_age_sec=400)
        _seed_run(session, run_id="r_stuck_fresh", project_id="p_stuck", status="running", last_event_age_sec=0)
        session.commit()
    finally:
        session.close()

    failed = run_worker.auto_fail_stuck_runs()
    assert failed >= 1

    verify = SessionLocal()
    try:
        hung = verify.get(Run, "r_stuck_hung")
        fresh = verify.get(Run, "r_stuck_fresh")
        assert hung.status == "failed"
        assert fresh.status == "running"
        events = [e.event_type for e in verify.query(RunEvent).filter_by(run_id="r_stuck_hung").all()]
        assert "stuck_auto_failed" in events
    finally:
        verify.close()


def test_auto_fail_disabled_when_timeout_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    monkeypatch.setattr(settings, "run_stuck_timeout_sec", 0)
    session = SessionLocal()
    try:
        session.add(User(id="u_off", email="off@test.local", hashed_password="x"))
        session.add(Project(id="p_off", name="WatchOff", created_by="u_off"))
        _seed_run(session, run_id="r_off_hung", project_id="p_off", status="running", last_event_age_sec=99999)
        session.commit()
    finally:
        session.close()

    assert run_worker.auto_fail_stuck_runs() == 0
    verify = SessionLocal()
    try:
        assert verify.get(Run, "r_off_hung").status == "running"
    finally:
        verify.close()


def test_startup_reconcile_fails_orphaned_running(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    monkeypatch.setattr(settings, "run_queue_startup_reconcile", True)
    monkeypatch.setattr(settings, "run_orphan_idle_sec", 300)
    # Avoid side effects from the approved-requeue branch.
    monkeypatch.setattr(run_worker, "enqueue_run_execution", lambda *a, **k: True)
    session = SessionLocal()
    try:
        session.add(User(id="u_orph", email="orph@test.local", hashed_password="x"))
        session.add(Project(id="p_orph", name="Orphan", created_by="u_orph"))
        _seed_run(session, run_id="r_orphan", project_id="p_orph", status="running", last_event_age_sec=400)
        session.commit()
    finally:
        session.close()

    run_worker.reconcile_stalled_approved_runs_on_startup()

    verify = SessionLocal()
    try:
        orphan = verify.get(Run, "r_orphan")
        assert orphan.status == "failed"
        assert "server restart" in orphan.error_message
        events = [e.event_type for e in verify.query(RunEvent).filter_by(run_id="r_orphan").all()]
        assert "stuck_auto_failed" in events
    finally:
        verify.close()


def test_startup_reconcile_spares_active_run_until_it_goes_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run still producing events may be alive on another server using this database."""
    init_db()
    monkeypatch.setattr(settings, "run_queue_startup_reconcile", True)
    monkeypatch.setattr(settings, "run_orphan_idle_sec", 300)
    monkeypatch.setattr(run_worker, "enqueue_run_execution", lambda *a, **k: True)
    session = SessionLocal()
    try:
        session.add(User(id="u_live", email="live@test.local", hashed_password="x"))
        session.add(Project(id="p_live", name="LiveElsewhere", created_by="u_live"))
        _seed_run(session, run_id="r_live", project_id="p_live", status="running", last_event_age_sec=5)
        session.commit()
    finally:
        session.close()

    run_worker.reconcile_stalled_approved_runs_on_startup()

    verify = SessionLocal()
    try:
        live = verify.get(Run, "r_live")
        assert live.status == "running"
        assert live.abort_requested is False
    finally:
        verify.close()

    # The same run, once it has been quiet past the limit, is orphaned by a later watchdog tick.
    monkeypatch.setattr(settings, "run_orphan_idle_sec", 0)
    run_worker.settle_orphan_suspects()

    verify = SessionLocal()
    try:
        assert verify.get(Run, "r_live").status == "failed"
    finally:
        verify.close()


def test_aborted_run_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    retries: list[str] = []
    monkeypatch.setattr(run_worker._queue_rt, "schedule_local_retry", lambda _d, _p, rid, _j: retries.append(rid))
    session = SessionLocal()
    try:
        session.add(User(id="u_retry", email="retry@test.local", hashed_password="x"))
        session.add(Project(id="p_retry", name="Retry", created_by="u_retry"))
        _seed_run(session, run_id="r_retry_aborted", project_id="p_retry", status="failed", last_event_age_sec=1)
        _seed_run(session, run_id="r_retry_failed", project_id="p_retry", status="failed", last_event_age_sec=1)
        session.flush()
        session.get(Run, "r_retry_aborted").abort_requested = True
        session.commit()
    finally:
        session.close()

    for run_id in ("r_retry_aborted", "r_retry_failed"):
        run_worker._handle_failed_job(
            project_id="p_retry",
            run_id=run_id,
            attempt=0,
            last_error="boom",
            prior_attempt_history=None,
            backend="local",
        )

    assert retries == ["r_retry_failed"]


def test_abort_keeps_the_reason_already_recorded() -> None:
    init_db()
    session = SessionLocal()
    try:
        session.add(User(id="u_keep", email="keep@test.local", hashed_password="x"))
        session.add(Project(id="p_keep", name="KeepReason", created_by="u_keep"))
        _seed_run(session, run_id="r_keep", project_id="p_keep", status="failed", last_event_age_sec=1)
        session.flush()
        run = session.get(Run, "r_keep")
        run.abort_requested = True
        run.error_message = "Stopped by user request."
        session.commit()
    finally:
        session.close()

    job = run_worker.RunJob(project_id="p_keep", run_id="r_keep")
    run_worker.open_run_job(job)
    try:
        outcome = run_worker._phase_prepare(job)
    finally:
        job.vars["session"].close()

    assert outcome == (False, "Stopped by user request.")
    verify = SessionLocal()
    try:
        assert verify.get(Run, "r_keep").error_message == "Stopped by user request."
    finally:
        verify.close()


@pytest.fixture()
def allow_signup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_allow_self_signup", True)


def _auth_header(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_active_runs_endpoint_states_and_role(allow_signup: None, monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    monkeypatch.setattr(settings, "run_stuck_timeout_sec", 30)
    # Keep the background watchdog from mutating our seeded rows mid-assertion.
    monkeypatch.setattr(run_worker, "auto_fail_stuck_runs", lambda: 0)

    client = TestClient(app)
    headers = _auth_header(client, "ops_owner@example.com")
    pr = client.post("/api/projects", json={"name": "Active Health"}, headers=headers)
    assert pr.status_code == 200, pr.text
    pid = pr.json()["id"]

    session = SessionLocal()
    try:
        _seed_run(session, run_id="r_act_hung", project_id=pid, status="running", last_event_age_sec=120)
        _seed_run(session, run_id="r_act_working", project_id=pid, status="running", last_event_age_sec=2)
        _seed_run(session, run_id="r_act_wait", project_id=pid, status="plan_ready", last_event_age_sec=5)
        _seed_run(session, run_id="r_act_queued", project_id=pid, status="approved", last_event_age_sec=5)
        session.commit()
    finally:
        session.close()

    resp = client.get(f"/api/runs/{pid}/active", headers=headers)
    assert resp.status_code == 200, resp.text
    by_id = {it["id"]: it for it in resp.json()["items"]}
    assert by_id["r_act_hung"]["state"] == "hung" and by_id["r_act_hung"]["stale"] is True
    assert by_id["r_act_hung"]["seconds_since_last_event"] >= 100
    assert by_id["r_act_working"]["state"] == "working" and by_id["r_act_working"]["stale"] is False
    assert by_id["r_act_wait"]["state"] == "awaiting_approval"
    assert by_id["r_act_queued"]["state"] == "queued"

    # A non-member is rejected.
    outsider = _auth_header(client, "ops_outsider@example.com")
    forbidden = client.get(f"/api/runs/{pid}/active", headers=outsider)
    assert forbidden.status_code == 403
