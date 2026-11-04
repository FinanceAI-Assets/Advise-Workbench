from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from src.core.tz import IST
from typing import Any

from src.core.db.models import Conversation
from src.core.storage import workspace_path


_SCHEMA_VERSION = 2
_ALLOWED_STATES = {
    "new",
    "exploring",
    "discovery",
    # Collaborative story-building states (Phase 2)
    "storyline_building",   # Sheldon proposes narrative arc options; user agrees or redirects
    "slide_negotiation",    # Walk through slides one at a time; each agreement stored as MemoryItem
    "structure_agreed",     # All slides agreed; deck_outline assembled from decisions
    "ready_to_plan",
    "plan_proposed",
    "confirming",
    "done",
}


@dataclass
class ConversationState:
    schema_version: int
    state: str
    slots: dict[str, Any]
    deliverable: dict[str, Any]
    last_router: dict[str, Any]
    pending_questions: list[str]
    surfaced_wiki_refs: list[str]
    history_summary: str
    conversation_summary: str = ""  # 2-3 line summary of conversation (auto-generated on idle/session-end)

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "state": self.state,
                "slots": self.slots,
                "deliverable": self.deliverable,
                "last_router": self.last_router,
                "pending_questions": self.pending_questions,
                "surfaced_wiki_refs": self.surfaced_wiki_refs,
                "history_summary": self.history_summary,
                "conversation_summary": self.conversation_summary,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "state": self.state,
            "slots": self.slots,
            "deliverable": self.deliverable,
            "last_router": self.last_router,
            "pending_questions": self.pending_questions,
            "surfaced_wiki_refs": self.surfaced_wiki_refs,
            "history_summary": self.history_summary,
            "conversation_summary": self.conversation_summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationState:
        if not isinstance(data, dict):
            return default_state()
        schema_version = int(data.get("schema_version") or _SCHEMA_VERSION)
        state = str(data.get("state") or "new").strip().lower()
        if state not in _ALLOWED_STATES:
            state = "new"
        slots = data.get("slots")
        deliverable = data.get("deliverable")
        last_router = data.get("last_router")
        pending_questions = data.get("pending_questions")
        surfaced_wiki_refs = data.get("surfaced_wiki_refs")
        return cls(
            schema_version=schema_version,
            state=state,
            slots=slots if isinstance(slots, dict) else {},
            deliverable=deliverable if isinstance(deliverable, dict) else {},
            last_router=last_router if isinstance(last_router, dict) else {},
            pending_questions=[str(x).strip() for x in (pending_questions or []) if str(x).strip()],
            surfaced_wiki_refs=[str(x).strip() for x in (surfaced_wiki_refs or []) if str(x).strip()],
            history_summary=str(data.get("history_summary") or "").strip(),
            conversation_summary=str(data.get("conversation_summary") or "").strip(),
        )


def default_state() -> ConversationState:
    return ConversationState(
        schema_version=_SCHEMA_VERSION,
        state="new",
        slots={},
        deliverable={},
        last_router={},
        pending_questions=[],
        surfaced_wiki_refs=[],
        history_summary="",
        conversation_summary="",
    )


def load_state(conv: Conversation) -> ConversationState:
    import logging
    logger = logging.getLogger(__name__)

    state_path = workspace_path(conv.project_id) / "conversation_state" / f"{conv.id}.json"
    if not state_path.exists():
        logger.debug(f"[TRACE] State file does not exist: {state_path}")
        return default_state()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        logger.debug(f"[TRACE] Loaded JSON payload, has conversation_summary: {'conversation_summary' in payload}")
        if 'conversation_summary' in payload:
            logger.debug(f"[TRACE] conversation_summary value from file: '{payload.get('conversation_summary')}'")
    except Exception as e:
        logger.error(f"[TRACE] Error loading state file: {e}")
        return default_state()
    if not isinstance(payload, dict):
        return default_state()
    schema_version = int(payload.get("schema_version") or _SCHEMA_VERSION)
    state = str(payload.get("state") or "new").strip().lower()
    if state not in _ALLOWED_STATES:
        state = "new"
    slots = payload.get("slots")
    deliverable = payload.get("deliverable")
    last_router = payload.get("last_router")
    pending_questions = payload.get("pending_questions")
    surfaced_wiki_refs = payload.get("surfaced_wiki_refs")
    return ConversationState(
        schema_version=schema_version,
        state=state,
        slots=slots if isinstance(slots, dict) else {},
        deliverable=deliverable if isinstance(deliverable, dict) else {},
        last_router=last_router if isinstance(last_router, dict) else {},
        pending_questions=[str(x).strip() for x in (pending_questions or []) if str(x).strip()],
        surfaced_wiki_refs=[str(x).strip() for x in (surfaced_wiki_refs or []) if str(x).strip()],
        history_summary=str(payload.get("history_summary") or "").strip(),
        conversation_summary=str(payload.get("conversation_summary") or "").strip(),
    )


def stamp_router(
    state: ConversationState,
    *,
    intent: str,
    confidence: float,
    rationale: str = "",
) -> None:
    state.last_router = {
        "intent": str(intent or "").strip(),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "rationale": str(rationale or "").strip(),
        "ts": datetime.now(IST).isoformat(),
    }


def save_state(conv: Conversation, state: ConversationState) -> None:
    import logging
    logger = logging.getLogger(__name__)

    state_dir = workspace_path(conv.project_id) / "conversation_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{conv.id}.json"

    json_content = state.to_json()
    logger.debug(f"[TRACE] save_state() writing to: {state_path}")
    logger.debug(f"[TRACE] save_state() conversation_summary value: '{state.conversation_summary}'")

    state_path.write_text(json_content, encoding="utf-8")

    logger.debug(f"[TRACE] save_state() file written, size: {state_path.stat().st_size} bytes")

    # Verify the file was written correctly
    verify_content = state_path.read_text(encoding="utf-8")
    logger.debug(f"[TRACE] save_state() verification: conversation_summary in saved file: {verify_content.count('conversation_summary')}")
    import json as json_lib
    verify_json = json_lib.loads(verify_content)
    logger.debug(f"[TRACE] save_state() verified conversation_summary value in file: '{verify_json.get('conversation_summary')}'")
