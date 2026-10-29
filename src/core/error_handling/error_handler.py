"""
Error handling service for Stage 1.3: Complete failure recovery and tracking.

Manages error tracking, DocumentJob updates, and failure notifications.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from src.core.tz import ist_now

logger = logging.getLogger(__name__)


class ErrorHandlerService:
    """Service for centralized error handling across all ingestion tasks."""

    @staticmethod
    def record_task_failure(
        db: Session,
        task_name: str,
        document_file_id: str,
        project_id: str,
        error_message: str,
        error_type: str = "unknown",
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Record task failure in database.

        Args:
            db: Database session
            task_name: Name of failed task (extract_facts, generate_wiki, etc.)
            document_file_id: Document being processed
            project_id: Project context
            error_message: Error message (truncated to 500 chars)
            error_type: Type of error (api_error, db_error, timeout, etc.)
            retry_count: Current retry attempt
            max_retries: Maximum retry attempts for this task

        Returns:
            Dictionary with failure tracking info
        """
        from src.core.db.models import TaskFailure

        logger.warning(
            f"[ERROR_HANDLER] Recording failure: task={task_name}, doc={document_file_id}, "
            f"retry={retry_count}/{max_retries}"
        )

        try:
            # Create failure record
            failure = TaskFailure(
                id=f"failure_{document_file_id[:15]}_{task_name}_{retry_count}",
                task_name=task_name,
                document_file_id=document_file_id,
                project_id=project_id,
                error_message=error_message[:500],  # Truncate to 500 chars
                error_type=error_type,
                retry_count=retry_count,
                max_retries=max_retries,
                is_final_failure=retry_count >= max_retries,
                created_at=datetime.utcnow(),
            )

            db.add(failure)
            db.commit()

            logger.info(f"[ERROR_HANDLER] Failure recorded: {failure.id}")

            return {
                "failure_id": failure.id,
                "is_final": retry_count >= max_retries,
                "retry_count": retry_count,
                "max_retries": max_retries,
            }

        except Exception as e:
            logger.error(f"[ERROR_HANDLER] Failed to record failure: {str(e)}")
            raise

    @staticmethod
    def update_document_job_failed(
        db: Session,
        document_file_id: str,
        error_message: str,
        failed_stage: str = "unknown",
    ) -> bool:
        """
        Mark DocumentJob as failed with error details.

        Args:
            db: Database session
            document_file_id: Document to mark as failed
            error_message: Error message
            failed_stage: Stage where failure occurred (1.1, 1.2, 1.3, etc.)

        Returns:
            True if updated successfully
        """
        from src.core.db.models import DocumentJob, DocumentFile

        logger.warning(
            f"[ERROR_HANDLER] Marking DocumentJob as failed: doc={document_file_id}, "
            f"stage={failed_stage}"
        )

        try:
            # Get document file to find job ID
            document_file = db.query(DocumentFile).filter(
                DocumentFile.id == document_file_id
            ).first()

            if not document_file:
                logger.error(f"[ERROR_HANDLER] DocumentFile not found: {document_file_id}")
                return False

            # Update job
            job = db.query(DocumentJob).filter(
                DocumentJob.job_id == document_file.job_id
            ).first()

            if job:
                job.status = "failed"
                job.error_message = error_message[:500]
                job.failed_stage = failed_stage
                job.updated_at = datetime.utcnow()

                db.commit()
                logger.info(f"[ERROR_HANDLER] Job marked as failed: {job.job_id}")
                return True
            else:
                logger.error(f"[ERROR_HANDLER] DocumentJob not found for file: {document_file_id}")
                return False

        except Exception as e:
            logger.error(f"[ERROR_HANDLER] Failed to update DocumentJob: {str(e)}")
            return False

    @staticmethod
    def should_retry_task(
        error_type: str,
        retry_count: int,
        max_retries: int,
    ) -> bool:
        """
        Determine if task should be retried based on error type.

        Args:
            error_type: Type of error
            retry_count: Current retry attempt
            max_retries: Maximum retries allowed

        Returns:
            True if should retry
        """
        # Don't retry if max attempts reached
        if retry_count >= max_retries:
            logger.info(f"[ERROR_HANDLER] Max retries reached ({max_retries})")
            return False

        # Always retry transient errors
        transient_errors = [
            "timeout",
            "connection_error",
            "api_timeout",
            "rate_limit",
            "temporary_failure",
        ]

        if error_type in transient_errors:
            logger.info(f"[ERROR_HANDLER] Retrying transient error: {error_type}")
            return True

        # Retry LLM API errors (may be temporary)
        if "api_error" in error_type or "llm_error" in error_type:
            if retry_count < max_retries:
                logger.info(f"[ERROR_HANDLER] Retrying LLM API error: {error_type}")
                return True

        # Don't retry validation errors
        if "validation" in error_type or "format" in error_type:
            logger.info(f"[ERROR_HANDLER] Not retrying validation error: {error_type}")
            return False

        # Default: retry if attempts remaining
        if retry_count < max_retries:
            logger.info(f"[ERROR_HANDLER] Retrying unknown error: {error_type}")
            return True

        return False

    @staticmethod
    def get_failure_summary(
        db: Session,
        project_id: str,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get failure summary for a project.

        Args:
            db: Database session
            project_id: Project to summarize
            hours: Look back N hours

        Returns:
            Dictionary with failure statistics
        """
        from src.core.db.models import TaskFailure
        from datetime import timedelta

        try:
            cutoff_time = ist_now() - timedelta(hours=hours)

            failures = db.query(TaskFailure).filter(
                TaskFailure.project_id == project_id,
                TaskFailure.created_at >= cutoff_time,
            ).all()

            # Group by task and error type
            by_task = {}
            by_error_type = {}
            final_failures = 0

            for failure in failures:
                # By task
                if failure.task_name not in by_task:
                    by_task[failure.task_name] = 0
                by_task[failure.task_name] += 1

                # By error type
                if failure.error_type not in by_error_type:
                    by_error_type[failure.error_type] = 0
                by_error_type[failure.error_type] += 1

                # Count final failures
                if failure.is_final_failure:
                    final_failures += 1

            summary = {
                "total_failures": len(failures),
                "final_failures": final_failures,
                "by_task": by_task,
                "by_error_type": by_error_type,
                "hours_lookback": hours,
                "summary_time": datetime.utcnow().isoformat(),
            }

            logger.info(f"[ERROR_HANDLER] Failure summary: {len(failures)} failures, "
                       f"{final_failures} final")

            return summary

        except Exception as e:
            logger.error(f"[ERROR_HANDLER] Failed to get summary: {str(e)}")
            return {}


def get_error_handler_service() -> ErrorHandlerService:
    """Get error handler service instance."""
    return ErrorHandlerService()
