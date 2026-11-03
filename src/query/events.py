"""Library Q&A question log: one record per question asked, for the admin metrics (outcomes, latency, model
errors, feedback, and the questions the library could not answer).

Records live in ``workbench_records`` (collection ``query_events``); a saved turn's record has the turn id, so
feedback on the turn reaches it. Records older than ``query_event_retention_days`` are removed as new ones arrive.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.db.models import WorkbenchRecord, utcnow
from src.query.pipeline import QueryResult

COLLECTION = "query_events"


def record(db: Session, user_id: str, result: QueryResult, *, conversation_id: str | None, turn_id: str | None) -> None:
    now = utcnow()
    payload = {
        "at": now.isoformat(timespec="seconds"),
        "status": result.status,
        "reason": result.reason,
        "question": result.question[:500],
        "standalone_question": result.standalone_question[:500],
        "intent": result.understanding.get("intent"),
        "question_type": result.understanding.get("question_type"),
        "language": result.understanding.get("language"),
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "timings_ms": result.timings_ms,
        "model_calls": result.model_calls,
        "llm_errors": [e["kind"] for e in result.answer_metadata.get("errors", [])],
        "retrieval": result.retrieval,
        "citations": len(result.citations),
        "coverage_ratio": result.coverage.get("ratio"),
        "feedback": None,
    }
    db.add(WorkbenchRecord(collection=COLLECTION, record_id=turn_id or f"qe_{uuid.uuid4().hex[:20]}", user_id=user_id,
                           payload_json=json.dumps(payload, ensure_ascii=False), updated_at=now))
    cutoff = now - timedelta(days=settings.query_event_retention_days)
    db.execute(delete(WorkbenchRecord).where(WorkbenchRecord.collection == COLLECTION, WorkbenchRecord.updated_at < cutoff))
    db.commit()


def set_feedback(db: Session, turn_id: str, feedback: dict[str, Any]) -> None:
    row = db.scalar(select(WorkbenchRecord).where(WorkbenchRecord.collection == COLLECTION, WorkbenchRecord.record_id == turn_id))
    if row is None:
        return  # outside the retention window
    payload = json.loads(row.payload_json or "{}")
    payload["feedback"] = feedback
    row.payload_json = json.dumps(payload, ensure_ascii=False)


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def summary(db: Session, *, days: int, top: int = 20) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    rows = db.scalars(
        select(WorkbenchRecord).where(WorkbenchRecord.collection == COLLECTION, WorkbenchRecord.updated_at >= since)
    ).all()
    events = [json.loads(r.payload_json or "{}") for r in rows]
    total = len(events)
    answered = sum(1 for e in events if e.get("status") == "answered")
    latencies = [int(e.get("timings_ms", {}).get("total", 0)) for e in events]
    errors = Counter(kind for e in events for kind in e.get("llm_errors", []))
    feedback = [e["feedback"] for e in events if e.get("feedback")]

    unanswered: dict[str, dict[str, Any]] = {}
    for e in sorted(events, key=lambda e: e.get("at", "")):
        if e.get("status") != "insufficient_evidence":
            continue
        key = re.sub(r"\W+", " ", (e.get("standalone_question") or e.get("question") or "").lower()).strip()
        item = unanswered.setdefault(key, {"question": e.get("standalone_question") or e.get("question"), "count": 0})
        item.update({"count": item["count"] + 1, "reason": e.get("reason"), "last_asked_at": e.get("at")})

    daily: dict[str, dict[str, int]] = {}
    for e in events:
        day = daily.setdefault((e.get("at") or "")[:10], {"total": 0, "answered": 0})
        day["total"] += 1
        day["answered"] += e.get("status") == "answered"

    return {
        "window_days": days,
        "since": since.isoformat(timespec="seconds"),
        "total": total,
        "answered": answered,
        "answer_rate": round(answered / total, 3) if total else 0.0,
        "by_status": dict(Counter(e.get("status") for e in events)),
        "by_reason": dict(Counter(e["reason"] for e in events if e.get("reason"))),
        "by_intent": dict(Counter(e["intent"] for e in events if e.get("intent"))),
        "latency_ms": {
            "avg": int(sum(latencies) / total) if total else 0,
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
        },
        "llm": {
            "calls": sum(int(e.get("model_calls", 0)) for e in events),
            "failed_requests": sum(1 for e in events if e.get("status") == "llm_unavailable"),
            "errors_by_kind": dict(errors),
        },
        "feedback": {
            "up": sum(1 for f in feedback if f.get("rating") == "up"),
            "down": sum(1 for f in feedback if f.get("rating") == "down"),
            "recent_comments": [
                {"rating": f["rating"], "comment": f["comment"], "at": f.get("at")}
                for f in sorted(feedback, key=lambda f: f.get("at") or "", reverse=True) if f.get("comment")
            ][:top],
        },
        "unanswered_questions": sorted(unanswered.values(), key=lambda u: (u["count"], u["last_asked_at"] or ""), reverse=True)[:top],
        "daily": [{"date": d, **v} for d, v in sorted(daily.items())],
    }
