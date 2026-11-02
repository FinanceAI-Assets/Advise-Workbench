"""Query API: ask the Leading Practice Library a question and get a cited answer, in a stored conversation.

POST   /api/query                                              ask (new conversation, or a follow-up)
GET    /api/query/health                                       can questions be answered right now; limits
GET    /api/query/conversations                                the caller's conversations, newest first
GET    /api/query/conversations/{id}                           one conversation with every turn
PATCH  /api/query/conversations/{id}                           rename
DELETE /api/query/conversations/{id}                           delete
PUT    /api/query/conversations/{id}/turns/{turn_id}/feedback  rate an answer (up / down, optional comment)
GET    /api/query/sources/{chunk|wiki}/{id}                    a cited source in full (``citations[].link``)
GET    /api/admin/library/query/metrics                        admin: outcomes, latency, model errors, feedback,
                                                               unanswered questions (``admin_router``)

Library content is readable by every signed-in user (as with the Leading Practice Library itself); only the
released version of Approved practices is ever retrieved or shown. Conversations are private to their owner.
"""

import asyncio
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.auth import get_current_user, require_admin
from src.core.config import settings
from src.core.db.models import User, utcnow
from src.core.db.session import get_db
from src.core.vector_db.qdrant_client import get_qdrant_client
from src.llm.claude import is_claude_enabled
from src.query import conversations, events
from src.query.pipeline import answer_question, reranker_name, source_detail
from src.workers.pipeline import LIBRARY_SCOPE

router = APIRouter()
admin_router = APIRouter()

Status = Literal["answered", "insufficient_evidence", "llm_unavailable"]
Reason = Literal["no_results", "low_confidence", "low_verification", "model_declined", "uncited_answer", "llm_failed"]
QUESTION_MAX_CHARS = 2000
TOP_K_MAX = 12


# --- request / response models (the contract the frontend integrates against) --------------------------------------


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=QUESTION_MAX_CHARS)
    conversation_id: str | None = Field(default=None, max_length=64, description="Omit to start a new conversation")
    save: bool = Field(default=True, description="False answers without storing a conversation turn")
    history: list[Turn] = Field(default_factory=list, max_length=20,
                                description="Only for save=false without conversation_id; ignored otherwise")
    top_k: int | None = Field(default=None, ge=1, le=TOP_K_MAX, description="Sources given to the model (default 10)")
    project_id: str | None = Field(default=None, description="Accepted for compatibility; the library is searched")


class Understanding(BaseModel):
    intent: Literal["comparison", "recommendation", "procedure", "definition", "reason", "list", "summary",
                    "verification", "fact", "other"]
    question_type: Literal["who", "what", "when", "where", "why", "how", "which", "yes_no", "other"]
    is_follow_up: bool
    context_turns: int = Field(description="Earlier questions of the conversation that were loaded")
    entities: list[str]
    keywords: list[str]
    language: Literal["en", "other"]


class Variant(BaseModel):
    text: str
    kind: Literal["standalone", "original", "translated", "clarified", "paraphrase", "focused", "keywords"]
    score: float | None = Field(description="Similarity to the main question (0-1)")
    embedded: bool = Field(description="Searched")


class Citation(BaseModel):
    ref: str = Field(description="S1, S2, ... as written in the answer")
    type: Literal["chunk", "wiki"]
    id: str
    title: str
    filename: str | None = None
    page_number: int | None = None
    chunk_number: int | None = None
    practice_id: str | None = None
    practice_title: str | None = None
    supports: str | None = Field(default=None, description="Wiki page id this passage was added as evidence for")
    score: float
    verification: float = Field(description="0-1: 1 for source passages; wiki pages, support by their sources")
    snippet: str
    link: str = Field(description="GET this for the full source")
    markdown: str = Field(description="[Title](id)")


class SourceView(BaseModel):
    type: Literal["chunk", "wiki"]
    id: str
    label: str
    title: str
    filename: str | None = None
    page_number: int | None = None
    practice_id: str | None = None
    practice_title: str | None = None
    score: float
    rank_score: float
    verification: float
    verification_details: dict[str, Any] = Field(description="How the verification score was reached")
    snippet: str
    link: str


class Coverage(BaseModel):
    claims: int = 0
    cited: int = 0
    ratio: float = 0.0
    uncited: list[str] = Field(default_factory=list)
    fully_cited: bool = False
    invalid_refs: list[str] = Field(default_factory=list, description="Removed from the answer")


class Retrieval(BaseModel):
    candidates: int = 0
    verified: int = 0
    dropped_low_verification: int = 0
    top_score: float = 0.0
    reranker: str = "keyword"
    final: int = 0


class AnswerMetadata(BaseModel):
    provider: str | None = None
    model: str | None = None
    attempts: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list, description="[{attempt, kind, message}]; kind: "
                                         "timeout | rate_limit | api_error | not_configured | budget | circuit_open")
    latency_ms: int | None = None
    answer_chars: int | None = None
    context: dict[str, Any] = Field(default_factory=dict, description="{sources, chars, tokens_est, max_tokens}")


class Feedback(BaseModel):
    rating: Literal["up", "down"]
    comment: str = ""
    at: str | None = None


class AnswerTurn(BaseModel):
    id: str | None = Field(default=None, description="Turn id; null when save=false")
    created_at: str | None = None
    status: Status
    reason: Reason | None = None
    question: str
    standalone_question: str
    answer: str = Field(description="Plain text with [S#] markers")
    answer_markdown: str = Field(description="The answer with each [S#] linked to its source id")
    citations: list[Citation]
    sources: list[SourceView] = Field(description="The sources given to the model (answered), else those retrieved")
    coverage: Coverage
    understanding: Understanding
    variants: list[Variant]
    queries: list[str]
    retrieval: Retrieval
    answer_metadata: AnswerMetadata
    model_calls: int
    timings_ms: dict[str, int]
    feedback: Feedback | None = None


class AnswerResponse(AnswerTurn):
    conversation_id: str | None = Field(default=None, description="Send back as conversation_id for follow-ups")
    turn_id: str | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    turn_count: int
    last_question: str | None = None
    last_status: Status | None = None


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    total: int


class Conversation(ConversationSummary):
    turns: list[AnswerTurn]


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    comment: str = Field(default="", max_length=1000)


class Evidence(BaseModel):
    id: str
    filename: str | None = None
    practice_id: str | None = None
    page_number: int | None = None
    chunk_number: int | None = None
    snippet: str
    link: str


class SourceDetail(BaseModel):
    type: Literal["chunk", "wiki"]
    id: str
    label: str
    title: str
    filename: str | None = None
    page_number: int | None = None
    chunk_number: int | None = None
    practice_id: str | None = None
    practice_title: str | None = None
    verification: float
    verification_details: dict[str, Any]
    snippet: str
    link: str
    text: str
    evidence: list[Evidence] = Field(description="Wiki pages: the source passages that support them")


class Health(BaseModel):
    ready: bool = Field(description="False: disable the ask box (search_available or model_available is false)")
    search_available: bool
    model_available: bool
    embedding_model: str
    reranker: str
    limits: dict[str, int]


# --- endpoints ------------------------------------------------------------------------------------------------------


def _conversation_or_404(db: Session, user: User, conversation_id: str) -> dict[str, Any]:
    conversation = conversations.get(db, user.id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("", response_model=AnswerResponse)
async def ask(body: QueryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Answer one question. status: answered | insufficient_evidence | llm_unavailable (``reason`` says why).

    Follow-ups: send the ``conversation_id`` from the previous response; earlier turns are read from the server.
    503 when search itself (embeddings / Qdrant) is unreachable.
    """
    history = [t.model_dump() for t in body.history]
    if body.conversation_id:
        conversation = _conversation_or_404(db, user, body.conversation_id)
        if body.save and conversation["turn_count"] >= conversations.MAX_TURNS:
            raise HTTPException(status_code=409, detail="This conversation is full; start a new one")
        history = conversations.history(conversation)
    try:
        result = await asyncio.to_thread(answer_question, db, LIBRARY_SCOPE, body.question, history, body.top_k)
    except Exception as e:  # embedding service / Qdrant unreachable
        raise HTTPException(status_code=503, detail=f"Search is unavailable: {e}") from e
    if not body.save:
        events.record(db, user.id, result, conversation_id=None, turn_id=None)
        return {**asdict(result), "conversation_id": body.conversation_id}
    try:
        conversation_id, turn = conversations.append(db, user.id, body.conversation_id, result)
    except LookupError as e:
        raise HTTPException(status_code=404, detail="Conversation not found") from e
    except conversations.ConversationFull as e:
        raise HTTPException(status_code=409, detail="This conversation is full; start a new one") from e
    events.record(db, user.id, result, conversation_id=conversation_id, turn_id=turn["id"])
    return {**turn, "conversation_id": conversation_id, "turn_id": turn["id"]}


@router.get("/health", response_model=Health)
def health(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Whether questions can be answered right now, and the request limits for the ask form."""
    try:
        search = get_qdrant_client().health_check()
    except Exception:  # unreachable or misconfigured: report it, do not fail
        search = False
    model = is_claude_enabled()
    return {
        "ready": search and model,
        "search_available": search,
        "model_available": model,
        "embedding_model": settings.embedding_model,
        "reranker": reranker_name(),
        "limits": {"question_max_chars": QUESTION_MAX_CHARS, "top_k_max": TOP_K_MAX, "top_k_default": settings.query_top_k,
                   "max_turns_per_conversation": conversations.MAX_TURNS},
    }


@router.get("/conversations", response_model=ConversationList)
def list_conversations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return conversations.list_for(db, user.id, limit=limit, offset=offset)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _conversation_or_404(db, user, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: str, body: RenameRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    summary = conversations.rename(db, user.id, conversation_id, body.title)
    if summary is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return summary


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    if not conversations.delete(db, user.id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": conversation_id}


@router.put("/conversations/{conversation_id}/turns/{turn_id}/feedback", response_model=AnswerTurn)
def rate_answer(
    conversation_id: str, turn_id: str, body: FeedbackRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Rate one answer; sending again replaces the earlier rating. Admins see ratings in the query metrics."""
    feedback = {"rating": body.rating, "comment": body.comment.strip(), "at": utcnow().isoformat(timespec="seconds")}
    turn = conversations.set_feedback(db, user.id, conversation_id, turn_id, feedback)
    if turn is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    events.set_feedback(db, turn_id, feedback)
    db.commit()
    return turn


@router.get("/sources/{kind}/{source_id}", response_model=SourceDetail)
def get_source(
    kind: Literal["chunk", "wiki"], source_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """A cited passage or wiki page in full. 404 when it is gone or not part of a released practice."""
    detail = source_detail(db, LIBRARY_SCOPE, kind, source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return detail


@admin_router.get("/metrics")
def query_metrics(
    days: int = Query(7, ge=1, le=365),
    top: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Library Q&A over the last ``days``: outcomes by status/reason/intent, answer rate, latency (avg/p50/p95),
    model calls and errors by kind, feedback, the most-asked questions the library could not answer (content
    gaps), and a daily series."""
    return events.summary(db, days=min(days, settings.query_event_retention_days), top=top)
