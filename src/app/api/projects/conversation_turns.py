"""Conversation messages answered in the background.

A reply from Sheldon can take longer than a browser request should stay open. With
``?background=true`` the message, decisions and outline endpoints return a turn id at once; the reply is produced on a
worker thread and the client polls ``GET /{pid}/conversation/turns/{turn_id}`` for it.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from src.app.api.projects._router import router
from src.app.api.projects._schemas import ConversationMessageRequest
from src.core.auth import get_current_user, require_project_role
from src.core.db.models import ConversationTurn, User
from src.core.db.session import SessionLocal, get_db
from src.core.tz import ist_now

_LOG = logging.getLogger(__name__)
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="conversation-turn")
# A turn still "running" this long after it started lost its worker (for example, the server restarted).
_STALE_AFTER = timedelta(minutes=15)

# Progress of the turns this process is answering. It is kept in memory, not in the database: the
# turn's own transaction is open while it runs, and on SQLite a second writer would wait on its lock.
# A poll that lands on another API process sees the phase stored at the start ("queued").
_LIVE_PHASE: dict[str, str] = {}

PHASE_LABELS = {
    "queued": "Starting",
    "receive": "Reading your message",
    "understand": "Working out what you have told me so far",
    "route": "Checking the project knowledge and deciding the next step",
    "respond": "Writing the reply",
}


def _update_turn(turn_id: str, **values: object) -> None:
    session = SessionLocal()
    try:
        turn = session.get(ConversationTurn, turn_id)
        if turn is not None:
            for key, value in values.items():
                setattr(turn, key, value)
            turn.updated_at = ist_now()
            session.commit()
    finally:
        session.close()


Work = Callable[[Session, User, Callable[[str], None]], dict]


def _answer_turn(turn_id: str, pid: str, user_id: str, work: Work) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        response = work(db, user, lambda name: _LIVE_PHASE.__setitem__(turn_id, name))
        db.commit()
        _update_turn(
            turn_id, status="done", phase=_LIVE_PHASE.get(turn_id, "queued"), response_json=json.dumps(response, default=str)
        )
    except HTTPException as exc:
        db.rollback()
        _update_turn(turn_id, status="failed", status_code=exc.status_code, response_json=json.dumps({"detail": exc.detail}, default=str))
    except Exception as exc:
        db.rollback()
        _LOG.exception("conversation_turn_failed project=%s turn=%s err=%s", pid, turn_id, exc)
        detail = f"conversation_message_failed: {type(exc).__name__}: {str(exc)[:300]}"
        _update_turn(turn_id, status="failed", status_code=500, response_json=json.dumps({"detail": detail}))
    finally:
        db.close()
        _LIVE_PHASE.pop(turn_id, None)


def start_background(pid: str, user: User, db: Session, work: Work) -> dict:
    """Record a turn and hand ``work`` to a worker thread. ``work`` gets its own session, the user and a progress callback."""
    require_project_role(pid, {"Owner", "Editor", "Viewer"}, user, db)
    turn = ConversationTurn(id=f"t_{uuid.uuid4().hex[:16]}", project_id=pid, user_id=user.id)
    db.add(turn)
    db.commit()
    _EXECUTOR.submit(_answer_turn, turn.id, pid, user.id, work)
    return {"turn_id": turn.id, "status": "running", "phase": "queued", "phase_label": PHASE_LABELS["queued"]}


def start_turn(pid: str, body: ConversationMessageRequest, user: User, db: Session) -> dict:
    """Answer a chat message in the background."""
    from src.app.api.projects.conversation import _post_project_conversation_message_impl

    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content must not be empty")
    request = ConversationMessageRequest(content=content)
    return start_background(
        pid, user, db, lambda session, who, on_phase: _post_project_conversation_message_impl(pid, request, who, session, on_phase=on_phase)
    )


@router.get("/{pid}/conversation/turns/{turn_id}")
def get_project_conversation_turn(
    pid: str,
    turn_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_project_role(pid, {"Owner", "Editor", "Viewer"}, user, db)
    turn = db.get(ConversationTurn, turn_id)
    if turn is None or turn.project_id != pid or turn.user_id != user.id:
        raise HTTPException(status_code=404, detail="turn not found")
    phase = _LIVE_PHASE.get(turn.id, turn.phase) if turn.status == "running" else turn.phase
    out: dict = {
        "turn_id": turn.id,
        "status": turn.status,
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase),
    }
    if turn.status == "running" and ist_now() - turn.created_at > _STALE_AFTER:
        out.update(status="failed", status_code=503, response={"detail": "The reply was interrupted. Please send the message again."})
    elif turn.status != "running":
        out.update(status_code=turn.status_code, response=json.loads(turn.response_json or "{}"))
    return out
