from __future__ import annotations

import hashlib
import logging
from typing import Any

from src.core.cache import cache_service
from src.core.observability.metrics import increment
from src.memory.knowledge import lp_index
from src.memory.knowledge.lp_rag import run_lp_rag

_LOG = logging.getLogger(__name__)


class LeadingPracticeLibraryService:
    """
    Leading Practice Library (LP) retrieval service.

    Searches go through the LangGraph retrieval pipeline in ``lp_rag.py``; the passages come from
    the index in ``lp_index.py`` (the ``LP_LIBRARY_LOCAL_PATH`` folder and the leading-practice wiki).
    With an empty library, ``search`` returns [].
    """

    def ensure_index(self, *, force: bool = False) -> None:
        lp_index.load_index(force=force)

    def search(
        self,
        query: str,
        *,
        project_id: str | None = None,
        dpdp_enabled: bool = False,  # placeholder for later DPDP tagging exclusions
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []

        scoped_practice_ids: list[str] | None = None
        if project_id:
            # Engagement-scoped mode: use only practices explicitly linked to this engagement.
            try:
                from src.core.db.session import session_scope
                from src.query import service as query_service

                with session_scope() as db:
                    scoped_practice_ids = query_service.engagement_practice_ids(db, project_id)
            except Exception as exc:
                _LOG.warning("LP search scope lookup failed for project=%s: %s", project_id, exc)
                scoped_practice_ids = []
            # No linked practices means no LP retrieval for this engagement.
            if not scoped_practice_ids:
                return []

        fingerprint = lp_index.load_index().fingerprint
        digest = hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]
        scope_sig = f"project:{project_id}:{','.join(scoped_practice_ids)}" if project_id else "global"
        cache_key = f"lpsearch:{fingerprint}:{scope_sig}:{max_results}:{digest}"
        cached = cache_service.get(cache_key)
        if cached and isinstance(cached, dict) and isinstance(cached.get("results"), list):
            return cached["results"]

        results = run_lp_rag(q, max_results=max_results, practice_ids=scoped_practice_ids).get("results") or []
        increment("lp_rag_searches_total")
        cache_service.set(cache_key, {"results": results}, ttl_seconds=300)
        return results

    def answer(self, question: str, *, max_results: int = 5, practice_ids: list[str] | None = None) -> dict[str, Any]:
        """An answer written from the library, with the passages it cites (numbered from 1).

        ``practice_ids`` limits the passages to those published practices.
        """
        final = run_lp_rag(question.strip(), max_results=max_results, want_answer=True, practice_ids=practice_ids)
        increment("lp_rag_answers_total")
        return {"answer": final.get("answer") or "The Leading Practice library is empty.", "sources": final.get("results") or []}


leading_practice_library_service = LeadingPracticeLibraryService()
