"""Quality checks: QA loop, evaluators, quality framework, format QA, visual QA, evidence."""
"""
Content Quality Evaluation Module

Automatic LLM-based evaluation of generated content.

Usage:
    from src.evaluation import ContentQualityEvaluator, evaluate_run_quality
    
    # Direct evaluation
    evaluator = ContentQualityEvaluator()
    result = evaluator.evaluate("Your content...", artifact_type="sop")
    
    # Run-based evaluation (async)
    result = await evaluate_run_quality(
        project_id="proj_123",
        run_id="run_456",
        artifact_paths=[Path("artifact1.docx"), ...],
        user_instructions="Create an SOP...",
        project_context="Hiring process"
    )
"""

from .content_quality_evaluator import (
    ContentQualityEvaluator,
    QualityMetric,
    evaluate_run_quality
)
from .content_extractor import ContentExtractor
from .quality_evaluation_hook import (
    QualityEvaluationHook,
    register_quality_evaluation_hook,
    trigger_quality_evaluation
)

__all__ = [
    "ContentQualityEvaluator",
    "QualityMetric",
    "evaluate_run_quality",
    "ContentExtractor",
    "QualityEvaluationHook",
    "register_quality_evaluation_hook",
    "trigger_quality_evaluation",
]
