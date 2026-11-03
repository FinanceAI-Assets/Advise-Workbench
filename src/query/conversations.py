"""Library Q&A conversations: each signed-in user's threads of questions and cited answers.

A conversation is one ``workbench_records`` row (collection ``library_conversations``, owned by ``user_id``);
its payload holds the title and every turn as the query pipeline returned it. Follow-up questions are rewritten
from the stored turns, so clients only send ``conversation_id``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.models import WorkbenchRecord, utcnow
from src.query.pipeline import QueryResult

COLLECTION = "library_conversations"
MAX_TURNS = 100
TITLE_CHARS = 80


class ConversationFull(Exception):
    """The conversation already has ``MAX_TURNS`` turns."""


def _now() -> str:
    return utcnow().isoformat(timespec="seconds")


def _row(db: Session, user_id: str, conversation_id: str, *, lock: bool = False) -> WorkbenchRecord | None:
    stmt = select(WorkbenchRecord).where(
        WorkbenchRecord.collection == COLLECTION,
        WorkbenchRecord.record_id == conversation_id,
        WorkbenchRecord.user_id == user_id,
    )
    return db.scalar(stmt.with_for_update() if lock else stmt)


def _payload(row: WorkbenchRecord) -> dict[str, Any]:
    return json.loads(row.payload_json or "{}")


def _summary(row: WorkbenchRecord) -> dict[str, Any]:
    payload = _payload(row)
    turns = payload.get("turns", [])
    return {
        "id": row.record_id,
        "title": payload.get("title", ""),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "turn_count": len(turns),
        "last_question": turns[-1]["question"] if turns else None,
        "last_status": turns[-1]["status"] if turns else None,
    }


def get(db: Session, user_id: str, conversation_id: str) -> dict[str, Any] | None:
    row = _row(db, user_id, conversation_id)
    return {**_summary(row), "turns": _payload(row).get("turns", [])} if row is not None else None


def list_for(db: Session, user_id: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    rows = db.scalars(
        select(WorkbenchRecord).where(WorkbenchRecord.collection == COLLECTION, WorkbenchRecord.user_id == user_id)
    ).all()
    items = sorted((_summary(r) for r in rows), key=lambda c: c["updated_at"] or "", reverse=True)
    return {"items": items[offset : offset + limit], "total": len(items)}


def history(conversation: dict[str, Any]) -> list[dict[str, str]]:
    """The stored turns as chat messages, for rewriting a follow-up question."""
    messages: list[dict[str, str]] = []
    for turn in conversation.get("turns", []):
        messages.append({"role": "user", "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    return messages


def append(db: Session, user_id: str, conversation_id: str | None, result: QueryResult) -> tuple[str, dict[str, Any]]:
    """Store one answered question; a new conversation is created when ``conversation_id`` is None."""
    now = _now()
    turn = {"id": f"turn_{uuid.uuid4().hex[:16]}", "created_at": now, **asdict(result)}
    row = _row(db, user_id, conversation_id, lock=True) if conversation_id else None
    if conversation_id and row is None:
        raise LookupError(conversation_id)  # deleted while the question was being answered
    if row is None:
        row = WorkbenchRecord(collection=COLLECTION, record_id=f"conv_{uuid.uuid4().hex[:20]}", user_id=user_id,
                              payload_json="{}")
        db.add(row)
        payload: dict[str, Any] = {"title": result.question[:TITLE_CHARS], "created_at": now, "turns": []}
    else:
        payload = _payload(row)
        if len(payload.get("turns", [])) >= MAX_TURNS:
            raise ConversationFull(conversation_id)
    payload["turns"].append(turn)
    payload["updated_at"] = now
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.updated_at = utcnow()
    db.commit()
    return row.record_id, turn


def set_feedback(db: Session, user_id: str, conversation_id: str, turn_id: str, feedback: dict[str, Any]) -> dict[str, Any] | None:
    """Store the user's rating of one answer (replacing an earlier one); None when the turn is not theirs.

    The caller commits, so the question log can be updated in the same transaction."""
    row = _row(db, user_id, conversation_id, lock=True)
    if row is None:
        return None
    payload = _payload(row)
    turn = next((t for t in payload.get("turns", []) if t["id"] == turn_id), None)
    if turn is None:
        return None
    turn["feedback"] = feedback
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    return turn


def rename(db: Session, user_id: str, conversation_id: str, title: str) -> dict[str, Any] | None:
    row = _row(db, user_id, conversation_id, lock=True)
    if row is None:
        return None
    payload = _payload(row)
    payload["title"] = title.strip()[:TITLE_CHARS]
    payload["updated_at"] = _now()
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.updated_at = utcnow()
    db.commit()
    return _summary(row)


def delete(db: Session, user_id: str, conversation_id: str) -> bool:
    row = _row(db, user_id, conversation_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
