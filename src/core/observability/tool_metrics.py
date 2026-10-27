"""
Tool Metrics Tracking Module

Provides tracker class that delegates to advanced_metrics.py for centralized metric recording.

Usage:
    from src.core.observability.tool_metrics import ToolMetricsTracker

    tracker = ToolMetricsTracker(tool_name="document_parser")
    with tracker.track_tool_call():
        result = tool.execute(data)
    tracker.track_success(success=True, necessary=True)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from src.core.observability.advanced_metrics import record_tool_call

_LOG = logging.getLogger(__name__)


class ToolMetricsTracker:
    """Track metrics for tool execution via advanced_metrics."""

    def __init__(self, tool_name: str):
        """Initialize tool metrics tracker.

        Args:
            tool_name: Name of the tool (e.g., "document_parser", "code_executor")
        """
        self.tool_name = tool_name
        self._start_time: float | None = None

    @contextmanager
    def track_tool_call(self):
        """Context manager to track a single tool call."""
        self._start_time = time.time()

        try:
            yield
        except Exception:
            raise
        finally:
            if self._start_time:
                duration_ms = (time.time() - self._start_time) * 1000
                _LOG.debug(f"[TOOL_METRICS] {self.tool_name} call completed in {duration_ms:.1f}ms")

    def track_success(self, success: bool, necessary: bool = True):
        """Track tool success and necessity via advanced_metrics."""
        duration_ms = (time.time() - self._start_time) * 1000 if self._start_time else 0
        record_tool_call(
            duration_ms=duration_ms,
            success=success,
            necessary=necessary
        )
