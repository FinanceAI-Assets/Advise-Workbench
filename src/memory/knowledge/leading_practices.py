from __future__ import annotations

import hashlib
from typing import Any

from src.core.cache import cache_service
from src.core.observability.metrics import increment
from src.memory.knowledge import lp_index
from src.memory.knowledge.lp_rag import run_lp_rag


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

        fingerprint = lp_index.load_index().fingerprint
        digest = hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]
        cache_key = f"lpsearch:{fingerprint}:{max_results}:{digest}"
        cached = cache_service.get(cache_key)
        if cached and isinstance(cached, dict) and isinstance(cached.get("results"), list):
            return cached["results"]

        results = run_lp_rag(q, max_results=max_results).get("results") or []
        increment("lp_rag_searches_total")
        cache_service.set(cache_key, {"results": results}, ttl_seconds=300)
        return results

    def answer(self, question: str, *, max_results: int = 5) -> dict[str, Any]:
        """An answer written from the library, with the passages it cites (numbered from 1)."""
        final = run_lp_rag(question.strip(), max_results=max_results, want_answer=True)
        increment("lp_rag_answers_total")
        return {"answer": final.get("answer") or "The Leading Practice library is empty.", "sources": final.get("results") or []}


leading_practice_library_service = LeadingPracticeLibraryService()
