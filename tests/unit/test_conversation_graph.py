"""Conversation turns: the LangGraph phase driver and replies answered in the background."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app.api.projects import conversation_turns
from src.app.main import app as fastapi_app
from src.workflows.conversation_graph import run_turn
from tests.unit.plan_helpers import confirm_plan_for_project
from tests.unit.test_auth_hitl import auth_header


def _phases(log: list[str], reply_at: str, fail_at: str = ""):
    def make(name: str):
        def phase(turn: dict) -> dict | None:
            log.append(name)
            if name == fail_at:
                raise HTTPException(status_code=409, detail="stop")
            return {"from": name, "turn": turn["id"]} if name == reply_at else None

        return phase

    return tuple((name, make(name)) for name in ("receive", "understand", "route", "respond"))


def test_phases_run_in_order_until_one_replies() -> None:
    log: list[str] = []
    seen: list[str] = []
    assert run_turn(_phases(log, "respond"), {"id": 1}, on_phase=seen.append) == {"from": "respond", "turn": 1}
    assert log == seen == ["receive", "understand", "route", "respond"]

    log.clear()
    assert run_turn(_phases(log, "understand"), {"id": 2}) == {"from": "understand", "turn": 2}
    assert log == ["receive", "understand"]


def test_phase_error_reaches_the_caller_unchanged() -> None:
    log: list[str] = []
    with pytest.raises(HTTPException) as err:
        run_turn(_phases(log, "respond", fail_at="route"), {"id": 3})
    assert err.value.status_code == 409
    assert log == ["receive", "understand", "route"]


def test_no_reply_is_an_error() -> None:
    with pytest.raises(RuntimeError):
        run_turn(_phases([], "never"), {"id": 4})


def _client_and_project() -> tuple[TestClient, dict[str, str], str]:
    client = TestClient(fastapi_app)
    headers = auth_header(client)
    created = client.post("/api/projects", json={"name": "Turns"}, headers=headers)
    assert created.status_code == 200, created.text
    return client, headers, created.json()["id"]


def test_plan_is_proposed_through_the_graph() -> None:
    client, headers, pid = _client_and_project()
    _, plan_hash = confirm_plan_for_project(client, headers, pid)
    assert plan_hash


class _InlineExecutor:
    """Runs the turn in the request thread: the test database is one shared in-memory connection."""

    @staticmethod
    def submit(fn, *args):
        fn(*args)


def test_background_turn_returns_at_once_and_is_polled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversation_turns, "_EXECUTOR", _InlineExecutor)
    client, headers, pid = _client_and_project()
    started = client.post(
        f"/api/projects/{pid}/conversation/messages?background=true", json={"content": "hi"}, headers=headers
    )
    assert started.status_code == 200, started.text
    turn_id = started.json()["turn_id"]
    assert started.json()["status"] == "running"

    polled = client.get(f"/api/projects/{pid}/conversation/turns/{turn_id}", headers=headers)
    assert polled.status_code == 200, polled.text
    body = polled.json()
    assert body["status"] == "done" and body["status_code"] == 200
    assert [m["role"] for m in body["response"]["messages"]][-2:] == ["user", "assistant"]

    direct = client.get(f"/api/projects/{pid}/conversation", headers=headers)
    assert len(direct.json()["messages"]) == len(body["response"]["messages"])


def test_background_turn_reports_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversation_turns, "_EXECUTOR", _InlineExecutor)
    client, headers, pid = _client_and_project()

    def boom(*_: object, **__: object) -> dict:
        raise HTTPException(status_code=409, detail="plan_required")

    monkeypatch.setattr("src.app.api.projects.conversation._post_project_conversation_message_impl", boom)
    turn_id = client.post(
        f"/api/projects/{pid}/conversation/messages?background=true", json={"content": "hello"}, headers=headers
    ).json()["turn_id"]
    body = client.get(f"/api/projects/{pid}/conversation/turns/{turn_id}", headers=headers).json()
    assert (body["status"], body["status_code"], body["response"]) == ("failed", 409, {"detail": "plan_required"})


def test_background_turn_is_private_and_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversation_turns, "_EXECUTOR", _InlineExecutor)
    client, headers, pid = _client_and_project()
    empty = client.post(f"/api/projects/{pid}/conversation/messages?background=true", json={"content": " "}, headers=headers)
    assert empty.status_code == 400
    assert client.get(f"/api/projects/{pid}/conversation/turns/t_missing", headers=headers).status_code == 404


@pytest.mark.parametrize(
    ("endpoint", "body"),
    [
        ("decisions", {"answers": [{"prompt_id": "x", "selected_values": ["y"]}]}),
        ("outline", {"slides": [{"title": "One", "slide_type": "content"}]}),
    ],
)
def test_decisions_and_outline_in_the_background_match_the_direct_call(
    monkeypatch: pytest.MonkeyPatch, endpoint: str, body: dict
) -> None:
    monkeypatch.setattr(conversation_turns, "_EXECUTOR", _InlineExecutor)
    client, headers, pid = _client_and_project()
    url = f"/api/projects/{pid}/conversation/{endpoint}"
    direct = client.post(url, json=body, headers=headers)
    started = client.post(f"{url}?background=true", json=body, headers=headers)
    if started.status_code == 422:  # the body is rejected before any work starts, the same in both modes
        assert direct.status_code == 422
        return
    assert started.status_code == 200, started.text
    turn = client.get(f"/api/projects/{pid}/conversation/turns/{started.json()['turn_id']}", headers=headers).json()
    assert turn["status_code"] == direct.status_code
    assert turn["response"] == direct.json()


def test_go_commits_the_run_before_it_is_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    """The queue reads the run in its own session; on a real database an uncommitted run is invisible to it."""
    from unittest.mock import patch

    from sqlalchemy import event
    from sqlalchemy.orm import Session

    from src.app.api.projects import conversation
    from src.core.db.models import Run
    from tests.unit.plan_helpers import DEFAULT_PLAN_USER_MESSAGE, _stub_route_turn

    uncommitted = {"run": False}

    def after_flush(session, _ctx) -> None:
        if any(isinstance(obj, Run) for obj in session.new):
            uncommitted["run"] = True

    def after_commit(_session) -> None:
        uncommitted["run"] = False

    seen: list[bool] = []
    monkeypatch.setattr(conversation, "enqueue_run_execution", lambda pid, run_id: seen.append(uncommitted["run"]) or True)
    client, headers, pid = _client_and_project()
    event.listen(Session, "after_flush", after_flush)
    event.listen(Session, "after_commit", after_commit)
    try:
        with (
            patch("src.app.api.projects.conversation.route_turn", side_effect=_stub_route_turn),
            patch("src.workflows.task_router.output_format_detection.resolve_output_formats", return_value=([], {}, "")),
        ):
            url = f"/api/projects/{pid}/conversation/messages"
            assert client.post(url, json={"content": DEFAULT_PLAN_USER_MESSAGE}, headers=headers).json().get("plan_hash")
            went = client.post(url, json={"content": "go ahead"}, headers=headers)
    finally:
        event.remove(Session, "after_flush", after_flush)
        event.remove(Session, "after_commit", after_commit)
    assert went.status_code == 200, went.text
    assert went.json().get("auto_executed") is True
    assert seen == [False]


def test_only_a_run_in_progress_blocks_a_new_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finished run must not stop another conversation in the engagement from generating."""
    from unittest.mock import patch

    from src.app.api.projects import conversation
    from src.core.db.models import Run
    from src.core.db.session import SessionLocal
    from tests.unit.plan_helpers import DEFAULT_PLAN_USER_MESSAGE, _stub_route_turn

    monkeypatch.setattr(conversation, "enqueue_run_execution", lambda pid, run_id: True)
    client, headers, pid = _client_and_project()

    def generate_in_new_conversation(title: str) -> dict:
        started = client.post(f"/api/engagements/{pid}/conversations", json={"title": title}, headers=headers)
        assert started.status_code == 201, started.text
        url = f"/api/projects/{pid}/conversation/messages"
        assert client.post(url, json={"content": DEFAULT_PLAN_USER_MESSAGE}, headers=headers).json().get("plan_hash")
        went = client.post(url, json={"content": "go ahead"}, headers=headers)
        assert went.status_code == 200, went.text
        return went.json()

    with (
        patch("src.app.api.projects.conversation.route_turn", side_effect=_stub_route_turn),
        patch("src.workflows.task_router.output_format_detection.resolve_output_formats", return_value=([], {}, "")),
    ):
        first = generate_in_new_conversation("First thread")
        assert first["auto_executed"] is True

        blocked = generate_in_new_conversation("While the first is in progress")
        assert blocked["auto_executed"] is False
        assert blocked["run_id"] == first["run_id"]

        session = SessionLocal()
        try:
            session.get(Run, first["run_id"]).status = "review_ready"
            session.commit()
        finally:
            session.close()

        second = generate_in_new_conversation("After the first finished")

    assert second["auto_executed"] is True
    assert second["run_id"] != first["run_id"]


@pytest.mark.parametrize(("last_status", "starts_a_new_run"), [("failed", True), ("running", False)])
def test_go_again_retries_a_failed_run_but_not_one_in_progress(
    monkeypatch: pytest.MonkeyPatch, last_status: str, starts_a_new_run: bool
) -> None:
    from unittest.mock import patch

    from sqlalchemy import select

    from src.app.api.projects import conversation
    from src.core.db.models import Run
    from src.core.db.session import SessionLocal
    from tests.unit.plan_helpers import DEFAULT_PLAN_USER_MESSAGE, _stub_route_turn

    monkeypatch.setattr(conversation, "enqueue_run_execution", lambda pid, run_id: True)
    client, headers, pid = _client_and_project()
    url = f"/api/projects/{pid}/conversation/messages"

    with (
        patch("src.app.api.projects.conversation.route_turn", side_effect=_stub_route_turn),
        patch("src.workflows.task_router.output_format_detection.resolve_output_formats", return_value=([], {}, "")),
    ):
        assert client.post(url, json={"content": DEFAULT_PLAN_USER_MESSAGE}, headers=headers).json().get("plan_hash")
        first = client.post(url, json={"content": "go ahead"}, headers=headers).json()
        assert first["auto_executed"] is True

        session = SessionLocal()
        try:
            session.get(Run, first["run_id"]).status = last_status
            session.commit()
        finally:
            session.close()

        again = client.post(url, json={"content": "go ahead"}, headers=headers)
        assert again.status_code == 200, again.text

    session = SessionLocal()
    try:
        runs = session.scalars(select(Run.id).where(Run.project_id == pid)).all()
    finally:
        session.close()
    assert len(runs) == (2 if starts_a_new_run else 1)
    assert again.json()["auto_executed"] is starts_a_new_run


@pytest.mark.parametrize("reply", ["yes", "go ahead"])
def test_go_after_a_finished_run_asks_before_generating_again(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    from unittest.mock import patch

    from sqlalchemy import select

    from src.app.api.projects import conversation
    from src.core.db.models import Run
    from src.core.db.session import SessionLocal
    from tests.unit.plan_helpers import DEFAULT_PLAN_USER_MESSAGE, _stub_route_turn

    monkeypatch.setattr(conversation, "enqueue_run_execution", lambda pid, run_id: True)
    client, headers, pid = _client_and_project()
    url = f"/api/projects/{pid}/conversation/messages"

    def run_ids() -> list[str]:
        session = SessionLocal()
        try:
            return list(session.scalars(select(Run.id).where(Run.project_id == pid)).all())
        finally:
            session.close()

    with (
        patch("src.app.api.projects.conversation.route_turn", side_effect=_stub_route_turn),
        patch("src.workflows.task_router.output_format_detection.resolve_output_formats", return_value=([], {}, "")),
    ):
        assert client.post(url, json={"content": DEFAULT_PLAN_USER_MESSAGE}, headers=headers).json().get("plan_hash")
        first = client.post(url, json={"content": "go ahead"}, headers=headers).json()

        session = SessionLocal()
        try:
            session.get(Run, first["run_id"]).status = "review_ready"
            session.commit()
        finally:
            session.close()

        asked = client.post(url, json={"content": "go"}, headers=headers).json()
        assert asked["auto_executed"] is False
        assert asked["messages"][-1]["metadata"]["kind"] == "regeneration_confirmation"
        assert run_ids() == [first["run_id"]]

        confirmed = client.post(url, json={"content": reply}, headers=headers).json()

    assert confirmed["auto_executed"] is True
    assert confirmed["run_id"] != first["run_id"]
    assert len(run_ids()) == 2


def test_a_plain_yes_starts_nothing_unless_sheldon_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import patch

    from sqlalchemy import select

    from src.app.api.projects import conversation
    from src.core.db.models import Run
    from src.core.db.session import SessionLocal
    from tests.unit.plan_helpers import DEFAULT_PLAN_USER_MESSAGE, _stub_route_turn

    monkeypatch.setattr(conversation, "enqueue_run_execution", lambda pid, run_id: True)
    client, headers, pid = _client_and_project()
    url = f"/api/projects/{pid}/conversation/messages"

    with (
        patch("src.app.api.projects.conversation.route_turn", side_effect=_stub_route_turn),
        patch("src.workflows.task_router.output_format_detection.resolve_output_formats", return_value=([], {}, "")),
    ):
        assert client.post(url, json={"content": DEFAULT_PLAN_USER_MESSAGE}, headers=headers).json().get("plan_hash")
        answer = client.post(url, json={"content": "yes"}, headers=headers)
    assert answer.status_code == 200, answer.text

    session = SessionLocal()
    try:
        assert session.scalars(select(Run.id).where(Run.project_id == pid)).all() == []
    finally:
        session.close()
