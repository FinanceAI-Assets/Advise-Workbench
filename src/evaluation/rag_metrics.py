"""RAG answer evaluation: retrieval relevance, groundedness, hallucination rate, context utilization, answer relevance.

For each answered question the query pipeline (``src.query.pipeline``) hands over the question, the numbered context
the model was given ([S1] ...) and the answer. One LLM judge call (prompt ``config/prompts/rag_eval.yaml``) decides
which chunks are relevant, which facts of the answer the chunks support, and how well the answer addresses the
question; the counts go to ``advanced_metrics.record_rag_evaluation``:

- retrieval relevance  = relevant chunks / retrieved chunks x 100 (LLM)
- groundedness         = supported facts / total facts x 100 (LLM)
- hallucination rate   = unsupported facts / total facts x 100 (= 100 - groundedness)
- context utilization  = chunks the answer cites / retrieved chunks x 100 (from the citations, no LLM)
- answer relevance     = the judge's 0.0-1.0 score x 100

Retrieval calls and latency are recorded by the pipeline for every query (``record_rag_retrieval_call``).
With ``QUERY_RAG_EVAL=background`` (the default) the judge runs after the answer has been returned, so it adds no
latency; ``off`` disables it.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from dataclasses import dataclass
from typing import Any

from src.core.config import settings
from src.core.observability.advanced_metrics import record_rag_evaluation

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\[S(\d+)\]")
_MAX_ANSWER_CHARS = 6000

_pool: concurrent.futures.ThreadPoolExecutor | None = None


@dataclass
class RagEvaluation:
    retrieved_chunks: int
    utilized_chunks: int
    relevant_chunks: int | None = None
    total_facts: int | None = None
    supported_facts: int | None = None
    answer_relevance: float | None = None  # 0.0-1.0
    judge_error: str | None = None

    def percentages(self) -> dict[str, float | None]:
        def pct(part: float | None, whole: float | None) -> float | None:
            return round(part / whole * 100, 1) if part is not None and whole else None

        unsupported = None if self.total_facts is None or self.supported_facts is None else self.total_facts - self.supported_facts
        return {
            "retrieval_relevance_percent": pct(self.relevant_chunks, self.retrieved_chunks),
            "groundedness_percent": pct(self.supported_facts, self.total_facts),
            "hallucination_rate_percent": pct(unsupported, self.total_facts),
            "context_utilization_percent": pct(self.utilized_chunks, self.retrieved_chunks),
            "answer_relevance_percent": None if self.answer_relevance is None else round(self.answer_relevance * 100, 1),
        }


def utilized_chunks(answer: str, retrieved: int) -> int:
    """Distinct retrieved chunks the answer cites ([S#] markers that point at one of them)."""
    return len({n for n in map(int, _CITATION.findall(answer)) if 1 <= n <= retrieved})


def _judge(question: str, context: str, answer: str) -> dict[str, Any]:
    from src.llm.claude import claude_generate_json
    from src.prompts.registry import get_prompt

    prompt = get_prompt("rag_eval")
    out = claude_generate_json(
        system=prompt.render_system(),
        user=prompt.render_user(question=question, context=context, answer=answer[:_MAX_ANSWER_CHARS]),
        temperature=0.0,
        max_tokens=1500,
    )
    if not isinstance(out, dict):
        raise ValueError(f"judge returned {type(out).__name__}, not a JSON object")
    return out


def _counts(verdict: dict[str, Any], retrieved: int) -> tuple[int, int, int, float | None]:
    """(relevant chunks, total facts, supported facts, answer relevance) from the judge's JSON.

    Only chunks S1..S<retrieved> count, each once; a chunk the judge left out counts as not relevant."""
    relevant: set[int] = set()
    for chunk in verdict.get("chunks") or []:
        match = re.fullmatch(r"\[?S?(\d+)\]?", str(chunk.get("ref", "")).strip(), re.I) if isinstance(chunk, dict) else None
        if match and chunk.get("relevant") is True and 1 <= int(match.group(1)) <= retrieved:
            relevant.add(int(match.group(1)))
    claims = [c for c in verdict.get("claims") or [] if isinstance(c, dict)]
    supported = sum(1 for c in claims if c.get("supported") is True)
    score = verdict.get("answer_relevance")
    try:
        relevance = min(1.0, max(0.0, float(score))) if score is not None else None
    except (TypeError, ValueError):
        relevance = None
    return len(relevant), len(claims), supported, relevance


def evaluate_answer(question: str, context: str, answer: str, retrieved: int) -> RagEvaluation:
    """Judge one answer and record it. ``retrieved``: the chunks numbered S1..S<retrieved> in ``context``."""
    evaluation = RagEvaluation(retrieved_chunks=retrieved, utilized_chunks=utilized_chunks(answer, retrieved))
    try:
        relevant, facts, supported, relevance = _counts(_judge(question, context, answer), retrieved)
        evaluation.relevant_chunks = relevant
        if facts:  # an answer with no factual claim says nothing about groundedness
            evaluation.total_facts, evaluation.supported_facts = facts, supported
        evaluation.answer_relevance = relevance
    except Exception as exc:  # noqa: BLE001 — evaluation must never affect the answer; utilization is still recorded
        evaluation.judge_error = f"{type(exc).__name__}: {exc}"[:300]
        logger.warning("[RAG_EVAL] judge failed, recording context utilization only: %s", evaluation.judge_error)
    record_rag_evaluation(
        retrieved_chunks=evaluation.retrieved_chunks,
        utilized_chunks=evaluation.utilized_chunks,
        relevant_chunks=evaluation.relevant_chunks,
        supported_facts=evaluation.supported_facts,
        total_facts=evaluation.total_facts,
        answer_relevance=evaluation.answer_relevance,
    )
    logger.info("[RAG_EVAL] %s (chunks: %d retrieved, %s relevant, %d cited; facts: %s/%s supported) question=%r",
                {k: v for k, v in evaluation.percentages().items() if v is not None}, evaluation.retrieved_chunks,
                evaluation.relevant_chunks, evaluation.utilized_chunks, evaluation.supported_facts,
                evaluation.total_facts, question[:120])
    return evaluation


def schedule_evaluation(question: str, context: str, answer: str, retrieved: int) -> concurrent.futures.Future | None:
    """Evaluate in the background (``QUERY_RAG_EVAL=background``); None when evaluation is off."""
    global _pool
    if settings.query_rag_eval != "background" or retrieved <= 0:
        return None
    if _pool is None:
        _pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="rag-eval")
    return _pool.submit(evaluate_answer, question, context, answer, retrieved)
