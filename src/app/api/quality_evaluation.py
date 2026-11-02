"""
Quality Evaluation API Routes

Endpoints for retrieving and triggering content quality evaluations.

Routes:
- GET /api/projects/{project_id}/runs/{run_id}/quality-metrics
- POST /api/projects/{project_id}/runs/{run_id}/evaluate-quality
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.auth import get_current_user
from src.core.db.models import User, Project
from src.core.db.session import SessionLocal
from src.core.storage import workspace_path
from src.evaluation import trigger_quality_evaluation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["quality-evaluation"])


class EvaluateQualityRequest(BaseModel):
    force: bool = False


class QualityMetricsResponse(BaseModel):
    success: bool
    overall_score: float
    quality_grade: str
    report: dict


@router.get("/{project_id}/runs/{run_id}/quality-metrics")
async def get_quality_metrics(
    project_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user)
) -> QualityMetricsResponse:
    """
    Retrieve quality evaluation metrics for a completed run.

    Returns: Full quality metrics report if available.
    """
    try:
        db = SessionLocal()

        # Check authorization
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if not _has_project_access(current_user, project):
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if metrics file exists
        metrics_path = workspace_path(project_id) / f"{run_id}_quality_metrics.json"

        if not metrics_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Quality metrics not found. Run may not be complete or evaluation not yet done."
            )

        # Load and return metrics
        with open(metrics_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        summary = report.get("summary", {})

        return QualityMetricsResponse(
            success=True,
            overall_score=summary.get("overall_quality_score", 0),
            quality_grade=report.get("quality_grade", "N/A"),
            report=report
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving quality metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/runs/{run_id}/evaluate-quality")
async def trigger_quality_evaluation_endpoint(
    project_id: str,
    run_id: str,
    request: EvaluateQualityRequest,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Manually trigger quality evaluation for a run.

    Parameters:
    - force: If true, re-evaluate even if metrics already exist

    Returns: Evaluation result or status
    """
    try:
        db = SessionLocal()

        # Check authorization
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if not _has_project_access(current_user, project):
            raise HTTPException(status_code=403, detail="Access denied")

        # Trigger evaluation
        result = await trigger_quality_evaluation(
            project_id=project_id,
            run_id=run_id,
            force=request.force
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Evaluation failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering quality evaluation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _has_project_access(user: User, project: Project) -> bool:
    """Check if user has access to project."""
    # This is a simplified check - adjust based on your RBAC model
    # Typically: check if user is project owner or has membership
    if hasattr(project, "user_id"):
        return project.user_id == user.id
    if hasattr(project, "members"):
        return any(m.user_id == user.id for m in project.members)
    return False
