"""Sheldon's rag_agent: answers a question from documents through the query pipeline.

In an engagement Conversation it searches the engagement's uploaded documents and the approved Leading Practice
Library; Talk to data uses it for the library only. The answer is the query pipeline's (``src.query.service.ask``):
cited [S#], evidence only, and "insufficient evidence" instead of a guess. Engagement uploads are searchable once the
ingestion pipeline has processed them; the reply names any that are still being processed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from src.query import service
from src.query.pipeline import LLM_UNAVAILABLE, QueryResult, format_answer

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 8  # earlier messages given to the pipeline to rewrite a follow-up question


@dataclass
class RagReply:
    text: str  # Sheldon's message: the answer with [S#] markers and its sources, or why there is none
    metadata: dict[str, Any] = field(default_factory=dict)  # stored on the message: kind rag_answer, citations ...
    result: QueryResult | None = None


def _where(engagement_id: str | None, include_library: bool) -> str:
    if engagement_id and include_library:
        return "this engagement's documents or the Leading Practice Library"
    return "this engagement's documents" if engagement_id else "the Leading Practice Library"


def _history(messages: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    turns = [
        {"role": str(m.get("role")), "content": str(m.get("content") or "")[:4000]}
        for m in messages or []
        if m.get("role") in ("user", "assistant") and str(m.get("content") or "").strip()
    ]
    return turns[-HISTORY_MESSAGES:]


def answer(
    db: Session,
    *,
    user_id: str,
    question: str,
    engagement_id: str | None = None,
    include_library: bool = True,
    practice_ids: list[str] | None = None,
    history: list[dict[str, Any]] | None = None,
    top_k: int | None = None,
) -> RagReply:
    """Answer ``question``. Raises ``service.AccessDenied`` and search outages, like ``service.ask``."""
    scope = service.scope_for(engagement_id=engagement_id, include_library=include_library, practice_ids=practice_ids)
    turns = _history(history)
    logger.info("[RAG_AGENT] called: engagement=%s library=%s user=%s history=%d message(s); asking the query pipeline",
                engagement_id or "-", include_library, user_id, len(turns))
    result = service.ask(db, user_id, question, scope, history=turns, top_k=top_k)
    logger.info(
        "[RAG_AGENT] result: engagement=%s library=%s status=%s reason=%s citations=%d (engagement %d, library %d) "
        "candidates=%s final=%s ms=%s; reply goes back to Sheldon",
        engagement_id or "-", include_library, result.status, result.reason or "-", len(result.citations),
        sum(c.get("scope") == "engagement" for c in result.citations),
        sum(c.get("scope") == "library" for c in result.citations),
        result.retrieval.get("candidates"), result.retrieval.get("final"), result.timings_ms.get("total"),
    )
    where = _where(engagement_id, include_library)
    if result.status == "answered":
        text = format_answer(result)
    elif result.status == LLM_UNAVAILABLE:
        text = (f"I found sources in {where} but could not write the answer just now. Please ask again in a moment."
                + ("\nMost relevant sources:\n" + "\n".join(f"- {s['label']}" for s in result.sources[:5]) if result.sources else ""))
    else:
        text = (f"I couldn't find anything in {where} that answers that, so I won't guess. "
                "Try naming the document, process or practice, or upload the document that covers it.")
    pending = result.retrieval.get("pending_documents") or []
    if pending:
        names = ", ".join(pending[:5]) + (f" and {len(pending) - 5} more" if len(pending) > 5 else "")
        text += (f"\n\nStill processing, so not searched yet: {names}. "
                 "Ask again in a minute or two to include them.")
    metadata = {
        "kind": "rag_answer",
        "agent": "rag_agent",
        "status": result.status,
        "reason": result.reason,
        "question": result.question,
        "standalone_question": result.standalone_question,
        "answer_markdown": result.answer_markdown if result.status == "answered" else "",
        "citations": result.citations,
        "sources": result.sources[:8],
        "coverage": result.coverage,
        "retrieval": result.retrieval,
        "pending_documents": pending,
        "scope": {"engagement_id": engagement_id, "library": include_library, "practice_ids": list(scope.practice_ids)},
    }
    return RagReply(text=text, metadata=metadata, result=result)


def unavailable_reply(engagement_id: str | None = None, include_library: bool = True) -> RagReply:
    """Sheldon's reply when search itself is down."""
    return RagReply(
        text=f"I can't search {_where(engagement_id, include_library)} right now. Please try again in a moment.",
        metadata={"kind": "rag_answer", "agent": "rag_agent", "status": "search_unavailable", "reason": None,
                  "citations": [], "sources": []},
    )
