"""
Quality Evaluation Metrics Tracking Module

Provides tracker class that delegates to advanced_metrics.py for centralized metric recording.

Usage:
    from src.core.observability.quality_metrics import QualityMetricsTracker

    tracker = QualityMetricsTracker()
    tracker.record_eval_scores(
        run_id="run_123",
        completeness=4.5,
        clarity=4.2,
        faithfulness=3.8,
        accuracy=4.1
    )
"""

from __future__ import annotations

import logging
from src.core.observability.advanced_metrics import record_quality_evaluation

_LOG = logging.getLogger(__name__)


class QualityMetricsTracker:
    """Track quality evaluation metrics via advanced_metrics."""

    def __init__(self):
        """Initialize quality metrics tracker."""
        pass

    def record_eval_scores(
        self,
        run_id: str,
        completeness: float,
        clarity: float,
        faithfulness: float,
        accuracy: float,
    ) -> None:
        """Record individual quality evaluation scores for a run."""
        # Convert 1-5 scale to 0-1 scale
        completeness_01 = completeness / 5.0
        clarity_01 = clarity / 5.0
        faithfulness_01 = faithfulness / 5.0
        accuracy_01 = accuracy / 5.0

        record_quality_evaluation(
            completeness=completeness_01,
            clarity_readability=clarity_01,
            faithfulness_usefulness=faithfulness_01,
            content_accuracy=accuracy_01
        )

    def calculate_overall_score(
        self,
        completeness: float,
        clarity: float,
        faithfulness: float,
        accuracy: float,
    ) -> float:
        """Calculate overall quality score as average of 4 dimensions."""
        scores = [
            min(5.0, max(1.0, float(completeness))),
            min(5.0, max(1.0, float(clarity))),
            min(5.0, max(1.0, float(faithfulness))),
            min(5.0, max(1.0, float(accuracy))),
        ]
        overall = round(sum(scores) / len(scores), 2)
        return overall

    def record_overall_score(self, overall_score: float) -> None:
        """Record overall quality score (via advanced_metrics)."""
        score_01 = overall_score / 5.0
        record_quality_evaluation(
            completeness=score_01,
            clarity_readability=score_01,
            faithfulness_usefulness=score_01,
            content_accuracy=score_01,
            score=score_01
        )

    def record_eval_complete(
        self,
        run_id: str,
        completeness: float,
        clarity: float,
        faithfulness: float,
        accuracy: float,
    ) -> float:
        """Record all quality scores and return overall score in one call."""
        self.record_eval_scores(
            run_id=run_id,
            completeness=completeness,
            clarity=clarity,
            faithfulness=faithfulness,
            accuracy=accuracy,
        )

        overall = self.calculate_overall_score(
            completeness=completeness,
            clarity=clarity,
            faithfulness=faithfulness,
            accuracy=accuracy,
        )

        self.record_overall_score(overall)
        return overall
