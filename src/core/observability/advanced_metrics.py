"""
Advanced Production-Grade Metrics (Agent, RAG, Tool, App, Quality).
Supports per-project aggregation, per-run tracking, and global metrics.
See docs/METRICS_INTEGRATION_GUIDE.md
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any
import time
import logging

logger = logging.getLogger(__name__)

from src.core.observability.metrics import increment, observe_latency, set_gauge

_LOCK = Lock()

# ============================================================================
# GLOBAL METRICS (all-time aggregate across all projects)
# ============================================================================

# Agent metrics - keyed by agent_name
_AGENT_CALLS: dict[str, int] = defaultdict(int)
_AGENT_RETRIES: dict[str, int] = defaultdict(int)
_AGENT_TOTAL_LATENCY_MS: dict[str, float] = defaultdict(float)
_AGENT_LATENCY_COUNT: dict[str, int] = defaultdict(int)
_AGENT_SUCCESSES: dict[str, int] = defaultdict(int)
_AGENT_TOTAL_TASKS: dict[str, int] = defaultdict(int)

# Per-Project Agent Metrics
_PROJECT_AGENT_RUNS: dict[tuple[str, str], int] = defaultdict(int)  # (project_id, agent_name) -> run_count

# RAG metrics
_RAG_RELEVANT_CHUNKS: int = 0
_RAG_TOTAL_CHUNKS_RETRIEVED: int = 0
_RAG_SUPPORTED_FACTS: int = 0
_RAG_TOTAL_FACTS: int = 0
_RAG_UTILIZED_CHUNKS: int = 0
_RAG_TOTAL_RETRIEVAL_TIME_MS: float = 0.0
_RAG_RETRIEVAL_CALL_COUNT: int = 0

# Tool metrics
_TOOL_CALLS_SUCCESS: int = 0
_TOOL_CALLS_TOTAL: int = 0
_TOOL_CALLS_NECESSARY: int = 0
_TOOL_TOTAL_LATENCY_MS: float = 0.0
_TOOL_LATENCY_COUNT: int = 0

# Application metrics
_APP_FAILED_REQUESTS: int = 0
_APP_TOTAL_REQUESTS: int = 0
_APP_TOTAL_COST: float = 0.0
_APP_CONCURRENT_REQUESTS: int = 0
_APP_TOTAL_LATENCY_MS: float = 0.0
_APP_LATENCY_COUNT: int = 0
_APP_REQUEST_TIMESTAMPS: list[float] = []

# Per-Project Application Metrics
_PROJECT_RUNS: dict[str, int] = defaultdict(int)  # project_id -> total runs in project

# Quality Evaluation Metrics - GLOBAL (4 evaluation metrics + 2 aggregate)
_QUALITY_EVAL_RUNS_TOTAL: int = 0
_QUALITY_EVAL_COMPLETENESS_TOTAL: float = 0.0
_QUALITY_EVAL_COMPLETENESS_COUNT: int = 0
_QUALITY_EVAL_CLARITY_TOTAL: float = 0.0
_QUALITY_EVAL_CLARITY_COUNT: int = 0
_QUALITY_EVAL_FAITHFULNESS_TOTAL: float = 0.0
_QUALITY_EVAL_FAITHFULNESS_COUNT: int = 0
_QUALITY_EVAL_ACCURACY_TOTAL: float = 0.0
_QUALITY_EVAL_ACCURACY_COUNT: int = 0
_QUALITY_EVAL_GRADE_TOTAL: float = 0.0
_QUALITY_EVAL_GRADE_COUNT: int = 0
_QUALITY_EVAL_SCORE_TOTAL: float = 0.0
_QUALITY_EVAL_SCORE_COUNT: int = 0
_QUALITY_EVAL_PASSED: int = 0
_QUALITY_EVAL_FAILED: int = 0

# Per-Project Quality Metrics
_PROJECT_QUALITY_RUNS: dict[str, int] = defaultdict(int)  # project_id -> quality eval runs in project


# ============================================================================
# AGENT METRICS - Per Agent, Per Project
# ============================================================================

def record_agent_call(agent_name: str, duration_ms: float, success: bool, is_retry: bool = False, project_id: str | None = None) -> None:
    """Record agent execution with per-project tracking."""
    print(f"[METRICS] record_agent_call: agent={agent_name}, duration={duration_ms}ms, success={success}, project_id={project_id}")
    logger.info(f"[AGENT_METRICS] Recording: agent={agent_name}, duration={duration_ms}ms, success={success}, project={project_id}")
    with _LOCK:
        # Global metrics
        _AGENT_CALLS[agent_name] += 1
        _AGENT_TOTAL_LATENCY_MS[agent_name] += duration_ms
        _AGENT_LATENCY_COUNT[agent_name] += 1
        if is_retry:
            _AGENT_RETRIES[agent_name] += 1
        if success:
            _AGENT_SUCCESSES[agent_name] += 1
        _AGENT_TOTAL_TASKS[agent_name] += 1

        # Per-project metrics
        if project_id:
            _PROJECT_AGENT_RUNS[(project_id, agent_name)] += 1

        # Export to OTEL
        increment(f"agent_{agent_name}_call_count_total")
        observe_latency(f"agent_{agent_name}_latency_ms", duration_ms)
        if is_retry:
            increment(f"agent_{agent_name}_retry_total")
        if success:
            increment(f"agent_{agent_name}_task_success_total")

        # Update rates
        total_calls = _AGENT_CALLS[agent_name]
        if total_calls > 0:
            retry_rate = (_AGENT_RETRIES[agent_name] / total_calls) * 100
            set_gauge(f"agent_{agent_name}_retry_rate_percent", retry_rate)
        total_tasks = _AGENT_TOTAL_TASKS[agent_name]
        if total_tasks > 0:
            completion_rate = (_AGENT_SUCCESSES[agent_name] / total_tasks) * 100
            set_gauge(f"agent_{agent_name}_completion_rate_percent", completion_rate)

        print(f"[METRICS] agent metrics updated: {agent_name} - calls={_AGENT_CALLS[agent_name]}, successes={_AGENT_SUCCESSES[agent_name]}")


# ============================================================================
# RAG METRICS
# ============================================================================

def record_rag_retrieval(relevant_chunks: int, total_chunks: int, supported_facts: int, total_facts: int, utilized_chunks: int, retrieval_latency_ms: float) -> None:
    print(f"[METRICS] record_rag_retrieval called: relevant={relevant_chunks}/{total_chunks}, facts={supported_facts}/{total_facts}, utilized={utilized_chunks}, latency={retrieval_latency_ms}ms")
    with _LOCK:
        global _RAG_RELEVANT_CHUNKS, _RAG_TOTAL_CHUNKS_RETRIEVED, _RAG_SUPPORTED_FACTS, _RAG_TOTAL_FACTS, _RAG_UTILIZED_CHUNKS, _RAG_TOTAL_RETRIEVAL_TIME_MS, _RAG_RETRIEVAL_CALL_COUNT

        _RAG_RELEVANT_CHUNKS += relevant_chunks
        _RAG_TOTAL_CHUNKS_RETRIEVED += total_chunks
        _RAG_SUPPORTED_FACTS += supported_facts
        _RAG_TOTAL_FACTS += total_facts
        _RAG_UTILIZED_CHUNKS += utilized_chunks
        _RAG_TOTAL_RETRIEVAL_TIME_MS += retrieval_latency_ms
        _RAG_RETRIEVAL_CALL_COUNT += 1
        print(f"[METRICS] rag metrics updated: retrievals={_RAG_RETRIEVAL_CALL_COUNT}, total_chunks={_RAG_TOTAL_CHUNKS_RETRIEVED}")

        increment("rag_relevant_chunks_total", relevant_chunks)
        increment("rag_retrieved_chunks_total", total_chunks)
        increment("rag_supported_facts_total", supported_facts)
        increment("rag_total_facts_total", total_facts)
        increment("rag_utilized_chunks_total", utilized_chunks)
        observe_latency("rag_retrieval_latency_ms", retrieval_latency_ms)

        if total_chunks > 0:
            relevance = (relevant_chunks / total_chunks) * 100
            set_gauge("rag_retrieval_relevance_percent", relevance)
        if total_facts > 0:
            groundedness = (supported_facts / total_facts) * 100
            set_gauge("rag_groundedness_percent", groundedness)
        if total_chunks > 0:
            utilization = (utilized_chunks / total_chunks) * 100
            set_gauge("rag_context_utilization_percent", utilization)


# ============================================================================
# TOOL METRICS
# ============================================================================

def record_tool_call(duration_ms: float, success: bool, necessary: bool = True) -> None:
    print(f"[METRICS] record_tool_call called: duration={duration_ms}ms, success={success}, necessary={necessary}")
    with _LOCK:
        global _TOOL_CALLS_SUCCESS, _TOOL_CALLS_TOTAL, _TOOL_CALLS_NECESSARY, _TOOL_TOTAL_LATENCY_MS, _TOOL_LATENCY_COUNT

        _TOOL_CALLS_TOTAL += 1
        _TOOL_TOTAL_LATENCY_MS += duration_ms
        _TOOL_LATENCY_COUNT += 1
        if success:
            _TOOL_CALLS_SUCCESS += 1
        if necessary:
            _TOOL_CALLS_NECESSARY += 1

        print(f"[METRICS] tool metrics updated: total_calls={_TOOL_CALLS_TOTAL}, success={_TOOL_CALLS_SUCCESS}, necessary={_TOOL_CALLS_NECESSARY}")

        increment("tool_calls_total")
        observe_latency("tool_call_latency_ms", duration_ms)
        if success:
            increment("tool_calls_success_total")
        if necessary:
            increment("tool_calls_necessary_total")

        success_rate = (_TOOL_CALLS_SUCCESS / _TOOL_CALLS_TOTAL * 100) if _TOOL_CALLS_TOTAL > 0 else 0
        necessity_rate = (_TOOL_CALLS_NECESSARY / _TOOL_CALLS_TOTAL * 100) if _TOOL_CALLS_TOTAL > 0 else 0
        set_gauge("tool_calls_success_rate_percent", success_rate)
        set_gauge("tool_calls_necessity_rate_percent", necessity_rate)


# ============================================================================
# APPLICATION METRICS - Per Project Per Run
# ============================================================================

def record_application_request(duration_ms: float, success: bool, cost: float = 0.0, project_id: str | None = None) -> None:
    """Record application request with per-project tracking."""
    logger.info(f"[APP_METRICS_RECORD] Called: duration={duration_ms}ms, success={success}, cost=${cost}, project_id={project_id}")
    with _LOCK:
        global _APP_FAILED_REQUESTS, _APP_TOTAL_REQUESTS, _APP_TOTAL_COST, _APP_TOTAL_LATENCY_MS, _APP_LATENCY_COUNT

        _APP_TOTAL_REQUESTS += 1
        _APP_TOTAL_LATENCY_MS += duration_ms
        _APP_LATENCY_COUNT += 1
        _APP_TOTAL_COST += cost
        if not success:
            _APP_FAILED_REQUESTS += 1

        # Per-project metrics
        if project_id:
            _PROJECT_RUNS[project_id] += 1

        increment("app_requests_total")
        observe_latency("app_request_latency_ms", duration_ms)
        increment("app_cost_total", cost)
        if not success:
            increment("app_failed_requests_total")

        failure_rate = (_APP_FAILED_REQUESTS / _APP_TOTAL_REQUESTS * 100) if _APP_TOTAL_REQUESTS > 0 else 0
        avg_cost = _APP_TOTAL_COST / _APP_TOTAL_REQUESTS if _APP_TOTAL_REQUESTS > 0 else 0
        set_gauge("app_failure_rate_percent", failure_rate)
        set_gauge("app_avg_cost", avg_cost)
        logger.info(f"[APP_METRICS_UPDATED] total_requests={_APP_TOTAL_REQUESTS}, total_cost=${_APP_TOTAL_COST:.4f}, failure_rate={failure_rate:.1f}%")

        print(f"[METRICS] app metrics updated: total_requests={_APP_TOTAL_REQUESTS}, total_cost=${_APP_TOTAL_COST:.4f}, failure_rate={failure_rate:.1f}%")


def set_application_concurrent_requests(count: int) -> None:
    with _LOCK:
        global _APP_CONCURRENT_REQUESTS
        _APP_CONCURRENT_REQUESTS = count
        set_gauge("app_concurrent_requests", count)


# ============================================================================
# QUALITY EVALUATION METRICS - 4 Metrics Per Project Per Run
# ============================================================================

def record_quality_evaluation(
    completeness: float,
    clarity_readability: float,
    faithfulness_usefulness: float,
    content_accuracy: float,
    grade: float | None = None,
    score: float | None = None,
    project_id: str | None = None,
) -> None:
    """Record quality evaluation with 4 evaluation metrics + aggregate metrics.

    Args:
        completeness: 0.0-1.0, does output cover all required aspects?
        clarity_readability: 0.0-1.0, is output clear and well-structured?
        faithfulness_usefulness: 0.0-1.0, is output faithful to source and useful?
        content_accuracy: 0.0-1.0, is output factually accurate?
        grade: Optional aggregate grade (0.0-1.0). If None, auto-calculated as average of 4 metrics.
        score: Optional aggregate score (0.0-1.0). If None, auto-calculated as average of 4 metrics.
        project_id: Optional project ID for per-project aggregation
    """
    with _LOCK:
        global _QUALITY_EVAL_RUNS_TOTAL, _QUALITY_EVAL_COMPLETENESS_TOTAL, _QUALITY_EVAL_COMPLETENESS_COUNT
        global _QUALITY_EVAL_CLARITY_TOTAL, _QUALITY_EVAL_CLARITY_COUNT, _QUALITY_EVAL_FAITHFULNESS_TOTAL
        global _QUALITY_EVAL_FAITHFULNESS_COUNT, _QUALITY_EVAL_ACCURACY_TOTAL, _QUALITY_EVAL_ACCURACY_COUNT
        global _QUALITY_EVAL_GRADE_TOTAL, _QUALITY_EVAL_GRADE_COUNT, _QUALITY_EVAL_SCORE_TOTAL, _QUALITY_EVAL_SCORE_COUNT
        global _QUALITY_EVAL_PASSED, _QUALITY_EVAL_FAILED

        _QUALITY_EVAL_RUNS_TOTAL += 1
        _QUALITY_EVAL_COMPLETENESS_TOTAL += completeness
        _QUALITY_EVAL_COMPLETENESS_COUNT += 1
        _QUALITY_EVAL_CLARITY_TOTAL += clarity_readability
        _QUALITY_EVAL_CLARITY_COUNT += 1
        _QUALITY_EVAL_FAITHFULNESS_TOTAL += faithfulness_usefulness
        _QUALITY_EVAL_FAITHFULNESS_COUNT += 1
        _QUALITY_EVAL_ACCURACY_TOTAL += content_accuracy
        _QUALITY_EVAL_ACCURACY_COUNT += 1

        # Auto-calculate grade and score as average of 4 metrics if not provided
        avg_metric = (completeness + clarity_readability + faithfulness_usefulness + content_accuracy) / 4

        # Convert grade to float if it's a string (A=0.9, B=0.8, C=0.7, D=0.6, F=0.5)
        if isinstance(grade, str):
            grade_map = {'A': 0.9, 'B': 0.8, 'C': 0.7, 'D': 0.6, 'F': 0.5}
            calc_grade = grade_map.get(grade.upper(), avg_metric)
        else:
            calc_grade = grade if grade is not None else avg_metric

        calc_score = score if score is not None else avg_metric

        _QUALITY_EVAL_GRADE_TOTAL += calc_grade
        _QUALITY_EVAL_GRADE_COUNT += 1
        _QUALITY_EVAL_SCORE_TOTAL += calc_score
        _QUALITY_EVAL_SCORE_COUNT += 1

        # Determine pass: all 4 metrics must be >= 0.7 (70%)
        passed = all([
            completeness >= 0.7,
            clarity_readability >= 0.7,
            faithfulness_usefulness >= 0.7,
            content_accuracy >= 0.7,
        ])
        if passed:
            _QUALITY_EVAL_PASSED += 1
        else:
            _QUALITY_EVAL_FAILED += 1

        # Per-project metrics
        if project_id:
            _PROJECT_QUALITY_RUNS[project_id] += 1

        # Export to OTEL (4 evaluation metrics + grade + score)
        increment("quality_eval_runs_total")
        increment("quality_eval_completeness_total", int(completeness * 100))
        increment("quality_eval_clarity_total", int(clarity_readability * 100))
        increment("quality_eval_faithfulness_total", int(faithfulness_usefulness * 100))
        increment("quality_eval_accuracy_total", int(content_accuracy * 100))
        increment("quality_eval_grade_total", int(calc_grade * 100))
        increment("quality_eval_score_total", int(calc_score * 100))
        if passed:
            increment("quality_eval_passed_total")
        else:
            increment("quality_eval_failed_total")

        # Update gauges - all 4 metrics + grade + score
        avg_completeness = _QUALITY_EVAL_COMPLETENESS_TOTAL / _QUALITY_EVAL_COMPLETENESS_COUNT if _QUALITY_EVAL_COMPLETENESS_COUNT > 0 else 0
        avg_clarity = _QUALITY_EVAL_CLARITY_TOTAL / _QUALITY_EVAL_CLARITY_COUNT if _QUALITY_EVAL_CLARITY_COUNT > 0 else 0
        avg_faithfulness = _QUALITY_EVAL_FAITHFULNESS_TOTAL / _QUALITY_EVAL_FAITHFULNESS_COUNT if _QUALITY_EVAL_FAITHFULNESS_COUNT > 0 else 0
        avg_accuracy = _QUALITY_EVAL_ACCURACY_TOTAL / _QUALITY_EVAL_ACCURACY_COUNT if _QUALITY_EVAL_ACCURACY_COUNT > 0 else 0
        avg_grade = _QUALITY_EVAL_GRADE_TOTAL / _QUALITY_EVAL_GRADE_COUNT if _QUALITY_EVAL_GRADE_COUNT > 0 else 0
        avg_score = _QUALITY_EVAL_SCORE_TOTAL / _QUALITY_EVAL_SCORE_COUNT if _QUALITY_EVAL_SCORE_COUNT > 0 else 0

        set_gauge("quality_eval_avg_completeness", avg_completeness)
        set_gauge("quality_eval_avg_clarity", avg_clarity)
        set_gauge("quality_eval_avg_faithfulness", avg_faithfulness)
        set_gauge("quality_eval_avg_accuracy", avg_accuracy)
        set_gauge("quality_eval_avg_grade", avg_grade)
        set_gauge("quality_eval_avg_score", avg_score)

        pass_rate = (_QUALITY_EVAL_PASSED / _QUALITY_EVAL_RUNS_TOTAL * 100) if _QUALITY_EVAL_RUNS_TOTAL > 0 else 0
        set_gauge("quality_eval_pass_rate_percent", pass_rate)


# ============================================================================
# SNAPSHOTS FOR API RESPONSES
# ============================================================================

def get_agent_metrics(project_id: str | None = None) -> dict[str, Any]:
    """Get agent metrics, optionally scoped to project."""
    with _LOCK:
        result = {}
        for agent_name in set(_AGENT_CALLS.keys()) | set(_AGENT_RETRIES.keys()):
            total_calls = _AGENT_CALLS[agent_name]
            total_tasks = _AGENT_TOTAL_TASKS[agent_name]
            result[agent_name] = {
                "call_count_total": total_calls,
                "retry_rate_percent": (_AGENT_RETRIES[agent_name] / total_calls * 100) if total_calls > 0 else 0,
                "avg_latency_ms": round(_AGENT_TOTAL_LATENCY_MS[agent_name] / _AGENT_LATENCY_COUNT[agent_name], 2) if _AGENT_LATENCY_COUNT[agent_name] > 0 else 0,
                "task_completion_rate_percent": (_AGENT_SUCCESSES[agent_name] / total_tasks * 100) if total_tasks > 0 else 0,
            }
            if project_id:
                project_runs = _PROJECT_AGENT_RUNS.get((project_id, agent_name), 0)
                result[agent_name]["runs_in_project"] = project_runs
        return result


def get_rag_metrics() -> dict[str, Any]:
    with _LOCK:
        return {
            "retrieval_relevance_percent": (_RAG_RELEVANT_CHUNKS / _RAG_TOTAL_CHUNKS_RETRIEVED * 100) if _RAG_TOTAL_CHUNKS_RETRIEVED > 0 else 0,
            "groundedness_percent": (_RAG_SUPPORTED_FACTS / _RAG_TOTAL_FACTS * 100) if _RAG_TOTAL_FACTS > 0 else 0,
            "context_utilization_percent": (_RAG_UTILIZED_CHUNKS / _RAG_TOTAL_CHUNKS_RETRIEVED * 100) if _RAG_TOTAL_CHUNKS_RETRIEVED > 0 else 0,
            "avg_retrieval_latency_ms": round(_RAG_TOTAL_RETRIEVAL_TIME_MS / _RAG_RETRIEVAL_CALL_COUNT, 2) if _RAG_RETRIEVAL_CALL_COUNT > 0 else 0,
            "total_retrievals": _RAG_RETRIEVAL_CALL_COUNT,
        }


def get_tool_metrics() -> dict[str, Any]:
    with _LOCK:
        return {
            "calls_success_rate_percent": (_TOOL_CALLS_SUCCESS / _TOOL_CALLS_TOTAL * 100) if _TOOL_CALLS_TOTAL > 0 else 0,
            "calls_necessity_rate_percent": (_TOOL_CALLS_NECESSARY / _TOOL_CALLS_TOTAL * 100) if _TOOL_CALLS_TOTAL > 0 else 0,
            "avg_latency_ms": round(_TOOL_TOTAL_LATENCY_MS / _TOOL_LATENCY_COUNT, 2) if _TOOL_LATENCY_COUNT > 0 else 0,
            "total_calls": _TOOL_CALLS_TOTAL,
        }


def get_application_metrics(project_id: str | None = None) -> dict[str, Any]:
    with _LOCK:
        avg_latency = round(_APP_TOTAL_LATENCY_MS / _APP_LATENCY_COUNT, 2) if _APP_LATENCY_COUNT > 0 else 0
        avg_cost = round(_APP_TOTAL_COST / _APP_TOTAL_REQUESTS, 4) if _APP_TOTAL_REQUESTS > 0 else 0
        failure_rate = (_APP_FAILED_REQUESTS / _APP_TOTAL_REQUESTS * 100) if _APP_TOTAL_REQUESTS > 0 else 0
        now = time.time()
        recent_timestamps = [ts for ts in _APP_REQUEST_TIMESTAMPS if now - ts < 60]
        throughput = len(recent_timestamps)

        efficiency_score = (100 - failure_rate) if failure_rate >= 0 else 100

        metrics = {
            "failure_rate_percent": failure_rate,
            "efficiency_score_percent": round(efficiency_score, 2),
            "avg_cost": avg_cost,
            "concurrent_requests": _APP_CONCURRENT_REQUESTS,
            "avg_latency_ms": avg_latency,
            "total_requests": _APP_TOTAL_REQUESTS,
            "total_cost": round(_APP_TOTAL_COST, 4),
            "throughput_requests_per_minute": throughput,
        }

        if project_id:
            metrics["runs_in_project"] = _PROJECT_RUNS.get(project_id, 0)

        return metrics


def get_quality_evaluation_metrics(project_id: str | None = None) -> dict[str, Any]:
    with _LOCK:
        metrics = {
            "runs_total": _QUALITY_EVAL_RUNS_TOTAL,
            "avg_completeness": round(_QUALITY_EVAL_COMPLETENESS_TOTAL / _QUALITY_EVAL_COMPLETENESS_COUNT, 4) if _QUALITY_EVAL_COMPLETENESS_COUNT > 0 else 0,
            "avg_clarity_readability": round(_QUALITY_EVAL_CLARITY_TOTAL / _QUALITY_EVAL_CLARITY_COUNT, 4) if _QUALITY_EVAL_CLARITY_COUNT > 0 else 0,
            "avg_faithfulness_usefulness": round(_QUALITY_EVAL_FAITHFULNESS_TOTAL / _QUALITY_EVAL_FAITHFULNESS_COUNT, 4) if _QUALITY_EVAL_FAITHFULNESS_COUNT > 0 else 0,
            "avg_content_accuracy": round(_QUALITY_EVAL_ACCURACY_TOTAL / _QUALITY_EVAL_ACCURACY_COUNT, 4) if _QUALITY_EVAL_ACCURACY_COUNT > 0 else 0,
            "avg_grade": round(_QUALITY_EVAL_GRADE_TOTAL / _QUALITY_EVAL_GRADE_COUNT, 4) if _QUALITY_EVAL_GRADE_COUNT > 0 else 0,
            "avg_score": round(_QUALITY_EVAL_SCORE_TOTAL / _QUALITY_EVAL_SCORE_COUNT, 4) if _QUALITY_EVAL_SCORE_COUNT > 0 else 0,
            "pass_rate_percent": (_QUALITY_EVAL_PASSED / _QUALITY_EVAL_RUNS_TOTAL * 100) if _QUALITY_EVAL_RUNS_TOTAL > 0 else 0,
            "passed_total": _QUALITY_EVAL_PASSED,
            "failed_total": _QUALITY_EVAL_FAILED,
        }

        if project_id:
            metrics["runs_in_project"] = _PROJECT_QUALITY_RUNS.get(project_id, 0)

        return metrics


def get_all_advanced_metrics(project_id: str | None = None) -> dict[str, Any]:
    """Get all metrics, optionally scoped to project."""
    return {
        "agent": get_agent_metrics(project_id),
        "rag": get_rag_metrics(),
        "tool": get_tool_metrics(),
        "application": get_application_metrics(project_id),
        "quality_evaluation": get_quality_evaluation_metrics(project_id),
    }
