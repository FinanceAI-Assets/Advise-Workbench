"""
Content Quality Evaluation System

Automatically evaluates LLM-generated content quality using Claude as a judge.
Metrics: Completeness, Clarity & Readability, Faithfulness & Usefulness, Content Accuracy.

Runs on engagement/run completion and stores results in JSON.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.config import settings
from src.core.storage import workspace_path
from src.llm.claude import claude_generate_json
from .content_extractor import ContentExtractor

logger = logging.getLogger(__name__)


class QualityMetric:
    """Definition of a single quality metric."""

    def __init__(self, name: str, definition: str, scale_min: int = 1, scale_max: int = 5):
        self.name = name
        self.definition = definition
        self.scale_min = scale_min
        self.scale_max = scale_max

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "definition": self.definition,
            "scale": f"{self.scale_min}-{self.scale_max}",
            "scale_description": f"1=Not Good, {self.scale_max}=Excellent"
        }


class ContentQualityEvaluator:
    """
    Evaluates content quality using Claude as a judge.
    Scores: 1-5 scale for each metric.
    """

    # Define all quality metrics
    METRICS = [
        QualityMetric(
            name="Completeness",
            definition="Did the response answer all required aspects of the user query?"
        ),
        QualityMetric(
            name="Clarity & Readability",
            definition="How easy is the output to read and understand? Checks: Grammar, Spelling, Readability"
        ),
        QualityMetric(
            name="Faithfulness & Usefulness",
            definition="Everything generated must be supported by supplied context and help user accomplish goal?"
        ),
        QualityMetric(
            name="Content Accuracy",
            definition="Are the generated facts or content or artifacts correct?"
        ),
    ]

    def __init__(self, model: Optional[str] = None):
        """Initialize evaluator using Sheldon's LLM (claude_generate_json)."""
        self.model = model or "claude-opus-5-5"
        self.extractor = ContentExtractor()
        logger.info(f"Quality evaluator initialized (using Sheldon's LLM)")

    def _build_evaluation_prompt(self, content: str, context: str = "") -> str:
        """Build structured prompt for Claude to evaluate content."""

        metrics_yaml = "\n".join([
            f"  - {m.name}: {m.definition}"
            for m in self.METRICS
        ])

        prompt = f"""You are an expert content quality evaluator. Analyze the following content and score it on each metric.

CONTENT TO EVALUATE:
---
{content[:5000]}  # Truncate for token efficiency
---

{"CONTEXT/REQUIREMENTS:" + context if context else ""}

EVALUATION METRICS (Score 1-5, where 1=Not Good, 5=Excellent):
{metrics_yaml}

Provide your evaluation in strict JSON format (no markdown, no extra text):
{{
  "completeness": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
  "clarity_readability": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
  "faithfulness_usefulness": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
  "content_accuracy": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
  "overall_assessment": "<1-2 sentence summary>"
}}

Be strict but fair. Return ONLY valid JSON."""

        return prompt

    def _evaluate_sync(
        self,
        content: str,
        context: str = "",
        artifact_type: str = "text"
    ) -> Dict[str, Any]:
        """
        Evaluate content quality using Claude (same as Sheldon).

        Args:
            content: The content to evaluate
            context: Optional context/requirements for evaluation
            artifact_type: Type of artifact (docx, pptx, etc.)

        Returns:
            Dictionary with metric scores and metadata
        """
        try:
            # Build the evaluation prompt
            metrics_yaml = "\n".join([
                f"  - {m.name}: {m.definition}"
                for m in self.METRICS
            ])

            system = "You are an expert content quality evaluator. Analyze the content and score it on each metric. Return ONLY valid JSON, no markdown, no extra text."

            user = f"""CONTENT TO EVALUATE:
---
{content[:5000]}
---

{f"CONTEXT: {context}" if context else ""}

EVALUATION METRICS (Score 1-5, where 1=Not Good, 5=Excellent):
{metrics_yaml}

Return JSON format:
{{
  "completeness": {{"score": <1-5>, "reasoning": "<brief>"}},
  "clarity_readability": {{"score": <1-5>, "reasoning": "<brief>"}},
  "faithfulness_usefulness": {{"score": <1-5>, "reasoning": "<brief>"}},
  "content_accuracy": {{"score": <1-5>, "reasoning": "<brief>"}},
  "overall_assessment": "<1-2 sentence summary>"
}}"""

            # Use Sheldon's LLM (claude_generate_json)
            try:
                scores = claude_generate_json(system=system, user=user, temperature=0.3, max_tokens=500)
            except Exception as e:
                logger.error(f"LLM evaluation failed: {e}")
                scores = {
                    "completeness": {"score": 3, "reasoning": "LLM error"},
                    "clarity_readability": {"score": 3, "reasoning": "LLM error"},
                    "faithfulness_usefulness": {"score": 3, "reasoning": "LLM error"},
                    "content_accuracy": {"score": 3, "reasoning": "LLM error"},
                    "overall_assessment": "Evaluation failed"
                }

            # Validate scores are in range
            for key in ["completeness", "clarity_readability", "faithfulness_usefulness", "content_accuracy"]:
                if key in scores:
                    score = scores[key].get("score", 3)
                    if not (1 <= score <= 5):
                        scores[key]["score"] = max(1, min(5, score))

            return {
                "artifact_type": artifact_type,
                "timestamp": datetime.utcnow().isoformat(),
                "content_length": len(content),
                "scores": scores
            }

        except Exception as e:
            logger.error(f"Error evaluating content: {e}", exc_info=True)
            return {
                "error": str(e),
                "artifact_type": artifact_type,
                "timestamp": datetime.utcnow().isoformat()
            }


    def evaluate_artifacts(
        self,
        artifact_paths: list[Path],
        project_context: str = ""
    ) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate multiple artifacts and aggregate scores.

        Args:
            artifact_paths: List of artifact file paths
            project_context: Context about the project/requirements

        Returns:
            Dictionary mapping artifact name to scores
        """
        results = {}

        for artifact_path in artifact_paths:
            if not artifact_path.exists():
                logger.warning(f"Artifact not found: {artifact_path}")
                continue

            try:
                # Extract content based on file type
                content = self.extractor.extract_content(artifact_path)

                if not content:
                    logger.warning(f"No content extracted from {artifact_path}")
                    continue

                # Determine artifact type
                artifact_type = artifact_path.suffix.lstrip(".")

                # Evaluate (using Sheldon's LLM)
                # Note: evaluate_async uses claude_generate_json which is synchronous
                scores = self._evaluate_sync(content, project_context, artifact_type)
                results[artifact_path.name] = scores

                logger.info(f"Evaluated {artifact_path.name}: {scores.get('scores', {})}")

            except Exception as e:
                logger.error(f"Error processing artifact {artifact_path}: {e}", exc_info=True)
                results[artifact_path.name] = {"error": str(e)}

        return results

    def calculate_overall_score(self, evaluation_results: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate weighted overall quality score from evaluation results.

        Args:
            evaluation_results: Dictionary of artifact evaluations

        Returns:
            Dictionary with individual and overall scores
        """
        all_scores = []
        metric_totals = {
            "completeness": [],
            "clarity_readability": [],
            "faithfulness_usefulness": [],
            "content_accuracy": []
        }

        for artifact_name, result in evaluation_results.items():
            if "error" in result:
                continue

            scores = result.get("scores", {})
            for metric_key, metric_data in scores.items():
                if metric_key != "overall_assessment" and isinstance(metric_data, dict):
                    score = metric_data.get("score")
                    if score:
                        if metric_key in metric_totals:
                            metric_totals[metric_key].append(score)
                        all_scores.append(score)

        # Calculate averages
        summary = {
            "completeness_avg": (
                sum(metric_totals["completeness"]) / len(metric_totals["completeness"])
                if metric_totals["completeness"] else 0
            ),
            "clarity_readability_avg": (
                sum(metric_totals["clarity_readability"]) / len(metric_totals["clarity_readability"])
                if metric_totals["clarity_readability"] else 0
            ),
            "faithfulness_usefulness_avg": (
                sum(metric_totals["faithfulness_usefulness"]) / len(metric_totals["faithfulness_usefulness"])
                if metric_totals["faithfulness_usefulness"] else 0
            ),
            "content_accuracy_avg": (
                sum(metric_totals["content_accuracy"]) / len(metric_totals["content_accuracy"])
                if metric_totals["content_accuracy"] else 0
            ),
            "overall_quality_score": (
                sum(all_scores) / len(all_scores) if all_scores else 0
            ),
            "total_artifacts_evaluated": len(evaluation_results),
            "artifacts_with_errors": sum(1 for r in evaluation_results.values() if "error" in r)
        }

        return summary

    def save_evaluation_report(
        self,
        project_id: str,
        engagement_id: str,
        evaluation_results: Dict[str, Any],
        summary: Dict[str, float],
        user_instructions: str = ""
    ) -> Path:
        """
        Save evaluation report to JSON file.

        File structure:
        workspace/{project_id}/{engagement_id}_quality_metrics.json

        Args:
            project_id: Project ID
            engagement_id: Engagement/Run ID
            evaluation_results: Raw evaluation results
            summary: Aggregated summary scores
            user_instructions: Original user instructions/context

        Returns:
            Path to saved report file
        """
        workspace_root = workspace_path(project_id)
        workspace_root.mkdir(parents=True, exist_ok=True)

        report_path = workspace_root / f"{engagement_id}_quality_metrics.json"

        report = {
            "metadata": {
                "project_id": project_id,
                "engagement_id": engagement_id,
                "evaluation_timestamp": datetime.utcnow().isoformat(),
                "evaluator_version": "1.0",
                "model_used": self.model
            },
            "user_context": {
                "instructions": user_instructions
            },
            "metrics_definitions": [m.to_dict() for m in self.METRICS],
            "individual_artifact_scores": evaluation_results,
            "summary": summary,
            "quality_grade": self._calculate_grade(summary["overall_quality_score"])
        }

        # Write JSON report
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Quality evaluation report saved: {report_path}")
        return report_path

    @staticmethod
    def _calculate_grade(score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 4.5:
            return "A"
        elif score >= 3.5:
            return "B"
        elif score >= 2.5:
            return "C"
        elif score >= 1.5:
            return "D"
        else:
            return "F"


def evaluate_run_quality(
    project_id: str,
    run_id: str,
    artifact_paths: list[Path],
    user_instructions: str = "",
    project_context: str = ""
) -> Dict[str, Any]:
    """
    Evaluate a complete run's quality using Sheldon's LLM.

    Called from orchestrator hooks on run completion (in background thread).

    Args:
        project_id: Project ID
        run_id: Run/Engagement ID
        artifact_paths: List of artifact files to evaluate
        user_instructions: Original user instructions
        project_context: Project context/requirements

    Returns:
        Dictionary with evaluation results and report path
    """
    evaluator = None
    try:
        evaluator = ContentQualityEvaluator()

        print(f"\n[EVALUATE] Starting evaluation of {len(artifact_paths)} artifacts for {run_id}")
        logger.info(f"Starting quality evaluation for run {run_id} ({len(artifact_paths)} artifacts)")

        # Evaluate all artifacts (now synchronous)
        print(f"[EVALUATE] Extracting content and calling Claude for scoring...")
        results = evaluator.evaluate_artifacts(artifact_paths, project_context)

        # Calculate summary
        print(f"[EVALUATE] Calculating summary scores...")
        summary = evaluator.calculate_overall_score(results)

        # Add quality grade to summary
        quality_grade = evaluator._calculate_grade(summary["overall_quality_score"])
        summary["quality_grade"] = quality_grade

        # Save report
        print(f"[EVALUATE] Saving report to JSON...")
        report_path = evaluator.save_evaluation_report(
            project_id=project_id,
            engagement_id=run_id,
            evaluation_results=results,
            summary=summary,
            user_instructions=user_instructions
        )

        print(f"[EVALUATE] COMPLETE - Grade: {quality_grade}, Score: {summary['overall_quality_score']:.2f}")
        print(f"[EVALUATE] Report saved to: {report_path}\n")
        logger.info(f"Quality evaluation complete. Grade: {quality_grade}, Score: {summary['overall_quality_score']:.2f}")

        return {
            "success": True,
            "run_id": run_id,
            "report_path": str(report_path),
            "quality_grade": summary["quality_grade"],
            "overall_score": summary["overall_quality_score"],
            "summary": summary
        }

    except Exception as e:
        print(f"[EVALUATE] ERROR: {e}\n")
        logger.error(f"Error in evaluate_run_quality: {e}", exc_info=True)
        return {
            "success": False,
            "run_id": run_id,
            "error": str(e)
        }


# Example usage
if __name__ == "__main__":
    # Test content
    test_content = """
    Standard Operating Procedure: Customer Onboarding

    1. Initial Contact
    - Receive customer inquiry
    - Send welcome email with timeline
    - Schedule kickoff call

    2. Requirements Gathering
    - Document business needs
    - Create project scope
    - Define success metrics

    3. Setup Phase
    - Provision system access
    - Configure integrations
    - Create user accounts

    4. Training
    - Conduct system walkthroughs
    - Provide documentation
    - Schedule Q&A sessions
    """

    evaluator = ContentQualityEvaluator()
    result = evaluator.evaluate(
        content=test_content,
        context="Customer onboarding process for SaaS platform",
        artifact_type="sop"
    )

    print("Evaluation Result:")
    print(json.dumps(result, indent=2))
