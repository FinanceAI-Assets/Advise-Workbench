#!/usr/bin/env python3
"""
Test Quality Evaluation Pipeline

This script tests if the quality evaluation system is working properly.
It scans for existing artifacts and runs the evaluation pipeline on them.

Run this AFTER you've generated artifacts with Sheldon.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.storage import workspace_path
from src.evaluation.quality_evaluation_hook import trigger_quality_evaluation


def find_projects_with_artifacts():
    """Find all projects that have runs with artifacts."""
    workspace_root = workspace_path("dummy")  # Get workspace root
    workspace_root = workspace_root.parent  # Go up one level to workspace/

    projects = {}

    for project_dir in workspace_root.iterdir():
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue

        runs_dir = project_dir / "runs"
        if not runs_dir.exists():
            continue

        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue

            # Find artifacts - ONLY DOCX, PPTX, PDF (not XLSX, JSON, TXT, MD)
            artifacts = [
                f for f in run_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in [".docx", ".pptx", ".pdf"]
            ]

            if artifacts:
                projects[f"{project_dir.name}/{run_dir.name}"] = artifacts

    return projects


def main():
    print("\n" + "="*80)
    print("[TEST] Quality Evaluation Pipeline")
    print("="*80 + "\n")

    # Find projects with artifacts
    print("[SCAN] Looking for existing artifacts...")
    projects = find_projects_with_artifacts()

    if not projects:
        print("[FAIL] No projects with artifacts found!")
        print("\nYou need to:")
        print("  1. Start the backend: ./scripts/run_agent.sh")
        print("  2. Create a Sheldon engagement in the UI")
        print("  3. Generate artifacts (PPT, DOCX, etc.)")
        print("  4. Run this test again")
        return False

    print(f"[OK] Found {len(projects)} project(s) with artifacts\n")

    # Test each project
    all_passed = True
    for project_run, artifacts in projects.items():
        project_id, run_id = project_run.split("/")

        print(f"\n{'='*80}")
        print(f"[TEST] Testing: {project_id} / {run_id}")
        print(f"[TEST] Artifacts: {len(artifacts)}")
        for art in artifacts:
            print(f"       - {art.name}")
        print(f"{'='*80}\n")

        try:
            print("[DEBUG] Calling trigger_quality_evaluation()...")
            result = trigger_quality_evaluation(
                project_id=project_id,
                run_id=run_id,
                force=True  # Force re-evaluation even if cached
            )

            print(f"[DEBUG] Result: {result}")

            if result.get("success"):
                print(f"\n[SUCCESS] ✅ Quality evaluation WORKED!")
                print(f"   Grade: {result.get('quality_grade')}")
                print(f"   Score: {result.get('overall_score', 0):.2f}")
                print(f"   File: {result.get('report_path')}")
                print(f"   Summary: {result.get('summary', {})}")
            else:
                print(f"\n[FAIL] ❌ Quality evaluation failed!")
                print(f"   Error: {result.get('error')}")
                all_passed = False

        except Exception as e:
            import traceback
            print(f"\n[ERROR] ❌ Exception occurred!")
            print(f"   {type(e).__name__}: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            all_passed = False

    print(f"\n{'='*80}")
    if all_passed:
        print("[RESULT] ✅ All tests PASSED!")
    else:
        print("[RESULT] ❌ Some tests FAILED")
    print(f"{'='*80}\n")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
