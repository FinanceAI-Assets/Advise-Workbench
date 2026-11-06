"""Visual QA gate: a skipped deck check is not a pass, storytelling hints only warn, titles use real verbs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.config import Settings
from src.evaluation.action_title import classify_title, score_titles
from src.evaluation.run_evaluator_pipeline import build_evaluator_pipeline
from src.evaluation.run_visual_qa_augment import augment_visual_qa_with_render_hints


def _pipeline(visual_status: str, outputs: list[str]) -> dict:
    return build_evaluator_pipeline(
        requested_outputs=outputs,
        plan_payload={},
        qa_report={"passed": True},
        visual_qa_report={"status": visual_status},
        guardrail_report={"status": "pass"},
    )


def test_default_critic_mode_inspects_rendered_slides() -> None:
    assert Settings.model_fields["pptx_visual_critic_mode"].default == "pixel"


@pytest.mark.parametrize("status,expected", [("pass", True), ("warn", True), ("fail", False), ("skip", False)])
def test_deck_run_needs_a_real_visual_check(status: str, expected: bool) -> None:
    assert _pipeline(status, ["pptx"])["visual_qa_passed"] is expected


def test_skip_is_still_accepted_when_there_is_no_deck() -> None:
    assert _pipeline("skip", ["docx"])["visual_qa_passed"] is True
    assert _pipeline("fail", ["docx"])["visual_qa_passed"] is False


def _signals(run_dir: Path, *, pending: list[dict], quality: dict) -> None:
    (run_dir / "pptx_render_signals.json").write_text(json.dumps({"content_pending": pending}), encoding="utf-8")
    (run_dir / "pptx_render_quality.json").write_text(json.dumps({"storytelling_metrics": quality}), encoding="utf-8")


def test_storytelling_signals_warn_but_do_not_fail(tmp_path: Path) -> None:
    _signals(tmp_path, pending=[], quality={"clutter_risk_slides": [3], "weak_slides": [], "transition_issues": [4]})
    report = augment_visual_qa_with_render_hints({"status": "pass", "summary": "ok", "findings": []}, tmp_path)
    assert report["status"] == "warn"
    assert report["per_artifact"]["pptx"]["status"] == "warn"
    assert report["per_artifact"]["pptx"]["remediation_hints"]
    assert "placeholder" not in report["summary"]


def test_unresolved_placeholders_still_fail(tmp_path: Path) -> None:
    _signals(
        tmp_path,
        pending=[{"slide_index": 2, "title": "Pillars", "reason": "content pending"}],
        quality={"clutter_risk_slides": [], "weak_slides": [], "transition_issues": []},
    )
    report = augment_visual_qa_with_render_hints({"status": "pass", "summary": "ok", "findings": []}, tmp_path)
    assert report["status"] == "fail"
    assert "placeholders" in report["summary"]


def test_a_failed_check_is_never_downgraded_by_storytelling_hints(tmp_path: Path) -> None:
    _signals(tmp_path, pending=[], quality={"clutter_risk_slides": [2], "weak_slides": [], "transition_issues": []})
    report = augment_visual_qa_with_render_hints({"status": "fail", "summary": "bad", "findings": []}, tmp_path)
    assert report["status"] == "fail"


@pytest.mark.parametrize(
    "title",
    [
        "Fragmented systems hinder timely decisions across regions",
        "Procurement bottlenecks delay supplier payments by weeks",
        "Approval delays stretch cycle time well beyond targets",
        "Poor vendor master data undermines every downstream control",
        "Teams reduced manual touches across the close",
        "Manual reconciliation consumes most of the finance close",
    ],
)
def test_action_titles_with_common_verbs_are_assertions(title: str) -> None:
    assert classify_title(title).is_assertion


@pytest.mark.parametrize(
    "title",
    ["Process scale", "Operating pillars", "Workflow layers", "Role mandates", "Overview", "Roles and responsibilities"],
)
def test_topic_labels_are_still_flagged(title: str) -> None:
    assert not classify_title(title).is_assertion


def test_a_deck_of_real_action_titles_passes_the_title_check() -> None:
    titles = [
        "Fragmented systems hinder timely decisions across regions",
        "Procurement bottlenecks delay supplier payments by weeks",
        "Approval delays stretch cycle time well beyond targets",
        "Poor vendor master data undermines every downstream control",
        "Quick wins build momentum within ninety days",
    ]
    score, passed = score_titles(titles)
    assert passed and score.labels == 0
