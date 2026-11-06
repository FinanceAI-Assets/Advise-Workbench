"""Query API: the query pipeline over HTTP, for any caller (other services, Postman, tests).

POST   /api/query                          ask: a cited answer from an engagement's documents and/or the library
GET    /api/query/health                   can questions be answered right now; limits
GET    /api/query/sources/{kind}/{id}      a cited source in full (``citations[].link``)

The same pipeline answers inside the app: Sheldon's rag_agent (engagement Conversation) and Talk to data (Leading
Practice Library) call ``src.query.service.ask`` directly. The API is stateless: send earlier turns as ``history``
for follow-up questions. Library content is readable by every signed-in user (released practices only); an
engagement's documents only by its members.
"""

import asyncio
import hashlib
import logging
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.core.auth import get_current_user
from src.core.config import settings
from src.core.db.models import User
from src.core.db.session import get_db
from src.core.rate_limit import limiter
from src.core.vector_db.qdrant_client import get_qdrant_client
from src.llm.claude import is_claude_enabled
from src.query import service
from src.query.pipeline import reranker_name

logger = logging.getLogger(__name__)
router = APIRouter()

Status = Literal["answered", "insufficient_evidence", "llm_unavailable"]
Reason = Literal["no_results", "low_confidence", "low_verification", "model_declined", "uncited_answer", "llm_failed"]
SourceType = Literal["chunk", "wiki"]
QUESTION_MAX_CHARS = 2000
TOP_K_MAX = 12


def _rate_limit() -> str:
    return (settings.query_rate_limit or "30/minute").strip() or "30/minute"


def _caller_key(request: Request) -> str:
    """Rate-limit per signed-in caller (their token), falling back to the client address."""
    auth = request.headers.get("authorization") or ""
    return "q:" + hashlib.sha256(auth.encode()).hexdigest()[:24] if auth else get_remote_address(request)


# --- request / response models -------------------------------------------------------------------------------------


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=QUESTION_MAX_CHARS)
    engagement_id: str | None = Field(default=None, max_length=64,
                                      description="Also search this engagement's uploaded documents (members only)")
    include_library: bool = Field(default=True, description="Search the approved Leading Practice Library")
    practice_ids: list[str] = Field(default_factory=list, max_length=20,
                                    description="Only these library practices (Talk to data: selected sources)")
    history: list[Turn] = Field(default_factory=list, max_length=20, description="Earlier turns, for follow-ups")
    top_k: int | None = Field(default=None, ge=1, le=TOP_K_MAX, description="Sources given to the model (default 10)")


class Understanding(BaseModel):
    intent: Literal["comparison", "recommendation", "procedure", "definition", "reason", "list", "summary",
                    "verification", "fact", "other"]
    question_type: Literal["who", "what", "when", "where", "why", "how", "which", "yes_no", "other"]
    is_follow_up: bool
    context_turns: int = Field(description="Earlier questions of the conversation that were given")
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
    type: SourceType
    scope: Literal["engagement", "library"]
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
    type: SourceType
    scope: Literal["engagement", "library"]
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
    engagement_candidates: int = 0
    verified: int = 0
    dropped_low_verification: int = 0
    top_score: float = 0.0
    reranker: str = "keyword"
    final: int = 0
    pending_documents: list[str] = Field(default_factory=list,
                                         description="Engagement uploads still being processed, so not searched yet")


class AnswerMetadata(BaseModel):
    provider: str | None = None
    model: str | None = None
    attempts: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list, description="[{attempt, kind, message}]; kind: "
                                         "timeout | rate_limit | api_error | not_configured | budget | circuit_open")
    latency_ms: int | None = None
    answer_chars: int | None = None
    context: dict[str, Any] = Field(default_factory=dict, description="{sources, chars, tokens_est, max_tokens}")


class AnswerResponse(BaseModel):
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


class Evidence(BaseModel):
    id: str
    filename: str | None = None
    practice_id: str | None = None
    page_number: int | None = None
    chunk_number: int | None = None
    snippet: str
    link: str


class SourceDetail(BaseModel):
    type: SourceType
    scope: Literal["engagement", "library"]
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
    ready: bool = Field(description="False: questions cannot be answered (search_available or model_available is false)")
    search_available: bool
    model_available: bool
    embedding_model: str
    reranker: str
    limits: dict[str, int]


# --- endpoints ------------------------------------------------------------------------------------------------------


@router.post("", response_model=AnswerResponse)
@limiter.limit(_rate_limit, key_func=_caller_key)
async def ask(
    request: Request, body: QueryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Answer one question. status: answered | insufficient_evidence | llm_unavailable (``reason`` says why).

    403 when ``engagement_id`` is not the caller's engagement; 503 when search (embeddings / Qdrant) is down.
    """
    if not body.engagement_id and not body.include_library:
        raise HTTPException(status_code=422, detail="Nothing to search: give engagement_id or include_library=true")
    scope = service.scope_for(engagement_id=body.engagement_id, include_library=body.include_library,
                              practice_ids=body.practice_ids)
    history = [t.model_dump() for t in body.history]
    try:
        result = await asyncio.to_thread(service.ask, db, user.id, body.question, scope, history=history, top_k=body.top_k)
    except service.AccessDenied as e:
        raise HTTPException(status_code=403, detail="You do not have access to this engagement") from e
    except Exception as e:
        logger.exception("[QUERY] search unavailable")
        raise HTTPException(status_code=503, detail="Search is unavailable right now; try again shortly") from e
    return asdict(result)


@router.get("/health", response_model=Health)
def health(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Whether questions can be answered right now, and the request limits."""
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
        "limits": {"question_max_chars": QUESTION_MAX_CHARS, "top_k_max": TOP_K_MAX, "top_k_default": settings.query_top_k},
    }


@router.get("/sources/{kind}/{source_id}", response_model=SourceDetail)
def get_source(
    kind: SourceType,
    source_id: str,
    engagement_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """A cited passage or wiki page in full; an engagement upload's passage needs ``engagement_id`` (as in
    ``citations[].link``). 404 when it is gone, not part of a released practice, or not in one of the caller's
    engagements."""
    detail = service.source(db, user.id, kind, source_id, engagement_id=engagement_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return detail
