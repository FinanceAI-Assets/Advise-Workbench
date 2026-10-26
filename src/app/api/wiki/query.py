"""Wiki query, context, and lint/health routes.

Moved verbatim from the former single-module app/api/wiki.py.
"""

import asyncio
from typing import Any

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.app.api.wiki._common import logger, _wiki_require_access
from src.app.api.wiki._router import router
from src.core.auth import get_current_user
from src.core.config import settings
from src.core.db.models import User
from src.core.db.session import get_db
from src.memory.knowledge.wiki_integrations import WikiCoordinatorIntegration
from src.memory.knowledge.wiki_operations import wiki_lint_with_retry, wiki_query_with_retry


# ===== Query Operations =====

@router.post("/{wiki_type}/query")
async def query_wiki(
    wiki_type: str,
    question: str,
    project_id: str | None = None,
    include_qa: bool = False,
    max_retries: int = 3,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Query the wiki to answer a question.

    Args:
        wiki_type: "leading_practice" or "project"
        question: Question to ask
        project_id: Project ID for project wiki
        include_qa: Run QA evaluation on answer
        max_retries: Max retry attempts

    Returns:
        {
            "status": "success" | "error",
            "answer": str,
            "citations": [page_ids],
            "source_pages": [page_ids],
            "qa_result": {passed, score, issues} (if include_qa=true),
            "error": str (if failed)
        }
    """
    _wiki_require_access(wiki_type, project_id, user, db, mutating=False)
    if wiki_type == "project" and project_id and settings.document_pipeline_enabled:
        # Project questions take the one query path: verified sources, citations, evidence gate.
        from src.query.pipeline import answer_question, format_answer

        try:
            qr = await asyncio.to_thread(answer_question, db, project_id, question, [])
        except Exception as e:
            return {"status": "error", "error": f"Search is unavailable: {e}"}
        return {
            "status": "success",
            "answer": format_answer(qr),
            "evidence_status": qr.status,
            "citations": [
                (f"Wiki: {c['title']}" if c["type"] == "wiki" else c["filename"])
                + (f", page {c['page_number']}" if c.get("page_number") else "")
                for c in qr.citations
            ],
            "citation_details": qr.citations,
            "source_pages": [s["label"] for s in qr.sources],
            "qa_result": None,
        }
    try:
        result, error = wiki_query_with_retry(
            question=question,
            wiki_type=wiki_type,
            project_id=project_id,
            include_qa=include_qa,
            max_retries=max_retries,
        )

        if error:
            return {
                "status": "error",
                "error": error,
            }

        return {
            "status": "success",
            "answer": result.get("answer"),
            "citations": result.get("citations", []),
            "source_pages": result.get("source_pages", []),
            "qa_result": result.get("qa_result"),
        }

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{wiki_type}/context")
async def get_wiki_context(
    wiki_type: str,
    question: str,
    project_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get wiki context for coordinator run planning.

    Args:
        wiki_type: "leading_practice" or "project"
        question: Planning question
        project_id: Project ID

    Returns:
        {
            "question": str,
            "relevant_pages": [page_dicts],
            "learnings": [learning_dicts],
            "recommendations": [str]
        }
    """
    _wiki_require_access(wiki_type, project_id, user, db, mutating=False)
    try:
        context = WikiCoordinatorIntegration.query_wiki_for_context(
            question, wiki_type, project_id
        )

        return {
            "status": "success",
            "context": context,
        }

    except Exception as e:
        logger.error(f"Context query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ===== Lint/Health Check Operations =====

@router.post("/{wiki_type}/lint")
async def lint_wiki(
    wiki_type: str,
    project_id: str | None = None,
    max_retries: int = 3,
    auto_fix: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Run health check on wiki.

    Args:
        wiki_type: "leading_practice" or "project"
        project_id: Project ID
        max_retries: Max retry attempts
        auto_fix: Auto-apply low-risk fixes

    Returns:
        {
            "status": "success" | "error",
            "issues": [issue_dicts],
            "suggestions": [suggestion_dicts],
            "severity": "low" | "medium" | "high",
            "issues_count": int,
            "auto_fixes_applied": int (if auto_fix=true),
            "error": str (if failed)
        }
    """
    _wiki_require_access(wiki_type, project_id, user, db, mutating=True)
    try:
        result, error = wiki_lint_with_retry(
            wiki_type=wiki_type,
            project_id=project_id,
            max_retries=max_retries,
        )

        if error:
            return {
                "status": "error",
                "error": error,
            }

        return {
            "status": "success",
            "issues": result.get("issues", []),
            "suggestions": result.get("suggestions", []),
            "severity": result.get("severity", "low"),
            "issues_count": result.get("issues_count", 0),
            "suggestions_count": result.get("suggestions_count", 0),
        }

    except Exception as e:
        logger.error(f"Lint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
