"""Phase 5 design review: the approval API and the waiting phase that regenerates rejected artifacts."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from src.app.main import app as fastapi_app
from src.core.config import settings
from src.core.db.models import ArtifactApprovalRecord, Run
from src.core.db.session import SessionLocal, session_scope
from src.core.storage import workspace_path
from src.workflows import orchestrator, phase5_hitl_review
from src.workflows.phase5_rejection_handler import regeneration_plan, reviewed_artifact_types

SLIDES = [{"title": f"Slide {n}", "slide_type": "bullets"} for n in (1, 2, 3)]


@pytest.fixture(autouse=True)
def _workspace_in_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))


def _login(client: TestClient, prefix: str) -> tuple[str, dict[str, str]]:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    return email, {"Authorization": f"Bearer {resp.json()['access_token']}"}


class Review:
    """An engagement whose run is waiting in design review with a 3-slide deck and a document."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        _, self.lead = _login(client, "lead")
        resp = client.post("/api/engagements", json={"name": "Northstar", "brief": "Design a ninety-day pilot."}, headers=self.lead)
        assert resp.status_code == 201
        self.pid = resp.json()["id"]
        self.run_id = f"run_{uuid.uuid4().hex[:8]}"
        run_dir = workspace_path(self.pid) / "runs" / self.run_id
        run_dir.mkdir(parents=True)
        (run_dir / "pptx_slides.json").write_text(json.dumps(SLIDES), encoding="utf-8")
        with session_scope() as db:
            db.add(Run(id=self.run_id, project_id=self.pid, status="running", output_types='["pptx", "docx"]',
                       instruction="Roadmap", plan_payload="{}"))

    def url(self, path: str) -> str:
        return f"/api/runs/{self.run_id}/phase5/{path}"

    def start_review(self) -> None:
        """What the phase does on entry, without blocking."""
        with session_scope() as db:
            run = db.get(Run, self.run_id)
            run.phase_5_status = "pending"
            for t in ("pptx", "docx"):
                db.add(ArtifactApprovalRecord(id=str(uuid.uuid4()), run_id=self.run_id, project_id=self.pid,
                                              artifact_type=t, version="v1", is_current=True, status="pending",
                                              attempt_count=1, total_slides=3 if t == "pptx" else None))

    def set_status(self, artifact_type: str, status: str) -> None:
        with session_scope() as db:
            rec = db.query(ArtifactApprovalRecord).filter_by(run_id=self.run_id, artifact_type=artifact_type, is_current=True).one()
            rec.status = status


def test_reviewed_artifacts_follow_the_runs_outputs() -> None:
    assert reviewed_artifact_types(["pptx", "process_map", "raci", "pptx"]) == ["pptx", "drawio"]


def test_regeneration_plan_rebuilds_only_rejected_slides() -> None:
    plan = regeneration_plan(
        {"regeneration_directive": "Earlier note"},
        {"pptx": {"regenerate_mode": "partial", "rejected_slides": [3, 2], "feedback": "Bolder charts"}},
        SLIDES,
    )
    assert plan["prior_pptx_slides"] == SLIDES
    assert [h["slide_index"] for h in plan["pptx_visual_feedback"]] == [2, 3]
    assert "Bolder charts" in plan["pptx_visual_feedback"][0]["instruction"]
    assert plan["regeneration_directive"].startswith("Earlier note")


def test_regeneration_plan_full_rebuild_carries_feedback() -> None:
    plan = regeneration_plan({"prior_pptx_slides": SLIDES}, {"docx": {"regenerate_mode": "full", "feedback": "Shorter"}}, None)
    assert "prior_pptx_slides" not in plan
    assert "DOCX" in plan["regeneration_directive"] and "Shorter" in plan["regeneration_directive"]


def test_endpoints_require_sign_in_and_membership() -> None:
    client = TestClient(fastapi_app)
    review = Review(client)
    review.start_review()
    assert client.get(review.url("approval-status")).status_code == 401
    _, outsider = _login(client, "outsider")
    assert client.get(review.url("approval-status"), headers=outsider).status_code == 403
    assert client.post(review.url("approve-all"), json={}, headers=outsider).status_code == 403


def test_reject_records_the_reviewer_feedback_and_slides() -> None:
    client = TestClient(fastapi_app)
    review = Review(client)
    review.start_review()

    status = client.get(review.url("approval-status"), headers=review.lead).json()
    assert status["phase_5_status"] == "pending"
    deck = next(a for a in status["artifacts"] if a["artifact_type"] == "pptx")
    assert deck["total_slides"] == 3 and deck["rejections_used"] == 0

    resp = client.post(review.url("reject"), headers=review.lead,
                       json={"artifact_type": "pptx", "rejected_slides": [2, 9], "user_feedback": "Bolder charts"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "regenerating", "message": "PPTX queued for regeneration", "new_version": "v2", "attempt": "1/3"}

    with session_scope() as db:
        rec = db.query(ArtifactApprovalRecord).filter_by(run_id=review.run_id, artifact_type="pptx", is_current=True).one()
        assert (rec.version, rec.status, rec.user_feedback) == ("v2", "regenerating", "Bolder charts")
        assert json.loads(rec.rejected_slides) == [2] and json.loads(rec.approved_slides) == [1, 3]
        assert rec.rejected_by and rec.rejected_by != "test_user"
        data = json.loads(db.get(Run, review.run_id).phase_5_approval_data)
        assert data["pptx"]["feedback"] == "Bolder charts" and data["pptx"]["regenerate_mode"] == "partial"

    # Nothing can be decided on a version that is still being rebuilt.
    assert client.post(review.url("reject"), headers=review.lead, json={"artifact_type": "pptx"}).status_code == 409
    assert client.post(review.url("approve-all"), json={}, headers=review.lead).status_code == 409


def test_three_rejections_then_only_approval() -> None:
    client = TestClient(fastapi_app)
    review = Review(client)
    review.start_review()
    for n in (1, 2, 3):
        resp = client.post(review.url("reject"), headers=review.lead, json={"artifact_type": "docx"})
        assert resp.json()["attempt"] == f"{n}/3"
        review.set_status("docx", "pending")  # regeneration finished
    resp = client.post(review.url("reject"), headers=review.lead, json={"artifact_type": "docx"})
    assert resp.status_code == 400
    # The run is not failed by the limit: approving still moves it on.
    assert client.post(review.url("approve-all"), json={}, headers=review.lead).status_code == 200
    with session_scope() as db:
        run = db.get(Run, review.run_id)
        assert (run.phase_5_status, run.status) == ("approved", "running")


def test_decisions_need_a_run_waiting_in_review() -> None:
    client = TestClient(fastapi_app)
    review = Review(client)
    review.start_review()
    with session_scope() as db:
        db.get(Run, review.run_id).phase_5_status = "timed_out"
    assert client.post(review.url("approve-all"), json={}, headers=review.lead).status_code == 409


def test_run_moves_on_once_every_artifact_is_approved_one_by_one() -> None:
    client = TestClient(fastapi_app)
    review = Review(client)
    review.start_review()

    resp = client.post(review.url("approve"), json={"artifact_type": "pptx"}, headers=review.lead)
    assert resp.status_code == 200 and "Still awaiting: DOCX" in resp.json()["message"]
    with session_scope() as db:
        assert db.get(Run, review.run_id).phase_5_status == "pending"
    # An approved version can be neither approved again nor rejected.
    assert client.post(review.url("approve"), json={"artifact_type": "pptx"}, headers=review.lead).status_code == 409
    assert client.post(review.url("reject"), json={"artifact_type": "pptx"}, headers=review.lead).status_code == 409

    assert client.post(review.url("approve"), json={"artifact_type": "docx"}, headers=review.lead).status_code == 200
    with session_scope() as db:
        assert db.get(Run, review.run_id).phase_5_status == "approved"


def test_phase_regenerates_the_rejected_artifact_then_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(fastapi_app)
    review = Review(client)
    seen: dict = {}

    def fake_generate(job):
        seen["requested"] = list(job.vars["requested"])
        seen["plan"] = job.vars["init_state"]["plan_payload"]
        job.vars["state"] = {"pptx_slides": SLIDES + [{"title": "Slide 4"}]}
        run_dir = workspace_path(job.project_id) / "runs" / job.run_id
        (run_dir / "pptx_slides.json").write_text(json.dumps(SLIDES + [{"title": "Slide 4"}]), encoding="utf-8")
        return None

    decisions = iter([
        lambda: client.post(review.url("reject"), headers=review.lead,
                            json={"artifact_type": "pptx", "rejected_slides": [2], "user_feedback": "Bolder charts"}),
        lambda: client.post(review.url("approve-all"), json={}, headers=review.lead),
    ])
    # Each poll's wait is when the reviewer acts: first a rejection, then approval of the new version.
    monkeypatch.setattr(phase5_hitl_review.time, "sleep", lambda _s: next(decisions)())
    monkeypatch.setattr(orchestrator, "_phase_generate", fake_generate)

    session = SessionLocal()
    try:
        job = orchestrator.RunJob(project_id=review.pid, run_id=review.run_id)
        job.vars.update({
            "run": session.get(Run, review.run_id),
            "session": session,
            "requested": ["pptx", "docx"],
            "plan_payload_obj": {"regeneration_directive": ""},
            "init_state": {"plan_payload": {}, "requested_outputs": ["pptx", "docx"]},
            "state": {"narrative_md": "kept"},
        })
        assert phase5_hitl_review._phase_hitl_review(job) is None
    finally:
        session.close()

    assert seen["requested"] == ["pptx"]
    assert seen["plan"]["prior_pptx_slides"] == SLIDES
    assert seen["plan"]["pptx_visual_feedback"][0]["slide_index"] == 2
    # The run's own inputs are back for Phase 6; earlier outputs are kept alongside the new deck.
    assert job.vars["requested"] == ["pptx", "docx"]
    assert job.vars["state"]["narrative_md"] == "kept" and len(job.vars["state"]["pptx_slides"]) == 4
    with session_scope() as db:
        current = {r.artifact_type: r for r in db.query(ArtifactApprovalRecord).filter_by(run_id=review.run_id, is_current=True)}
        assert (current["pptx"].version, current["pptx"].status, current["pptx"].total_slides) == ("v2", "approved", 4)
        assert (current["docx"].version, current["docx"].status) == ("v1", "approved")
