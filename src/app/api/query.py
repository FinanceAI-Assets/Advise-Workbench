"""Query API: ask a question about a project's ingested documents and get a cited answer."""

import asyncio
from dataclasses import asdict
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.auth import get_current_user, require_project_role
from src.core.db.models import User
from src.core.db.session import get_db
from src.query.pipeline import answer_question

router = APIRouter()


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class QueryRequest(BaseModel):
    project_id: str
    question: str = Field(min_length=2, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=20)
    top_k: Optional[int] = Field(default=None, ge=1, le=12)


@router.post("")
async def ask(body: QueryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """status: answered | insufficient_evidence | llm_unavailable; citations reference [S#] markers in answer."""
    require_project_role(body.project_id, {"Owner", "Editor", "Viewer"}, user, db)
    try:
        result = await asyncio.to_thread(
            answer_question, db, body.project_id, body.question, [t.model_dump() for t in body.history], body.top_k
        )
    except Exception as e:  # embedding service / Qdrant unreachable
        raise HTTPException(status_code=503, detail=f"Search is unavailable: {e}") from e
    return asdict(result)
