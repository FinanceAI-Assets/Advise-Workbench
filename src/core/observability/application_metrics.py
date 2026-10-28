"""
Application Metrics Tracking Module

Provides tracker class that delegates to advanced_metrics.py for centralized metric recording.

Usage:
    from src.core.observability.application_metrics import ApplicationMetricsTracker

    tracker = ApplicationMetricsTracker()
    tracker.record_request_started()
    tracker.record_request_completed(success=True, duration_ms=1234)
    tracker.record_cost(0.50)
"""

from __future__ import annotations

import logging
from src.core.observability.advanced_metrics import record_application_request

_LOG = logging.getLogger(__name__)


class ApplicationMetricsTracker:
    """Track application-level metrics via advanced_metrics."""

    def __init__(self):
        """Initialize application metrics tracker."""
        pass

    def record_request_started(self, request_id: str | None = None) -> None:
        """Record that a request has started."""
        _LOG.debug(f"[APP_METRICS] Request started: {request_id}")

    def record_request_completed(
        self, success: bool, duration_ms: float, request_id: str | None = None, cost: float = 0.0
    ) -> None:
        """Record that a request has completed via advanced_metrics."""
        record_application_request(
            duration_ms=duration_ms,
            success=success,
            cost=cost
        )

    def record_cost(self, cost_usd: float) -> None:
        """Record cost incurred by operation."""
        record_application_request(
            duration_ms=0,
            success=True,
            cost=cost_usd
        )


# Global singleton for application metrics
_APP_METRICS: ApplicationMetricsTracker | None = None


def get_application_metrics() -> ApplicationMetricsTracker:
    """Get or create global application metrics tracker."""
    global _APP_METRICS
    if _APP_METRICS is None:
        _APP_METRICS = ApplicationMetricsTracker()
    return _APP_METRICS
