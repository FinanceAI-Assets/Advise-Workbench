"""
Agent & RAG Metrics Tracking Module

Provides tracker classes that delegate to advanced_metrics.py for centralized metric recording.

Usage:
    from src.core.observability.agent_rag_metrics import AgentMetricsTracker

    agent_tracker = AgentMetricsTracker(agent_name="content_enrichment")
    with agent_tracker.track_call():
        result = agent.execute()
    agent_tracker.track_task_completion(success=True)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

from src.core.observability.advanced_metrics import record_agent_call, record_rag_retrieval

_LOG = logging.getLogger(__name__)


class AgentMetricsTracker:
    """Track metrics for agent execution via advanced_metrics."""

    def __init__(self, agent_name: str):
        """Initialize agent metrics tracker.

        Args:
            agent_name: Name of the agent (e.g., "content_enrichment", "supervisor")
        """
        self.agent_name = agent_name
        self._start_time: float | None = None

    @contextmanager
    def track_call(self):
        """Context manager to track a single agent call via advanced_metrics."""
        self._start_time = time.time()

        try:
            yield
            # Success - record via advanced_metrics
            if self._start_time:
                duration_ms = (time.time() - self._start_time) * 1000
                record_agent_call(
                    agent_name=self.agent_name,
                    duration_ms=duration_ms,
                    success=True,
                    is_retry=False
                )
        except Exception as e:
            # Failed call - still record via advanced_metrics
            if self._start_time:
                duration_ms = (time.time() - self._start_time) * 1000
                record_agent_call(
                    agent_name=self.agent_name,
                    duration_ms=duration_ms,
                    success=False,
                    is_retry=False
                )
            _LOG.error(f"[AGENT_METRICS] {self.agent_name} call failed: {e}")
            raise

    def track_task_completion(self, success: bool) -> None:
        """Track task completion (via advanced_metrics record_agent_call)."""
        if self._start_time:
            duration_ms = (time.time() - self._start_time) * 1000
            record_agent_call(
                agent_name=self.agent_name,
                duration_ms=duration_ms,
                success=success,
                is_retry=False
            )


class RAGMetricsTracker:
    """Track metrics for RAG retrieval operations via advanced_metrics."""

    def __init__(self):
        """Initialize RAG metrics tracker."""
        pass

    def record_retrieval(
        self,
        relevant_chunks: int,
        total_chunks: int,
        supported_facts: int,
        total_facts: int,
        utilized_chunks: int,
        retrieval_latency_ms: float,
    ) -> None:
        """Record a RAG retrieval operation via advanced_metrics."""
        record_rag_retrieval(
            relevant_chunks=relevant_chunks,
            total_chunks=total_chunks,
            supported_facts=supported_facts,
            total_facts=total_facts,
            utilized_chunks=utilized_chunks,
            retrieval_latency_ms=retrieval_latency_ms
        )
