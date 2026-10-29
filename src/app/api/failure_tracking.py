"""
Failure tracking REST endpoints: Monitor and analyze document processing failures.

Provides dashboards and APIs for failure monitoring across all pipeline stages.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.core.db.session import get_db
from src.core.db.models import DocumentFile, DocumentJob, InAppNotification, TaskFailure
from src.core.auth import get_current_user, require_project_role, User
from src.core.tz import ist_now
from src.core.error_handling.error_handler import ErrorHandlerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/failure-tracking", tags=["failure-tracking"])


@router.get("/project/{project_id}/summary")
def get_project_failure_summary(
    project_id: str,
    hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get failure summary for a project.

    Args:
        project_id: Project ID
        hours: Look back N hours (1-720)
        current_user: Current user
        db: Database session

    Returns:
        Failure summary with aggregated statistics
    """
    require_project_role(project_id, {"Owner", "Editor", "Viewer"}, current_user, db)
    logger.info(f"[FAILURES] Getting summary: project={project_id}, hours={hours}")

    try:
        summary = ErrorHandlerService.get_failure_summary(
            db=db,
            project_id=project_id,
            hours=hours,
        )

        return {
            "project_id": project_id,
            "lookback_hours": hours,
            **summary,
        }

    except Exception as e:
        logger.error(f"[FAILURES] Failed to get summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get failure summary")


@router.get("/project/{project_id}/recent-failures")
def get_recent_failures(
    project_id: str,
    limit: int = Query(50, ge=1, le=500),
    task_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get recent failures for a project.

    Args:
        project_id: Project ID
        limit: Number of records to return
        task_name: Optional task filter
        current_user: Current user
        db: Database session

    Returns:
        List of recent failures
    """
    require_project_role(project_id, {"Owner", "Editor", "Viewer"}, current_user, db)
    logger.info(f"[FAILURES] Getting recent failures: project={project_id}, limit={limit}")

    try:
        query = db.query(TaskFailure).filter(TaskFailure.project_id == project_id)

        if task_name:
            query = query.filter(TaskFailure.task_name == task_name)

        failures = (
            query.order_by(TaskFailure.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": f.id,
                "task_name": f.task_name,
                "document_file_id": f.document_file_id,
                "error_type": f.error_type,
                "error_message": f.error_message,
                "retry_count": f.retry_count,
                "max_retries": f.max_retries,
                "is_final_failure": f.is_final_failure,
                "created_at": f.created_at.isoformat(),
            }
            for f in failures
        ]

    except Exception as e:
        logger.error(f"[FAILURES] Failed to get recent failures: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get recent failures")


@router.get("/document/{document_file_id}/failures")
def get_document_failures(
    document_file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get all failures for a specific document.

    Args:
        document_file_id: Document ID
        current_user: Current user
        db: Database session

    Returns:
        Document failure history
    """
    logger.info(f"[FAILURES] Getting document failures: doc={document_file_id}")

    doc_file = db.query(DocumentFile).filter(DocumentFile.id == document_file_id).first()
    if doc_file is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_project_role(doc_file.project_id, {"Owner", "Editor", "Viewer"}, current_user, db)

    try:
        failures = (
            db.query(TaskFailure)
            .filter(TaskFailure.document_file_id == document_file_id)
            .order_by(TaskFailure.created_at.desc())
            .all()
        )

        job = (
            db.query(DocumentJob)
            .filter(DocumentJob.job_id == doc_file.job_id)
            .first()
        )

        failure_timeline = [
            {
                "task": f.task_name,
                "error_type": f.error_type,
                "error_message": f.error_message,
                "attempt": f.retry_count,
                "max_attempts": f.max_retries,
                "timestamp": f.created_at.isoformat(),
            }
            for f in failures
        ]

        return {
            "document_file_id": document_file_id,
            "failure_count": len(failures),
            "final_failures": sum(1 for f in failures if f.is_final_failure),
            "job_status": job.status if job else "unknown",
            "job_error_message": job.error_message if job else None,
            "failure_timeline": failure_timeline,
        }

    except Exception as e:
        logger.error(f"[FAILURES] Failed to get document failures: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get document failures")


@router.get("/error-types-breakdown")
def get_error_types_breakdown(
    project_id: str,
    hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get breakdown of failure types by error category.

    Args:
        project_id: Project ID
        hours: Look back N hours
        current_user: Current user
        db: Database session

    Returns:
        Breakdown of error types
    """
    require_project_role(project_id, {"Owner", "Editor", "Viewer"}, current_user, db)
    logger.info(f"[FAILURES] Getting error type breakdown: project={project_id}")

    try:
        cutoff_time = ist_now() - timedelta(hours=hours)

        failures = (
            db.query(TaskFailure)
            .filter(
                TaskFailure.project_id == project_id,
                TaskFailure.created_at >= cutoff_time,
            )
            .all()
        )

        breakdown: Dict[str, Dict[str, Any]] = {}

        for failure in failures:
            error_type = failure.error_type
            if error_type not in breakdown:
                breakdown[error_type] = {
                    "count": 0,
                    "tasks": {},
                    "final_failures": 0,
                    "total_retries": 0,
                }

            breakdown[error_type]["count"] += 1
            breakdown[error_type]["total_retries"] += failure.retry_count

            if failure.task_name not in breakdown[error_type]["tasks"]:
                breakdown[error_type]["tasks"][failure.task_name] = 0
            breakdown[error_type]["tasks"][failure.task_name] += 1

            if failure.is_final_failure:
                breakdown[error_type]["final_failures"] += 1

        return {
            "project_id": project_id,
            "lookback_hours": hours,
            "error_types": breakdown,
        }

    except Exception as e:
        logger.error(f"[FAILURES] Failed to get error breakdown: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get error breakdown")


@router.get("/tasks-by-reliability")
def get_tasks_by_reliability(
    project_id: str,
    hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get tasks ranked by reliability (failure rate).

    Args:
        project_id: Project ID
        hours: Look back N hours
        current_user: Current user
        db: Database session

    Returns:
        Tasks ranked by failure rate
    """
    require_project_role(project_id, {"Owner", "Editor", "Viewer"}, current_user, db)
    logger.info(f"[FAILURES] Getting task reliability: project={project_id}")

    try:
        cutoff_time = ist_now() - timedelta(hours=hours)

        failures = (
            db.query(TaskFailure)
            .filter(
                TaskFailure.project_id == project_id,
                TaskFailure.created_at >= cutoff_time,
            )
            .all()
        )

        task_stats: Dict[str, Dict[str, Any]] = {}

        for failure in failures:
            task = failure.task_name
            if task not in task_stats:
                task_stats[task] = {
                    "total_failures": 0,
                    "final_failures": 0,
                    "error_types": {},
                }

            task_stats[task]["total_failures"] += 1
            if failure.is_final_failure:
                task_stats[task]["final_failures"] += 1

            error_type = failure.error_type
            if error_type not in task_stats[task]["error_types"]:
                task_stats[task]["error_types"][error_type] = 0
            task_stats[task]["error_types"][error_type] += 1

        # Sort by final failure count
        sorted_tasks = sorted(
            task_stats.items(),
            key=lambda x: x[1]["final_failures"],
            reverse=True,
        )

        return {
            "project_id": project_id,
            "lookback_hours": hours,
            "tasks_by_failure_severity": [
                {
                    "task_name": task,
                    "total_failures": stats["total_failures"],
                    "final_failures": stats["final_failures"],
                    "error_types": stats["error_types"],
                }
                for task, stats in sorted_tasks
            ],
        }

    except Exception as e:
        logger.error(f"[FAILURES] Failed to get task reliability: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get task reliability")


@router.get("/user/{user_id}/notifications")
def get_user_notifications(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get notifications for a user.

    Args:
        user_id: User ID
        limit: Number to return
        unread_only: Only return unread notifications
        current_user: Current user
        db: Database session

    Returns:
        List of notifications
    """
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only read your own notifications")
    logger.info(f"[FAILURES] Getting notifications: user={user_id}")

    try:
        query = db.query(InAppNotification).filter(InAppNotification.user_id == user_id)

        if unread_only:
            query = query.filter(InAppNotification.is_read == False)

        notifications = (
            query.order_by(InAppNotification.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": n.id,
                "notification_type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "document_file_id": n.document_file_id,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ]

    except Exception as e:
        logger.error(f"[FAILURES] Failed to get notifications: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get notifications")


@router.post("/notifications/{notification_id}/mark-read")
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Mark a notification as read.

    Args:
        notification_id: Notification ID
        current_user: Current user
        db: Database session

    Returns:
        Updated notification
    """
    logger.info(f"[FAILURES] Marking notification read: {notification_id}")

    try:
        notification = (
            db.query(InAppNotification)
            .filter(InAppNotification.id == notification_id, InAppNotification.user_id == current_user.id)
            .first()
        )

        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        notification.is_read = True
        notification.read_at = ist_now()
        db.commit()

        return {
            "id": notification.id,
            "is_read": notification.is_read,
            "read_at": notification.read_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FAILURES] Failed to mark notification: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to mark notification")
