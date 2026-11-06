"""RAG answer evaluation: the five percentages from one LLM-judge verdict, and how they are aggregated."""

from __future__ import annotations

import pytest

from src.core.observability import advanced_metrics as am
from src.evaluation import rag_metrics

CONTEXT = "[S1] policy.pdf\nBank changes need AP approval.\n\n[S2] notes.txt\nTurnaround is 9 days.\n\n[S3] menu.txt\nLunch is at noon."
ANSWER = "Bank changes need AP approval [S1]. Turnaround is 9 days [S2]. It is fully automated."


@pytest.fixture(autouse=True)
def fresh_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {"_RAG_RELEVANT_CHUNKS": 0, "_RAG_JUDGED_CHUNKS": 0, "_RAG_TOTAL_CHUNKS_RETRIEVED": 0,
                        "_RAG_SUPPORTED_FACTS": 0, "_RAG_TOTAL_FACTS": 0, "_RAG_UTILIZED_CHUNKS": 0,
                        "_RAG_ANSWER_RELEVANCE_TOTAL": 0.0, "_RAG_ANSWER_RELEVANCE_COUNT": 0,
                        "_RAG_EVALUATED_ANSWERS": 0, "_RAG_TOTAL_RETRIEVAL_TIME_MS": 0.0,
                        "_RAG_RETRIEVAL_CALL_COUNT": 0}.items():
        monkeypatch.setattr(am, name, value)


def _verdict(*_: object, **__: object) -> dict:
    return {
        "chunks": [{"ref": "S1", "relevant": True}, {"ref": "S2", "relevant": True}, {"ref": "S3", "relevant": False}],
        "claims": [{"claim": "AP approval", "supported": True}, {"claim": "9 days", "supported": True},
                   {"claim": "automated", "supported": False}],
        "answer_relevance": 0.8,
    }


def test_one_answer_gives_the_five_percentages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag_metrics, "_judge", _verdict)
    evaluation = rag_metrics.evaluate_answer("What do bank changes need?", CONTEXT, ANSWER, retrieved=3)

    assert evaluation.percentages() == {
        "retrieval_relevance_percent": 66.7,  # 2 of 3 chunks relevant
        "groundedness_percent": 66.7,  # 2 of 3 facts supported
        "hallucination_rate_percent": 33.3,  # 1 of 3 facts unsupported = 100 - groundedness
        "context_utilization_percent": 66.7,  # S1 and S2 cited, S3 not
        "answer_relevance_percent": 80.0,
    }
    rag = am.get_rag_metrics()
    assert rag["retrieval_relevance_percent"] == 66.67
    assert rag["hallucination_rate_percent"] == round(100 - rag["groundedness_percent"], 2)
    assert rag["evaluated_answers"] == 1


def test_metrics_aggregate_over_answers_by_counts_not_by_averaging_percentages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag_metrics, "_judge", _verdict)
    rag_metrics.evaluate_answer("q1", CONTEXT, ANSWER, retrieved=3)  # 2/3 relevant
    monkeypatch.setattr(rag_metrics, "_judge", lambda *a, **k: {
        "chunks": [{"ref": "S1", "relevant": True}], "claims": [{"claim": "x", "supported": True}], "answer_relevance": 1.0})
    rag_metrics.evaluate_answer("q2", "[S1] a\nx", "x [S1]", retrieved=1)  # 1/1 relevant

    rag = am.get_rag_metrics()
    assert rag["retrieval_relevance_percent"] == 75.0  # 3 relevant / 4 retrieved, not the mean of 66.7 and 100
    assert rag["groundedness_percent"] == 75.0  # 3 supported / 4 facts
    assert rag["answer_relevance_percent"] == 90.0


def test_a_failed_judge_records_context_utilization_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_: object, **__: object) -> dict:
        raise TimeoutError("judge timed out")

    monkeypatch.setattr(rag_metrics, "_judge", broken)
    evaluation = rag_metrics.evaluate_answer("q", CONTEXT, ANSWER, retrieved=3)

    assert evaluation.judge_error and evaluation.relevant_chunks is None
    rag = am.get_rag_metrics()
    assert rag["context_utilization_percent"] == 66.67
    assert rag["retrieval_relevance_percent"] == 0 and rag["judged_chunks"] == 0  # not counted as 0 relevant


def test_judge_output_is_read_defensively(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag_metrics, "_judge", lambda *a, **k: {
        "chunks": [{"ref": "[S1]", "relevant": True}, {"ref": "S1", "relevant": True},  # same chunk twice
                   {"ref": "S9", "relevant": True}, {"ref": "S2", "relevant": "yes"}],  # unknown ref, not a bool
        "claims": [], "answer_relevance": 7})
    evaluation = rag_metrics.evaluate_answer("q", CONTEXT, ANSWER, retrieved=3)

    assert evaluation.relevant_chunks == 1
    assert evaluation.total_facts is None  # no claims: says nothing about groundedness
    assert evaluation.answer_relevance == 1.0  # clamped to 0..1


def test_retrieval_calls_and_average_latency() -> None:
    for ms in (100, 300):
        am.record_rag_retrieval_call(ms)
    rag = am.get_rag_metrics()
    assert rag["total_retrievals"] == 2 and rag["avg_retrieval_latency_ms"] == 200.0


def test_evaluation_runs_in_the_background_unless_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag_metrics, "_judge", _verdict)
    monkeypatch.setattr(rag_metrics.settings, "query_rag_eval", "background")
    rag_metrics.schedule_evaluation("q", CONTEXT, ANSWER, 3).result(timeout=10)
    assert am.get_rag_metrics()["evaluated_answers"] == 1

    monkeypatch.setattr(rag_metrics.settings, "query_rag_eval", "off")
    assert rag_metrics.schedule_evaluation("q", CONTEXT, ANSWER, 3) is None
