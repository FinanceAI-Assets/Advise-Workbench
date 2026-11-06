"""Phase 5 design review: which artifacts are reviewed, and how a rejection becomes a regeneration request.

The API (src/app/api/phase5_hitl.py) records a rejection; the Phase 5 phase (phase5_hitl_review.py), which
is blocked waiting for the decision, turns it into a generate pass limited to the rejected artifact.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from src.core.db.models import Run

_log = logging.getLogger(__name__)

# Rejections allowed per artifact. After the last one the regenerated version can only be approved.
MAX_REJECTIONS = 3

# Run output type -> design review artifact type. Output types without an entry are not reviewed.
OUTPUT_TO_ARTIFACT: dict[str, str] = {
    "pptx": "pptx",
    "docx": "docx",
    "xlsx": "xlsx",
    "pdf": "pdf",
    "sop": "sop",
    "narrative": "narrative",
    "process_map": "drawio",
    "drawio": "drawio",
}
ARTIFACT_TO_OUTPUT: dict[str, str] = {"drawio": "process_map"}

DEFAULT_FEEDBACK = "The reviewer rejected this in design review. Improve its design quality and clarity."


def reviewed_artifact_types(requested_outputs: list[str]) -> list[str]:
    """Design review artifact types for a run's requested outputs, in request order, without duplicates."""
    out: list[str] = []
    for output_type in requested_outputs or []:
        artifact_type = OUTPUT_TO_ARTIFACT.get(str(output_type).strip().lower())
        if artifact_type and artifact_type not in out:
            out.append(artifact_type)
    return out


def output_type_for(artifact_type: str) -> str:
    return ARTIFACT_TO_OUTPUT.get(artifact_type, artifact_type)


def rejections_used(attempt_count: int) -> int:
    """attempt_count is 1 for the first version and grows by one per rejection."""
    return max(0, int(attempt_count or 1) - 1)


def queue_phase3_regeneration(
    run_id: str,
    artifact_type: str,
    rejected_slides: list[int] | None,
    approved_slides: list[int] | None,
    new_version: str,
    rejection_type: str,
    feedback: str,
    session: Session,
) -> dict:
    """Mark an artifact for regeneration in the run's Phase 5 state. The caller commits.

    The waiting Phase 5 phase picks this up and runs a generate pass for it.
    """
    run = session.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    approval_data = json.loads(run.phase_5_approval_data or "{}")
    approval_data.setdefault(artifact_type, {}).update(
        {
            "status": "regenerating",
            "regenerate_mode": rejection_type,  # "partial" (PPTX slides) or "full"
            "rejected_slides": rejected_slides or [],
            "approved_slides": approved_slides or [],
            "new_version": new_version,
            "feedback": feedback,
        }
    )
    run.phase_5_approval_data = json.dumps(approval_data)
    _log.info("phase5: %s of run %s queued for %s regeneration as %s", artifact_type, run_id, rejection_type, new_version)
    return {
        "status": "queued",
        "artifact": artifact_type,
        "new_version": new_version,
        "regenerate_mode": rejection_type,
        "feedback": feedback,
    }


def get_regeneration_instruction(run: Run, artifact_type: str, session: Session) -> dict | None:
    """Regeneration parameters for an artifact, or None when it is not being regenerated."""
    artifact_data = json.loads(run.phase_5_approval_data or "{}").get(artifact_type, {})
    if artifact_data.get("status") != "regenerating":
        return None
    return {
        "artifact_type": artifact_type,
        "regenerate_mode": artifact_data.get("regenerate_mode"),
        "rejected_slides": artifact_data.get("rejected_slides", []),
        "approved_slides": artifact_data.get("approved_slides", []),
        "new_version": artifact_data.get("new_version"),
        "feedback": artifact_data.get("feedback"),
    }


def regeneration_plan(
    plan_payload: dict[str, Any],
    regenerating: dict[str, dict[str, Any]],
    prior_slides: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """The run's plan with the design review's rejections applied, for one generate pass.

    A partial deck rejection uses the PPTX agent's repair mode (prior deck plus per-slide feedback): only the
    rejected slides are rebuilt and the rest restored verbatim. Everything else is rebuilt whole, guided by
    the reviewer's feedback in the regeneration directive every agent reads.
    """
    plan = dict(plan_payload or {})
    plan.pop("prior_pptx_slides", None)
    plan.pop("pptx_visual_feedback", None)
    lines: list[str] = []
    for artifact_type, data in regenerating.items():
        feedback = str(data.get("feedback") or "").strip() or DEFAULT_FEEDBACK
        slides = [int(n) for n in data.get("rejected_slides") or [] if str(n).isdigit()]
        if artifact_type == "pptx" and data.get("regenerate_mode") == "partial" and slides and prior_slides:
            plan["prior_pptx_slides"] = prior_slides
            plan["pptx_visual_feedback"] = [
                {"slide_index": n, "instruction": f"Design review rejected this slide: {feedback}"} for n in sorted(set(slides))
            ]
            lines.append(f"Design review: regenerate only slides {sorted(set(slides))} of the deck; keep every other slide unchanged.")
        else:
            lines.append(f"Design review rejected the {artifact_type.upper()} output. Regenerate it in full. Reviewer feedback: {feedback}")
    previous = str(plan.get("regeneration_directive") or "").strip()
    directive = "\n".join(lines)
    plan["regeneration_directive"] = f"{previous}\n\n{directive}".strip() if previous else directive
    return plan
