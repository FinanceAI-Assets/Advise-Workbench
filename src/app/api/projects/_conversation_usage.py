"""Token usage and estimated cost per conversation.

Each reply Sheldon writes is measured while it is produced (`capture_usage` in
`src.llm.run_budget`) and added to the conversation's running total, which is
stored in `workbench_records` (collection `conversation_usage`) so it survives a
restart. While a reply is in progress the tokens used so far are read live.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.db.models import WorkbenchRecord, utcnow
from src.llm.llm_pricing import calculate_run_cost_usd
from src.llm.run_budget import get_live_capture

COLLECTION = "conversation_usage"
_FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens")


def live_key(project_id: str, user_id: str) -> str:
    """Key of the reply currently being written for this user in this engagement."""
    return f"conversation:{project_id}:{user_id}"


def _row(db: Session, conversation_id: str) -> WorkbenchRecord | None:
    return db.scalar(
        select(WorkbenchRecord).where(
            WorkbenchRecord.collection == COLLECTION, WorkbenchRecord.record_id == conversation_id
        )
    )


def record_turn_usage(db: Session, *, conversation_id: str, project_id: str, usage: dict[str, int]) -> None:
    """Add one finished reply's token counts to the conversation's total."""
    if not any(usage.get(field) for field in _FIELDS):
        return
    row = _row(db, conversation_id)
    if row is None:
        row = WorkbenchRecord(collection=COLLECTION, record_id=conversation_id, project_id=project_id)
        db.add(row)
        totals: dict[str, int] = {}
    else:
        totals = json.loads(row.payload_json or "{}")
    for field in _FIELDS:
        totals[field] = int(totals.get(field, 0)) + int(usage.get(field, 0) or 0)
    totals["replies"] = int(totals.get("replies", 0)) + 1
    row.payload_json = json.dumps(totals)
    row.updated_at = utcnow()


def conversation_usage(db: Session, *, conversation_id: str | None, project_id: str, user_id: str) -> dict:
    """Saved totals for the conversation plus whatever the reply in progress has used so far."""
    row = _row(db, conversation_id) if conversation_id else None
    saved = json.loads(row.payload_json or "{}") if row else {}
    live = get_live_capture(live_key(project_id, user_id))
    totals = {field: int(saved.get(field, 0)) + int((live or {}).get(field, 0)) for field in _FIELDS}
    return {
        "conversationId": conversation_id,
        "model": settings.anthropic_claude_model,
        "inputTokens": totals["input_tokens"],
        "outputTokens": totals["output_tokens"],
        "cacheReadTokens": totals["cache_read_tokens"],
        "cacheCreationTokens": totals["cache_creation_tokens"],
        "totalTokens": sum(totals.values()),
        "costUsd": calculate_run_cost_usd(**totals),
        "replies": int(saved.get("replies", 0)),
        "live": live is not None,
        "pricing": {
            "inputPerMillion": settings.llm_price_input_per_mtok,
            "outputPerMillion": settings.llm_price_output_per_mtok,
        },
    }
