"""
Quality Evaluation Hook Integration

Automatically evaluates content quality when a run completes.
Integrates with src/workflows/orchestrator.py via hooks system.

Hook triggers:
- on_run_done: Evaluates all generated artifacts
- Stores results in workspace/{project_id}/{run_id}_quality_metrics.json

Configuration:
- QUALITY_EVALUATION_ENABLED=true (enable/disable)
- QUALITY_EVALUATION_ASYNC=true (run async, don't block)
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from src.core.db.models import Run
from src.core.db.session import SessionLocal
from src.core.storage import workspace_path
from src.core.observability.advanced_metrics import record_quality_evaluation
from .content_quality_evaluator import evaluate_run_quality

logger = logging.getLogger(__name__)

def safe_print(msg: str) -> None:
    """Print safely, avoiding unicode encoding errors."""
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            sys.stdout.buffer.write(msg.encode('utf-8', errors='replace') + b'\n')
        except Exception:
            print(msg.encode('ascii', errors='replace').decode('ascii'))


class QualityEvaluationHook:
    """Hook to evaluate content quality on run completion."""

    def __init__(self, enabled: bool = True, async_mode: bool = True):
        """
        Initialize hook.

        Args:
            enabled: Whether to enable quality evaluation
            async_mode: If True, run evaluation async (don't block orchestrator)
        """
        self.enabled = enabled
        self.async_mode = async_mode

    def on_run_done(self, run_id: str, project_id: str) -> Optional[dict]:
        """
        Called when a run completes successfully.

        Args:
            run_id: Run ID
            project_id: Project ID

        Returns:
            Evaluation result or None
        """
        if not self.enabled:
            return None

        try:
            # Get run from database
            db = SessionLocal()
            run = db.query(Run).filter(
                Run.id == run_id,
                Run.project_id == project_id
            ).first()

            if not run:
                logger.warning(f"Run not found: {run_id}")
                return None

            # Get all artifact files from workspace run directory
            run_dir = workspace_path(project_id) / "runs" / run_id
            if not run_dir.exists():
                logger.info(f"Run directory not found: {run_dir}")
                return None

            # Find artifact files - ONLY DOCX, PPTX, PDF (not internal metadata files)
            # OLD: artifact_paths = [
            #     f for f in run_dir.rglob("*")
            #     if f.is_file() and f.suffix.lower() in [".docx", ".pptx", ".xlsx", ".pdf", ".json", ".txt", ".md"]
            # ]
            artifact_paths = [
                f for f in run_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in [".docx", ".pptx", ".pdf", ".xlsx"]
            ]

            if not artifact_paths:
                logger.info(f"No artifacts found in run directory: {run_dir}")
                return None

            # Get user instructions (if available from conversation/events)
            user_instructions = self._get_user_instructions(run)

            # Get project context (if available)
            project_context = self._get_project_context(project_id, db)

            if self.async_mode:
                # Run evaluation async (don't block)
                asyncio.create_task(
                    evaluate_run_quality(
                        project_id=project_id,
                        run_id=run_id,
                        artifact_paths=artifact_paths,
                        user_instructions=user_instructions,
                        project_context=project_context
                    )
                )
                logger.info(f"Quality evaluation scheduled async for run {run_id}")
                return {"status": "scheduled_async"}
            else:
                # Run evaluation synchronously (blocks until complete)
                result = asyncio.run(
                    evaluate_run_quality(
                        project_id=project_id,
                        run_id=run_id,
                        artifact_paths=artifact_paths,
                        user_instructions=user_instructions,
                        project_context=project_context
                    )
                )
                logger.info(f"Quality evaluation complete for run {run_id}")
                return result

        except Exception as e:
            logger.error(f"Error in quality evaluation hook: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _get_user_instructions(run: Run) -> str:
        """
        Extract user instructions/requirements from run metadata or conversation.

        Args:
            run: Run object

        Returns:
            User instructions text
        """
        try:
            # Try to get from plan payload
            if hasattr(run, "plan_payload") and run.plan_payload:
                import json
                plan = json.loads(run.plan_payload) if isinstance(run.plan_payload, str) else run.plan_payload
                return plan.get("user_query", "") or plan.get("instructions", "")

            # Try conversation events
            if hasattr(run, "events"):
                for event in run.events:
                    if event.event_type == "user_message":
                        return event.payload.get("content", "")

            return ""
        except Exception as e:
            logger.debug(f"Could not extract user instructions: {e}")
            return ""

    @staticmethod
    def _get_project_context(project_id: str, db) -> str:
        """
        Get project context (name, description, requirements, etc.).

        Args:
            project_id: Project ID
            db: Database session

        Returns:
            Project context text
        """
        try:
            from src.core.db.models import Project

            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                context_parts = []
                if hasattr(project, "name"):
                    context_parts.append(f"Project: {project.name}")
                if hasattr(project, "description"):
                    context_parts.append(f"Description: {project.description}")
                return "\n".join(context_parts)

            return ""
        except Exception as e:
            logger.debug(f"Could not extract project context: {e}")
            return ""


def register_quality_evaluation_hook(orchestrator, enabled: bool = True, async_mode: bool = True):
    """
    Register quality evaluation hook with orchestrator.

    Args:
        orchestrator: RunOrchestrator instance
        enabled: Whether to enable hook
        async_mode: Whether to run evaluation async

    Usage in orchestrator:
        from src.evaluation.quality_evaluation_hook import register_quality_evaluation_hook

        # In _execute_run_job() or main setup:
        register_quality_evaluation_hook(self, enabled=True, async_mode=True)
    """
    hook = QualityEvaluationHook(enabled=enabled, async_mode=async_mode)

    # Register with orchestrator's hook system
    if hasattr(orchestrator, "register_hook"):
        orchestrator.register_hook("on_run_done", hook.on_run_done)
        logger.info("Quality evaluation hook registered")
    else:
        logger.warning("Orchestrator does not support hook registration")


# Standalone evaluation trigger (for manual/scheduled use)
def trigger_quality_evaluation(
    project_id: str,
    run_id: str,
    force: bool = False
) -> dict:
    """Trigger quality evaluation for a run using Sheldon's LLM."""
    db = None
    try:
        safe_print(f"[TRIGGER_EVAL] Starting for {project_id}/{run_id}")
        db = SessionLocal()

        # Check if evaluation already exists
        report_path = workspace_path(project_id) / f"{run_id}_quality_metrics.json"
        if report_path.exists() and not force:
            safe_print("[TRIGGER_EVAL] Report already exists, loading from cache")
            logger.info(f"Quality evaluation already exists: {report_path}")
            import json
            with open(report_path) as f:
                return json.load(f)

        # Get all artifact files from workspace run directory
        run_dir = workspace_path(project_id) / "runs" / run_id
        if not run_dir.exists():
            safe_print(f"[TRIGGER_EVAL] Run directory not found (job completed)")
            logger.warning(f"Run directory not found: {run_dir}")
            return {"success": False, "error": "Run directory not found"}

        # Find artifact files - ONLY DOCX, PPTX, PDF (not internal metadata files)
        artifact_paths = [
            f for f in run_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in [".docx", ".pptx", ".pdf", ".xlsx"]
        ]

        if not artifact_paths:
            safe_print(f"[TRIGGER_EVAL] No artifacts found (run_id={run_id})")
            logger.warning(f"No artifacts found for run {run_id}")
            return {"success": False, "error": "No artifacts found"}

        safe_print(f"[TRIGGER_EVAL] Found {len(artifact_paths)} artifacts to evaluate")

        # Get run for context
        run = db.query(Run).filter(Run.id == run_id).first()
        user_instructions = QualityEvaluationHook._get_user_instructions(run) if run else ""
        project_context = QualityEvaluationHook._get_project_context(project_id, db)

        # Close DB connection before evaluation to avoid locks
        db.close()
        db = None

        # Evaluate (now synchronous)
        result = evaluate_run_quality(
            project_id=project_id,
            run_id=run_id,
            artifact_paths=artifact_paths,
            user_instructions=user_instructions,
            project_context=project_context
        )

        # Record quality evaluation metrics for OpenObserve (4 evaluation metrics + grade/score)
        if isinstance(result, dict):
            # Extract from summary if available, otherwise use root level
            summary = result.get("summary", {})
            completeness = (summary.get("completeness_avg", 0) or 0) / 5.0  # Convert 1-5 scale to 0-1
            clarity_readability = (summary.get("clarity_readability_avg", 0) or 0) / 5.0
            faithfulness_usefulness = (summary.get("faithfulness_usefulness_avg", 0) or 0) / 5.0
            content_accuracy = (summary.get("content_accuracy_avg", 0) or 0) / 5.0
            grade = result.get("quality_grade") or summary.get("quality_grade")
            score = summary.get("overall_quality_score", 0)

            record_quality_evaluation(
                completeness=completeness,
                clarity_readability=clarity_readability,
                faithfulness_usefulness=faithfulness_usefulness,
                content_accuracy=content_accuracy,
                grade=grade,
                score=score,
                project_id=project_id,
            )
            try:
                safe_print(f"[QUALITY_EVAL_METRIC] Completeness: {completeness:.2f}, Clarity: {clarity_readability:.2f}, Faithfulness: {faithfulness_usefulness:.2f}, Accuracy: {content_accuracy:.2f}")
            except Exception:
                safe_print("[QUALITY_EVAL_METRIC] Metrics recorded successfully")
            logger.info(f"Recorded quality metrics - Complete: {completeness}, Clarity: {clarity_readability}, Faithfulness: {faithfulness_usefulness}, Accuracy: {content_accuracy}")

        return result

    except Exception as e:
        logger.error(f"Error triggering quality evaluation: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    # Example: Manually evaluate a run
    import asyncio

    result = asyncio.run(trigger_quality_evaluation(
        project_id="test_project",
        run_id="test_run_123"
    ))
    print(result)
