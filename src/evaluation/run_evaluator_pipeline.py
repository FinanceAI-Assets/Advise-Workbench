"""Run-level evaluator pipeline and PPTX evidence gate (extracted from run_worker)."""

from __future__ import annotations

import json
from typing import Any

from src.guardrails.policy import proposal_quality_policy


def pptx_evidence_gate_from_run_dir(run_dir: Any) -> dict[str, Any]:
    """Detect PPTX evidence hard-fail from on-disk render artifacts.

    Returns a gate payload used by the evaluator pipeline. ``passed`` is False only when
    the renderer marked ``evidence_hard_fail`` (unsupported numeric claims with a client
    source registry present) — other degraded render reasons stay out of this gate.
    """
    gate: dict[str, Any] = {
        "passed": True,
        "hard_fail": False,
        "unsupported_claims_count": 0,
        "summary": "",
        "remediation_hints": [],
        "render_status": None,
    }
    try:
        status_path = run_dir / "render_status.json"
        if status_path.is_file():
            raw_status = json.loads(status_path.read_text(encoding="utf-8"))
            if isinstance(raw_status, dict):
                gate["render_status"] = str(raw_status.get("pptx") or "").strip().lower() or None
    except Exception:  # noqa: S110 — render_status.json is optional
        pass
    qa_raw: dict[str, Any] = {}
    try:
        qa_path = run_dir / "pptx_render_quality.json"
        if qa_path.is_file():
            loaded = json.loads(qa_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                qa_raw = loaded
    except Exception:
        return gate
    if not qa_raw:
        # No presentation was rendered in this run, so there is nothing for this gate to judge.
        return gate

    evidence = qa_raw.get("evidence") if isinstance(qa_raw.get("evidence"), dict) else {}
    unsupported = int(evidence.get("unsupported_claims_count") or 0)
    gate["unsupported_claims_count"] = unsupported
    gate["summary"] = str(evidence.get("summary") or qa_raw.get("summary") or "").strip()

    hard_fail = bool(qa_raw.get("evidence_hard_fail"))
    # Defense in depth: if the flag was missing but render is degraded and evidence
    # failed with client sources present, treat it as a hard fail.
    if not hard_fail and gate["render_status"] == "degraded" and unsupported > 0:
        issues = qa_raw.get("issues") if isinstance(qa_raw.get("issues"), list) else []
        hard_fail = any("evidence validation failed" in str(i).lower() for i in issues)

    if not hard_fail:
        return gate

    gate["hard_fail"] = True
    gate["passed"] = False
    hints: list[dict[str, Any]] = []
    for i, sv in enumerate(evidence.get("slide_validations") or [], start=1):
        if not isinstance(sv, dict):
            continue
        validation = sv.get("validation") if isinstance(sv.get("validation"), dict) else {}
        unsupported_claims = validation.get("unsupported_claims") or []
        if not unsupported_claims:
            continue
        claims = ", ".join(
            str(c.get("claim") or "").strip()
            for c in unsupported_claims[:4]
            if isinstance(c, dict) and str(c.get("claim") or "").strip()
        )
        if not claims:
            continue
        title = str(sv.get("slide_title") or f"Slide {i}").strip()
        hints.append({
            "slide_index": i,
            "instruction": (
                f"{title}: unsupported figure(s) [{claims}]. Replace with sourced client "
                "values (cite filename/sheet) or remove the claim."
            ),
            "source": "evidence_hard_fail",
        })
    gate["remediation_hints"] = hints
    return gate


def build_evaluator_pipeline(
    *,
    requested_outputs: list[str],
    plan_payload: dict[str, Any],
    qa_report: dict[str, Any],
    visual_qa_report: dict[str, Any],
    guardrail_report: dict[str, Any],
    final_artifact_report: dict[str, Any] | None = None,
    evidence_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested_set = {str(x).strip().lower() for x in (requested_outputs or []) if str(x).strip()}
    gateable_outputs = {"narrative", "raci", "sop", "process_map", "docx", "pptx", "pdf", "xlsx"}
    proposal_policy = proposal_quality_policy(plan_payload, requested_outputs)
    if proposal_policy.get("active"):
        gateable_outputs |= set(proposal_policy.get("required_outputs") or [])
    has_gateable_outputs = bool(requested_set & gateable_outputs)

    # DEBUG: Log each check status
    print(f"\n[DEBUG-EVAL] ==================== EVALUATOR PIPELINE DEBUG ====================")
    print(f"[DEBUG-EVAL] Requested outputs: {requested_outputs}")
    print(f"[DEBUG-EVAL] Gateable outputs: {gateable_outputs}")
    print(f"[DEBUG-EVAL] Has gateable outputs: {has_gateable_outputs}")

    qa_passed = True if not has_gateable_outputs else bool((qa_report or {}).get("passed"))
    print(f"[DEBUG-EVAL] QA Check: passed={qa_passed}, report_status={qa_report.get('passed') if qa_report else 'N/A'}")
    if qa_report and not qa_passed:
        print(f"[DEBUG-EVAL]   → QA Report Details: {qa_report}")

    visual_status = str((visual_qa_report or {}).get("status") or "").lower()
    visual_passed = visual_status in set(proposal_policy.get("visual_pass_statuses") or {"pass", "warn", "skip"})
    print(f"[DEBUG-EVAL] Visual QA Check: status={visual_status}, passed={visual_passed}, pass_statuses={proposal_policy.get('visual_pass_statuses', ['pass', 'warn', 'skip'])}")
    if visual_qa_report and not visual_passed:
        print(f"[DEBUG-EVAL]   → Visual QA Report Details: {visual_qa_report}")

    guardrail_passed = (
        True
        if not has_gateable_outputs
        else str((guardrail_report or {}).get("status") or "").lower() == "pass"
    )
    print(f"[DEBUG-EVAL] Guardrail Check: passed={guardrail_passed}, status={guardrail_report.get('status') if guardrail_report else 'N/A'}")
    if guardrail_report and not guardrail_passed:
        print(f"[DEBUG-EVAL]   → Guardrail Report Details: {guardrail_report}")

    final_artifact_passed = True
    if isinstance(final_artifact_report, dict) and final_artifact_report:
        final_artifact_passed = bool(final_artifact_report.get("passed"))
    print(f"[DEBUG-EVAL] Final Artifact Check: passed={final_artifact_passed}")
    if final_artifact_report and not final_artifact_passed:
        print(f"[DEBUG-EVAL]   → Final Artifact Report Details: {final_artifact_report}")

    # Evidence hard-fail is a run-level gate: fabricated numbers with client sources
    # present must not ship as review_ready.
    evidence_passed = True
    if isinstance(evidence_gate, dict) and evidence_gate:
        evidence_passed = bool(evidence_gate.get("passed", True))
    print(f"[DEBUG-EVAL] Evidence Check: passed={evidence_passed}, gate={evidence_gate}")

    print(f"[DEBUG-EVAL] =========== OVERALL RESULT ===========")
    print(f"[DEBUG-EVAL] qa_passed={qa_passed}, visual_passed={visual_passed}, guardrail_passed={guardrail_passed}, final_artifact_passed={final_artifact_passed}, evidence_passed={evidence_passed}")

    final_status = "pass" if (qa_passed and visual_passed and guardrail_passed and final_artifact_passed and evidence_passed) else "fail"
    print(f"[DEBUG-EVAL] FINAL STATUS: {final_status}")
    print(f"[DEBUG-EVAL] =====================================================================\n")

    return {
        "qa_passed": qa_passed,
        "visual_qa_passed": visual_passed,
        "guardrails_passed": guardrail_passed,
        "final_artifact_qa_passed": final_artifact_passed,
        "evidence_passed": evidence_passed,
        "evidence_gate": {
            "hard_fail": bool((evidence_gate or {}).get("hard_fail")),
            "unsupported_claims_count": int((evidence_gate or {}).get("unsupported_claims_count") or 0),
            "summary": str((evidence_gate or {}).get("summary") or ""),
            "render_status": (evidence_gate or {}).get("render_status"),
        }
        if isinstance(evidence_gate, dict) and evidence_gate
        else None,
        "status": final_status,
        "quality_policy": proposal_policy,
    }


def guardrail_regeneration_directive(guardrail_report: dict[str, Any]) -> str:
    failed_gate = str((guardrail_report or {}).get("failed_gate") or "").strip()
    events = (guardrail_report or {}).get("guardrail_events") or []
    reason = ""
    if isinstance(events, list):
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if str(ev.get("gate") or "").strip() != failed_gate:
                continue
            reason = str(ev.get("reason") or "").strip()
            break
    base = (
        "Guardrail remediation required before final review. "
        "Revise outputs to satisfy compliance gates and remove unsupported claims."
    )
    if failed_gate == "gate_1_source_grounding":
        return (
            f"{base} Gate failed: source grounding. "
            "For each factual or quantitative claim, add explicit provenance in-line "
            "(for example: '(source: client-provided data)', '(source: benchmark assumptions)', "
            "or '(source: internal estimate; illustrative)'). Add a short 'Sources and assumptions' "
            "section summarizing key evidence used. Do not leave benchmark or percentage claims uncited."
        )
    if failed_gate == "gate_2_hallucination_check":
        return (
            f"{base} Gate failed: hallucination check. "
            "Remove or qualify unsupported claims, and mark unknowns as [TBC] rather than inventing values."
        )
    if failed_gate == "gate_4_reference_validation":
        return (
            f"{base} Gate failed: reference validation. "
            "Use a consistent source format for claims (for example '(source: ...)') and ensure references "
            "are directly tied to the statement they support."
        )
    if reason:
        return f"{base} Failed gate: {failed_gate}. Reason: {reason}"
    return f"{base} Failed gate: {failed_gate or 'unknown'}."


# Backward-compatible aliases for callers that import private names from run_worker.
_pptx_evidence_gate_from_run_dir = pptx_evidence_gate_from_run_dir
_build_evaluator_pipeline = build_evaluator_pipeline
_guardrail_regeneration_directive = guardrail_regeneration_directive
