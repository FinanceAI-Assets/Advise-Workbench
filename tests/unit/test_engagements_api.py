"""Tests for the workbench engagements API and the profile routes it relies on."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.app.main import app as fastapi_app
from src.core.config import settings
from src.core.db.models import Review, User
from src.core.db.session import session_scope

BRIEF = "Design a service ownership pilot for shared services over ninety days."


@pytest.fixture(autouse=True)
def _workspace_in_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Creating an engagement scaffolds a workspace folder; keep those out of the repo's workspace."""
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))


def auth_header(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _create(client: TestClient, headers: dict[str, str], name: str = "Northstar pilot") -> str:
    resp = client.post(
        "/api/engagements",
        json={"name": name, "brief": BRIEF, "clientOrg": "Northstar (illustrative)", "startDate": "2026-10-12"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_engagements_require_auth() -> None:
    client = TestClient(fastapi_app)
    assert client.get("/api/engagements").status_code == 401
    assert client.get("/api/engagements/stats").status_code == 401


def test_create_rejects_short_brief() -> None:
    client = TestClient(fastapi_app)
    headers = auth_header(client, _email("lead"))
    resp = client.post("/api/engagements", json={"name": "Too short", "brief": "short"}, headers=headers)
    assert resp.status_code == 422


def test_create_then_list_and_detail() -> None:
    client = TestClient(fastapi_app)
    headers = auth_header(client, _email("lead"))
    pid = _create(client, headers)

    listing = client.get("/api/engagements", headers=headers).json()
    assert listing["total"] == 1
    row = listing["items"][0]
    assert row["id"] == pid and row["stage"] == "Brief" and row["progress"] == 0

    detail = client.get(f"/api/engagements/{pid}", headers=headers).json()
    assert detail["brief"]["summary"] == BRIEF
    assert detail["clientOrg"] == "Northstar (illustrative)"
    assert [s["status"] for s in detail["steps"]] == ["in-progress", "upcoming", "upcoming", "upcoming", "upcoming"]
    assert detail["teamMembers"][0]["role"] == "Engagement lead"
    assert detail["tabCounts"]["team"] == 1


def test_list_search_filters_and_paginates() -> None:
    client = TestClient(fastapi_app)
    headers = auth_header(client, _email("lead"))
    for name in ("Atlas finance", "Cedar change", "Horizon reset"):
        _create(client, headers, name)

    assert client.get("/api/engagements?q=cedar", headers=headers).json()["total"] == 1
    page = client.get("/api/engagements?page=2&page_size=2", headers=headers).json()
    assert page["total"] == 3 and len(page["items"]) == 1


def test_detail_is_forbidden_for_non_member() -> None:
    client = TestClient(fastapi_app)
    pid = _create(client, auth_header(client, _email("lead")))
    outsider = auth_header(client, _email("outsider"))
    assert client.get(f"/api/engagements/{pid}", headers=outsider).status_code == 403
    assert client.get("/api/engagements", headers=outsider).json()["total"] == 0


def test_update_brief_and_stage() -> None:
    client = TestClient(fastapi_app)
    headers = auth_header(client, _email("lead"))
    pid = _create(client, headers)

    bad = client.put(f"/api/engagements/{pid}", json={"stage": "Nonsense"}, headers=headers)
    assert bad.status_code == 422
    ok = client.put(
        f"/api/engagements/{pid}", json={"stage": "Drafting", "sponsorObjective": "Improve accountability"}, headers=headers
    )
    assert ok.status_code == 200
    detail = client.get(f"/api/engagements/{pid}", headers=headers).json()
    assert detail["stage"] == "Drafting"
    assert detail["brief"]["sponsorObjective"] == "Improve accountability"
    assert detail["steps"][2]["status"] == "in-progress"


def test_member_add_change_and_remove() -> None:
    client = TestClient(fastapi_app)
    lead = auth_header(client, _email("lead"))
    reviewer_email = _email("reviewer")
    reviewer = auth_header(client, reviewer_email)
    pid = _create(client, lead)

    assert client.get(f"/api/engagements/{pid}", headers=reviewer).status_code == 403
    unknown = client.post(
        f"/api/engagements/{pid}/members", json={"email": "nobody@example.com", "role": "Viewer"}, headers=lead
    )
    assert unknown.status_code == 404
    added = client.post(
        f"/api/engagements/{pid}/members", json={"email": reviewer_email, "role": "Independent reviewer"}, headers=lead
    )
    assert added.status_code == 201
    mid = added.json()["id"]
    assert client.get(f"/api/engagements/{pid}", headers=reviewer).status_code == 200

    members = client.get(f"/api/engagements/{pid}/members", headers=lead).json()["items"]
    assert {m["role"] for m in members} == {"Engagement lead", "Independent reviewer"}
    # Only the lead may change access.
    denied = client.patch(f"/api/engagements/{pid}/members/{mid}", json={"role": "Viewer"}, headers=reviewer)
    assert denied.status_code == 403
    assert client.patch(f"/api/engagements/{pid}/members/{mid}", json={"role": "Viewer"}, headers=lead).status_code == 200
    assert client.delete(f"/api/engagements/{pid}/members/{mid}", headers=lead).status_code == 200


def test_last_lead_cannot_be_removed() -> None:
    client = TestClient(fastapi_app)
    lead = auth_header(client, _email("lead"))
    pid = _create(client, lead)
    mid = client.get(f"/api/engagements/{pid}/members", headers=lead).json()["items"][0]["id"]
    assert client.delete(f"/api/engagements/{pid}/members/{mid}", headers=lead).status_code == 409


def test_stats_next_actions_and_export_gate_follow_reviews() -> None:
    client = TestClient(fastapi_app)
    email = _email("lead")
    lead = auth_header(client, email)
    pid = _create(client, lead)
    review_id = f"RV-{uuid.uuid4().hex[:6]}"
    with session_scope() as db:
        owner = db.scalar(select(User).where(User.email == email))
        db.add(
            Review(
                id=review_id,
                project_id=pid,
                title="Transformation roadmap",
                artifact_type="pptx",
                version_label="v0.8",
                owner_id=owner.id,
                state="Changes requested",
                due_date="2026-10-12",
            )
        )

    stats = {s["id"]: s for s in client.get("/api/engagements/stats", headers=lead).json()["items"]}
    assert stats["in-review"]["value"] == 1
    assert stats["in-review"]["helper"] == "1 need your response"

    actions = client.get("/api/engagements/next-actions", headers=lead).json()
    assert [a["id"] for a in actions["needsAction"]] == [review_id]
    assert actions["needsAction"][0]["due"] == "Due 12 Oct"

    gate = client.get(f"/api/engagements/{pid}/export-readiness", headers=lead).json()
    assert gate["ready"] is False and gate["blockers"] == [review_id]

    activity = client.get(f"/api/engagements/{pid}/activity", headers=lead).json()["items"]
    assert activity[0]["title"] == "Engagement created"


def test_profile_read_update_and_admin_flag() -> None:
    client = TestClient(fastapi_app)
    email = _email("profile")
    headers = auth_header(client, email)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["email"] == email and me["isAdmin"] is False and me["name"] == email.split("@")[0]

    updated = client.patch(
        "/api/auth/me", json={"full_name": "Alex Chen", "job_title": "Engagement lead"}, headers=headers
    ).json()
    assert updated["name"] == "Alex Chen" and updated["jobTitle"] == "Engagement lead"


def test_sign_in_is_limited_to_the_allowed_email_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_allowed_email_domains", "deloitte.com")
    client = TestClient(fastapi_app)
    outside = client.post("/api/auth/login", json={"email": _email("someone"), "password": "secret123"})
    assert outside.status_code == 403
    assert outside.json()["detail"] == "Sign in with your @deloitte.com account."

    inside = f"Member-{uuid.uuid4().hex[:8]}@Deloitte.com"
    assert client.post("/api/auth/login", json={"email": inside, "password": "secret123"}).status_code == 200
    # The address is case-insensitive: the same account signs in again in lower case.
    again = client.post("/api/auth/login", json={"email": inside.lower(), "password": "secret123"})
    assert again.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {again.json()['access_token']}"}).json()
    assert me["email"] == inside.lower()


def test_engagement_brief_answers_sheldons_discovery_questions() -> None:
    """Client, outcome and themes entered on the engagement are not asked for again in the conversation."""
    from src.app.api.projects._discovery import _merge_discovery, _required_discovery_missing_slots
    from src.app.api.projects._engagement_context import engagement_brief_text, engagement_discovery
    from src.core.db.session import session_scope as scope

    client = TestClient(fastapi_app)
    headers = auth_header(client, _email("lead"))
    pid = _create(client, headers)
    with scope() as db:
        # A new engagement has a client and a brief, but no success measures yet.
        assert _required_discovery_missing_slots(engagement_discovery(db, pid)) == ["win_themes"]

    client.put(
        f"/api/engagements/{pid}",
        json={"sponsorObjective": "Improve accountability", "successMeasures": "Ownership clarity · Pilot adoption"},
        headers=headers,
    )
    with scope() as db:
        slots = engagement_discovery(db, pid)
        assert slots["client"] == {"name": "Northstar (illustrative)"}
        assert slots["win_themes"] == ["Ownership clarity", "Pilot adoption"]
        assert _required_discovery_missing_slots(slots) == []
        # What the user says in the conversation still takes precedence.
        merged = _merge_discovery(slots, {"client": {"name": "Meridian"}})
        assert merged["client"]["name"] == "Meridian"
        text = engagement_brief_text(db, pid)
        assert "Client: Northstar (illustrative)" in text and "Sponsor objective: Improve accountability" in text
        assert engagement_discovery(db, "p_missing") == {} and engagement_brief_text(db, "p_missing") == ""
