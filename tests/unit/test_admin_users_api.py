"""Creating accounts through the admin API, and what each platform role can reach."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from scripts import create_admin
from src.app.main import app as fastapi_app
from src.core.config import settings
from src.core.db.models import ActivityEvent, User
from src.core.db.session import session_scope

PASSWORD = "correct-horse-battery"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _login(client: TestClient, email: str, password: str = "secret123") -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _admin(client: TestClient) -> dict[str, str]:
    email = _email("first-admin")
    headers = _login(client, email)
    with session_scope() as db:
        row = db.scalar(select(User).where(User.email == email))
        row.is_admin, row.role = True, "admin"
    return headers


def _create(client: TestClient, headers: dict[str, str], **overrides):
    body = {"email": _email("created"), "password": PASSWORD, "role": "admin", **overrides}
    return client.post("/api/admin/users", json=body, headers=headers), body


def test_created_admin_can_sign_in_and_switch_to_the_admin_console() -> None:
    client = TestClient(fastapi_app)
    resp, body = _create(client, _admin(client), full_name="Asha Rao", job_title="Platform lead")
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin" and resp.json()["isAdmin"] is True and resp.json()["name"] == "Asha Rao"
    assert "password" not in resp.text

    headers = _login(client, body["email"], PASSWORD)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["isAdmin"] is True and me["canSwitchAdmin"] is True and me["jobTitle"] == "Platform lead"
    assert client.get("/api/admin/overview", headers=headers).status_code == 200
    assert client.get("/api/engagements", headers=headers).status_code == 200

    with session_scope() as db:
        assert db.scalar(
            select(ActivityEvent).where(ActivityEvent.kind == "admin", ActivityEvent.detail == body["email"])
        )


def test_regular_user_has_the_user_workspace_only() -> None:
    client = TestClient(fastapi_app)
    resp, body = _create(client, _admin(client), role="user")
    assert resp.status_code == 201 and resp.json()["isAdmin"] is False

    headers = _login(client, body["email"], PASSWORD)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["isAdmin"] is False and me["canSwitchAdmin"] is False
    assert client.get("/api/engagements", headers=headers).status_code == 200
    assert client.get("/api/admin/overview", headers=headers).status_code == 403


@pytest.mark.parametrize("env", ["development", "production"])
def test_regular_user_cannot_create_accounts_in_any_environment(env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "advise_workbench_env", env)
    client = TestClient(fastapi_app)
    resp, body = _create(client, _login(client, _email("member")))
    assert resp.status_code == 403
    with session_scope() as db:
        assert db.scalar(select(User).where(User.email == body["email"])) is None


def test_creating_an_account_requires_a_session() -> None:
    client = TestClient(fastapi_app)
    resp, _ = _create(client, {})
    assert resp.status_code == 401


def test_revoked_admin_loses_the_console_on_the_next_request() -> None:
    client = TestClient(fastapi_app)
    admin = _admin(client)
    resp, body = _create(client, admin)
    headers = _login(client, body["email"], PASSWORD)
    assert client.get("/api/admin/overview", headers=headers).status_code == 200

    assert client.patch(f"/api/admin/users/{resp.json()['id']}/role", json={"role": "user"}, headers=admin).status_code == 200
    assert client.get("/api/admin/overview", headers=headers).status_code == 403
    assert client.get("/api/auth/me", headers=headers).json()["canSwitchAdmin"] is False


def test_duplicate_email_is_rejected_regardless_of_case_and_keeps_the_existing_account() -> None:
    client = TestClient(fastapi_app)
    admin = _admin(client)
    resp, body = _create(client, admin, role="user")
    assert resp.status_code == 201

    again, _ = _create(client, admin, email=body["email"].upper(), password="another-long-password")
    assert again.status_code == 409
    with session_scope() as db:
        assert db.scalar(select(User).where(User.email == body["email"])).is_admin is False
    _login(client, body["email"], PASSWORD)


@pytest.mark.parametrize(
    "overrides",
    [
        {"role": "owner"},
        {"email": "not-an-email"},
        {"password": "too-short"},
        {"password": "x" * 73},
    ],
)
def test_invalid_requests_are_rejected(overrides) -> None:
    client = TestClient(fastapi_app)
    resp, _ = _create(client, _admin(client), **overrides)
    assert resp.status_code == 422


def test_email_outside_the_allowed_domains_is_rejected(monkeypatch) -> None:
    client = TestClient(fastapi_app)
    admin = _admin(client)
    monkeypatch.setattr(settings, "auth_allowed_email_domains", "deloitte.com")
    resp, _ = _create(client, admin)
    assert resp.status_code == 403


def _bootstrap(client: TestClient, secret: str | None = "bootstrap-secret-value", **overrides):
    body = {"email": _email("bootstrapped"), "password": PASSWORD, **overrides}
    headers = {} if secret is None else {"X-Admin-Bootstrap-Secret": secret}
    return client.post("/api/auth/bootstrap-admin", json=body, headers=headers), body


def test_bootstrap_creates_an_admin_who_can_sign_in_and_switch(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_bootstrap_secret", "bootstrap-secret-value")
    client = TestClient(fastapi_app)
    resp, body = _bootstrap(client, full_name="First Admin")
    assert resp.status_code == 201 and resp.json()["isAdmin"] is True
    assert "password" not in resp.text

    headers = _login(client, body["email"], PASSWORD)
    assert client.get("/api/auth/me", headers=headers).json()["canSwitchAdmin"] is True
    assert client.get("/api/admin/overview", headers=headers).status_code == 200
    with session_scope() as db:
        assert db.scalar(
            select(ActivityEvent).where(ActivityEvent.actor == "Admin bootstrap", ActivityEvent.detail == body["email"])
        )


def test_bootstrap_route_is_absent_until_a_secret_is_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_bootstrap_secret", "")
    client = TestClient(fastapi_app)
    for secret in (None, ""):
        resp, body = _bootstrap(client, secret=secret)
        assert resp.status_code == 404
        with session_scope() as db:
            assert db.scalar(select(User).where(User.email == body["email"])) is None


@pytest.mark.parametrize("secret", [None, "", "wrong-secret", "bootstrap-secret-valué"])
def test_bootstrap_rejects_a_missing_or_wrong_secret(secret, monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_bootstrap_secret", "bootstrap-secret-value")
    client = TestClient(fastapi_app)
    headers = {} if secret is None else {"X-Admin-Bootstrap-Secret": secret.encode("utf-8")}
    body = {"email": _email("bootstrapped"), "password": PASSWORD}
    resp = client.post("/api/auth/bootstrap-admin", json=body, headers=headers)
    assert resp.status_code == 403
    with session_scope() as db:
        assert db.scalar(select(User).where(User.email == body["email"])) is None


def test_bootstrap_cannot_take_over_an_existing_account(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_bootstrap_secret", "bootstrap-secret-value")
    client = TestClient(fastapi_app)
    existing = _email("member")
    _login(client, existing)
    resp, _ = _bootstrap(client, email=existing)
    assert resp.status_code == 409
    with session_scope() as db:
        assert db.scalar(select(User).where(User.email == existing)).is_admin is False
    _login(client, existing)  # the original password still works


def test_create_admin_script_creates_the_first_admin_and_promotes_an_existing_user(monkeypatch) -> None:
    client = TestClient(fastapi_app)
    email = _email("bootstrap")
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setattr("sys.argv", ["create_admin", "--email", email, "--name", "First Admin"])
    assert create_admin.main() == 0
    headers = _login(client, email, PASSWORD)
    assert client.get("/api/admin/overview", headers=headers).status_code == 200

    existing = _email("member")
    member = _login(client, existing)
    assert client.get("/api/admin/overview", headers=member).status_code == 403
    monkeypatch.setattr("sys.argv", ["create_admin", "--email", existing])
    assert create_admin.main() == 0
    assert client.get("/api/admin/overview", headers=member).status_code == 200
    _login(client, existing)  # promotion keeps the password


def test_create_admin_script_rejects_a_weak_password(monkeypatch, capsys) -> None:
    email = _email("bootstrap")
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    monkeypatch.setattr("sys.argv", ["create_admin", "--email", email])
    assert create_admin.main() == 2
    assert "at least 12" in capsys.readouterr().err
    with session_scope() as db:
        assert db.scalar(select(User).where(User.email == email)) is None
