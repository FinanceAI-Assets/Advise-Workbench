"""Sheldon's rag_agent: answers a question from documents through the query pipeline.

In an engagement Conversation it searches the engagement's uploaded documents and the approved Leading Practice
Library; Talk to data uses it for the library only. The answer is the query pipeline's (``src.query.service.ask``):
cited [S#], evidence only, and "insufficient evidence" instead of a guess. Engagement uploads are searchable once the
ingestion pipeline has processed them; the reply names any that are still being processed.

Two entry points, one pipeline:

- ``answer(db, user_id=..., question=..., engagement_id=...)``: Sheldon's ``_turn_respond`` (router agent ->
  rag) and Talk to data (``/api/library/ask``).
- ``search_knowledge_base(router_input)``: Path 1.b of the Phase 2 router (``src.agents.sheldon_router_agent``),
  called from the conversation's ``phase2_route`` and the run orchestrator. It returns the Phase 2 contract
  (``should_answer``, ``documents``, ``context``, ``answer_preview``, ``accumulated_context`` ...). It replaces the
  placeholder that returned dummy documents (kept, commented out, at the end of this file).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from src.core.observability.metrics import increment
from src.query import service
from src.query.pipeline import LLM_UNAVAILABLE, QueryResult, QueryScope, answer_question, format_answer

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
    return _reply(result, scope, engagement_id, include_library)


def _reply(result: QueryResult, scope: QueryScope, engagement_id: str | None, include_library: bool) -> RagReply:
    """Sheldon's message and its stored metadata, from one query pipeline result."""
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


# ------------------------------------------------------------------- Phase 2 router: Path 1.b
def _engagement_of(router_input: dict[str, Any]) -> str | None:
    """The engagement a Phase 2 caller asks about: ``project_id`` (conversation) or ``project_context`` (runs)."""
    pid = router_input.get("project_id") or (router_input.get("project_context") or {}).get("project_id")
    return str(pid) if pid else None


def search_knowledge_base(router_input: dict[str, Any]) -> dict[str, Any]:
    """Path 1.b: answer from engagement documents, and from selected library practices when linked.

    ``router_input``: ``user_instruction`` (the question), ``project_id`` or ``project_context.project_id`` (the
    engagement), and optionally ``user_id`` (the engagement membership is then checked, as for every other caller)
    and ``history`` (earlier ``{role, content}`` messages, for follow-up questions). Runs from the orchestrator carry
    no ``user_id``: their access was checked when the run was created.

    ``should_answer`` is true when the pipeline produced a cited answer; otherwise the caller continues to generation
    (Path 1.c) with whatever ``context`` was found. The pipeline itself decides: no separate model call.
    """
    from src.core.db.session import session_scope

    question = str(router_input.get("user_instruction") or "").strip()
    conversation_digest = router_input.get("conversation_digest", "")
    plan_payload = router_input.get("plan_payload", {})
    init_state = router_input.get("init_state", {})
    engagement_id = _engagement_of(router_input)
    user_id = router_input.get("user_id")

    def accumulated(documents: list[dict[str, Any]], context: str) -> dict[str, Any]:
        return {"rag_documents": documents, "rag_context": context, "conversation_digest": conversation_digest,
                "plan_payload": plan_payload, "init_state": init_state}

    try:
        if not question:
            raise ValueError("no question in router_input['user_instruction']")
        logger.info("[RAG_AGENT] Path 1.b search_knowledge_base: engagement=%s user=%s question=%r",
                    engagement_id or "-", user_id or "(run)", question[:120])
        with session_scope() as db:
            practice_ids = service.engagement_practice_ids(db, engagement_id)
            include_library = bool(practice_ids)
            if user_id:
                reply = answer(
                    db,
                    user_id=str(user_id),
                    question=question,
                    engagement_id=engagement_id,
                    include_library=include_library,
                    practice_ids=practice_ids or None,
                    history=router_input.get("history"),
                )
            else:
                scope = service.scope_for(
                    engagement_id=engagement_id,
                    include_library=include_library,
                    practice_ids=practice_ids or None,
                )
                result = answer_question(db, scope, question, _history(router_input.get("history")))
                if engagement_id:
                    result.retrieval["pending_documents"] = service.pending_documents(db, engagement_id)
                reply = _reply(result, scope, engagement_id, include_library)
        result = reply.result
        documents = [
            {"id": s["id"], "title": s["title"], "excerpt": s["snippet"], "relevance": s["score"], "source": s["scope"],
             "filename": s.get("filename"), "page_number": s.get("page_number"), "link": s["link"]}
            for s in result.sources
        ]
        context = "\n".join(f"- {d['title']}: {d['excerpt']}" for d in documents[:5])
        answered = result.status == "answered"
        increment("rag_search_total")
        logger.info("[RAG_AGENT] Path 1.b result: status=%s reason=%s documents=%d should_answer=%s",
                    result.status, result.reason or "-", len(documents), answered)
        return {
            "success": True,
            "documents": documents,
            "context": context,
            "should_answer": answered,
            "should_generate": not answered,
            "confidence": float(result.retrieval.get("top_score") or 0.0),
            "answer_preview": reply.text if answered else "",
            "answer": reply.text,
            "reasoning": f"query pipeline: {result.status}" + (f" ({result.reason})" if result.reason else ""),
            "status": result.status,
            "reason": result.reason,
            "citations": result.citations,
            "metadata": reply.metadata,  # the rag_answer metadata Sheldon stores on the message
            "accumulated_context": accumulated(documents, context),
        }
    except Exception as e:  # access denied, search outage, bad input: the caller falls through to generation
        logger.error("[RAG_AGENT] Path 1.b failed for engagement %s: %s", engagement_id or "-", e, exc_info=True)
        return {
            "success": False,
            "documents": [],
            "context": "",
            "should_answer": False,
            "should_generate": True,
            "confidence": 0.0,
            "answer_preview": "",
            "reasoning": "RAG search failed",
            "error": str(e),
            "accumulated_context": accumulated([], ""),
        }


# ---------------------------------------------------------------------------------------------------------------
# Previous Path 1.b placeholder from origin/Langraph_Agentic_Pipeline, kept for reference. It returned three dummy
# documents and asked the model whether they answered the question. Replaced by search_knowledge_base above, which
# uses the real query pipeline (engagement documents + Leading Practice Library, cited answers).
# ---------------------------------------------------------------------------------------------------------------
# """RAG Agent: Path 1.b for knowledge base search in Phase 2.
#
# Searches the knowledge base (RAG1) and decides if answer is sufficient or generation needed.
# Currently uses placeholder with dummy data.
# """
#
# import logging
# from typing import Any
# from datetime import datetime
#
# from src.llm.claude import claude_generate_json, is_claude_enabled
# from src.core.observability.metrics import increment
#
# _LOG = logging.getLogger(__name__)
#
#
# def _get_rag1_placeholder_results(query: str) -> dict[str, Any]:
#     """Get placeholder RAG results (dummy data for now).
#
#     This will be replaced with real RAG integration later.
#     """
#     # Dummy documents for demonstration
#     dummy_docs = [
#         {
#             "id": "doc_q4_2024_report",
#             "title": "Q4 2024 Business Report",
#             "excerpt": "Q4 2024 showed strong performance with 15% growth in revenue...",
#             "relevance": 0.95,
#             "source": "knowledge_base"
#         },
#         {
#             "id": "doc_strategic_plan_2024",
#             "title": "Strategic Plan 2024",
#             "excerpt": "Our strategic initiatives focus on market expansion and operational efficiency...",
#             "relevance": 0.82,
#             "source": "knowledge_base"
#         },
#         {
#             "id": "doc_project_status",
#             "title": "Current Project Status",
#             "excerpt": "All active projects are on track with 85% completion rate...",
#             "relevance": 0.75,
#             "source": "knowledge_base"
#         }
#     ]
#
#     return {
#         "query": query,
#         "documents": dummy_docs,
#         "total_found": len(dummy_docs),
#         "search_confidence": 0.8,
#         "timestamp": datetime.now().isoformat()
#     }
#
#
# def search_knowledge_base(router_input: dict[str, Any]) -> dict[str, Any]:
#     """Search RAG knowledge base for user query (Path 1.b).
#
#     Args:
#         router_input: Dict containing user_instruction and context
#
#     Returns:
#         Dict with search results and decision recommendation
#     """
#     user_instruction = router_input.get("user_instruction", "")
#     conversation_digest = router_input.get("conversation_digest", "")
#     plan_payload = router_input.get("plan_payload", {})
#     init_state = router_input.get("init_state", {})
#
#     try:
#         # Get RAG results (placeholder for now)
#         rag_results = _get_rag1_placeholder_results(user_instruction)
#         documents = rag_results.get("documents", [])
#
#         # Build context from found documents
#         doc_context = "\n".join([
#             f"- {doc.get('title')}: {doc.get('excerpt')}"
#             for doc in documents[:5]
#         ])
#
#         # Use LLM to decide if answer is sufficient or generation needed
#         if not is_claude_enabled():
#             _LOG.warning("Claude not enabled for RAG decision, defaulting to generation")
#             return {
#                 "success": True,
#                 "documents": documents,
#                 "context": doc_context,
#                 "should_answer": False,
#                 "should_generate": True,
#                 "confidence": 0.3,
#                 "answer_preview": "",
#                 "reasoning": "LLM unavailable; recommend generation",
#                 "accumulated_context": {
#                     "rag_documents": documents,
#                     "rag_context": doc_context,
#                     "conversation_digest": conversation_digest,
#                     "plan_payload": plan_payload,
#                     "init_state": init_state
#                 }
#             }
#
#         decision_prompt_system = "You are a RAG decision agent. Based on search results, decide if the information is sufficient to answer directly or if generation is needed."
#         decision_prompt_user = f"""Based on the search results below, decide if:
# 1. The information is SUFFICIENT to answer the user's question directly (should_answer=true)
# 2. The information needs file GENERATION to be properly presented (should_answer=false)
#
# User Query: {user_instruction}
#
# Search Results:
# {doc_context}
#
# Respond with JSON:
# {{
#   "should_answer": true or false,
#   "confidence": 0.0-1.0,
#   "reasoning": "brief explanation",
#   "answer_preview": "if should_answer is true, provide the answer based on docs"
# }}"""
#
#         decision = claude_generate_json(
#             system=decision_prompt_system,
#             user=decision_prompt_user,
#             temperature=0.5,
#             max_tokens=800,
#         )
#
#         increment("rag_search_total")
#         _LOG.info(f"RAG search completed: should_answer={decision.get('should_answer')}")
#
#         return {
#             "success": True,
#             "documents": documents,
#             "context": doc_context,
#             "should_answer": decision.get("should_answer", False),
#             "should_generate": not decision.get("should_answer", True),
#             "confidence": decision.get("confidence", 0.5),
#             "answer_preview": decision.get("answer_preview", "") if decision.get("should_answer") else "",
#             "reasoning": decision.get("reasoning", ""),
#             "accumulated_context": {
#                 "rag_documents": documents,
#                 "rag_context": doc_context,
#                 "conversation_digest": conversation_digest,
#                 "plan_payload": plan_payload,
#                 "init_state": init_state
#             }
#         }
#
#     except Exception as e:
#         _LOG.error(f"RAG agent error: {e}", exc_info=True)
#         return {
#             "success": False,
#             "documents": [],
#             "context": "",
#             "should_answer": False,
#             "should_generate": True,
#             "confidence": 0.0,
#             "answer_preview": "",
#             "reasoning": "RAG search failed",
#             "error": str(e),
#             "accumulated_context": {
#                 "rag_documents": [],
#                 "rag_context": "",
#                 "conversation_digest": conversation_digest,
#                 "plan_payload": plan_payload,
#                 "init_state": init_state
#             }
#         }
