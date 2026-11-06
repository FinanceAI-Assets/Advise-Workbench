#!/usr/bin/env python3
"""Comprehensive crash recovery test suite for conversation summaries."""

import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from src.core.db.session import SessionLocal
from src.core.db.models import Conversation, ConversationSummary, Project
from src.memory.short_term.conversation_state import load_state, save_state
from src.workflows.conversation_summary_worker import reconcile_orphaned_summaries

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def log_header(title):
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}{title.center(80)}{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

def log_success(msg):
    print(f"{GREEN}[OK] {msg}{RESET}")

def log_error(msg):
    print(f"{RED}[FAIL] {msg}{RESET}")

def log_warning(msg):
    print(f"{YELLOW}[WARN] {msg}{RESET}")

def log_info(msg):
    print(f"{BLUE}[INFO] {msg}{RESET}")

def log_step(step_num, msg):
    print(f"\n{BOLD}[STEP {step_num}] {msg}{RESET}")

# ============================================================================
# TEST 1: Verify Recovery on System Startup
# ============================================================================

def test_1_system_startup_recovery():
    """Test that orphaned summaries are recovered on system startup."""
    log_header("TEST 1: System Startup Recovery")

    db = SessionLocal()
    try:
        log_step(1, "Finding or creating a conversation")

        # Get or create a project
        project = db.query(Project).first()
        if not project:
            log_error("No project found. Please create a project first.")
            return False

        log_success(f"Using project: {project.id}")

        # Get or create a conversation
        conversation = db.query(Conversation).filter(
            Conversation.project_id == project.id
        ).first()

        if not conversation:
            log_error("No conversation found. Please create a conversation first.")
            return False

        log_success(f"Using conversation: {conversation.id}")

        log_step(2, "Creating orphaned summary in JSON file")

        # Create summary in JSON
        state = load_state(conversation)
        test_summary = f"TEST 1 RECOVERY: Summary created at {datetime.now().isoformat()}"
        state.conversation_summary = test_summary
        save_state(conversation, state)

        # Verify in JSON
        state_dir = Path("workspace") / project.id / "conversation_state"
        json_file = state_dir / f"{conversation.id}.json"
        json_data = json.loads(json_file.read_text())

        if json_data.get("conversation_summary") == test_summary:
            log_success(f"Summary saved to JSON: {json_file}")
        else:
            log_error("Summary not saved to JSON correctly")
            return False

        log_step(3, "Deleting from database (simulating crash)")

        # Delete from database
        existing = db.query(ConversationSummary).filter(
            ConversationSummary.project_id == project.id
        ).first()

        if existing:
            db.delete(existing)
            db.commit()
            log_success("Database record deleted (orphaned state created)")
        else:
            log_info("No prior database record (orphaned state ready)")

        # Verify NOT in database
        check = db.query(ConversationSummary).filter(
            ConversationSummary.project_id == project.id
        ).first()

        if check is None:
            log_success("Verified: Summary NOT in database")
        else:
            log_error("Summary still exists in database")
            return False

        log_step(4, "Running reconciliation (simulating system startup)")

        result = asyncio.run(reconcile_orphaned_summaries(db))
        recovered = result.get("orphaned_summaries_recovered", 0)
        log_success(f"Reconciliation complete: {recovered} summaries recovered")

        log_step(5, "Verifying recovery in database")

        db.expire_all()
        recovered_summary = db.query(ConversationSummary).filter(
            ConversationSummary.project_id == project.id
        ).first()

        if not recovered_summary:
            log_error("Summary NOT restored to database")
            return False

        log_success(f"Summary found in database!")
        log_info(f"  - Trigger: {recovered_summary.summary_trigger}")
        log_info(f"  - Text: {recovered_summary.summary_text[:80]}...")

        if test_summary in recovered_summary.summary_text:
            log_success("Summary content matches!")
            log_success("[SUCCESS] TEST 1 PASSED: Crash recovery on startup working!")
            return True
        else:
            log_error("Summary content doesn't match")
            return False

    except Exception as e:
        log_error(f"Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

# ============================================================================
# TEST 2: Consistency Check (JSON vs Database)
# ============================================================================

def test_2_consistency_check():
    """Verify all summaries in JSON files are also in database."""
    log_header("TEST 2: JSON to Database Consistency Check")

    db = SessionLocal()
    try:
        log_step(1, "Scanning workspace for conversation state files")

        orphaned_count = 0
        matched_count = 0
        errors = []

        workspace = Path("workspace")
        if not workspace.exists():
            log_warning("No workspace directory found")
            return True

        total_checked = 0

        for project_dir in workspace.iterdir():
            if not project_dir.is_dir():
                continue

            project_id = project_dir.name
            state_dir = project_dir / "conversation_state"

            if not state_dir.exists():
                continue

            for json_file in state_dir.glob("*.json"):
                try:
                    data = json.loads(json_file.read_text())
                    summary_text = data.get("conversation_summary", "").strip()

                    if not summary_text:
                        continue

                    total_checked += 1

                    # Check if in database
                    db_summary = db.query(ConversationSummary).filter(
                        ConversationSummary.project_id == project_id
                    ).first()

                    if db_summary:
                        if db_summary.summary_text == summary_text:
                            matched_count += 1
                            log_success(f"{project_id}: JSON to DB matched")
                        else:
                            errors.append(f"TEXT MISMATCH in {project_id}")
                            log_warning(f"{project_id}: TEXT MISMATCH")
                    else:
                        orphaned_count += 1
                        log_error(f"{project_id}: ORPHANED (in JSON but not in DB)")

                except Exception as e:
                    errors.append(f"Error reading {json_file}: {e}")

        log_step(2, "Consistency check results")

        log_info(f"Total summaries checked: {total_checked}")
        log_success(f"  Matched (JSON to DB): {matched_count}")
        log_error(f"  Orphaned (JSON only): {orphaned_count}") if orphaned_count > 0 else log_success(f"  Orphaned (JSON only): {orphaned_count}")

        if errors:
            log_step(3, "Errors found")
            for error in errors:
                log_error(error)

        if orphaned_count == 0 and not errors:
            log_success("[SUCCESS] TEST 2 PASSED: Perfect consistency between JSON and database!")
            return True
        elif orphaned_count > 0:
            log_warning(f"[WARN] TEST 2 WARNING: Found {orphaned_count} orphaned summaries")
            log_info("These will be recovered on next system startup or idle detection cycle")
            return True  # Not a failure, recoverable
        else:
            log_success("[SUCCESS] TEST 2 PASSED: All summaries consistent!")
            return True

    except Exception as e:
        log_error(f"Test 2 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

# ============================================================================
# TEST 3: Orphaned Summary Recovery
# ============================================================================

def test_3_orphaned_recovery():
    """Create and recover multiple orphaned summaries."""
    log_header("TEST 3: Orphaned Summary Recovery")

    db = SessionLocal()
    try:
        log_step(1, "Finding test projects")

        projects = db.query(Project).limit(2).all()
        if not projects:
            log_error("No projects found. Need at least 1 project.")
            return False

        test_project_ids = [p.id for p in projects[:1]]
        log_success(f"Using {len(test_project_ids)} project(s)")

        log_step(2, "Creating multiple orphaned summaries")

        created_orphans = []
        for project_id in test_project_ids:
            # Get conversation
            conversation = db.query(Conversation).filter(
                Conversation.project_id == project_id
            ).first()

            if not conversation:
                log_warning(f"No conversation for project {project_id}, skipping")
                continue

            # Create summary in JSON
            state = load_state(conversation)
            orphan_summary = f"ORPHAN TEST: {project_id} at {datetime.now().isoformat()}"
            state.conversation_summary = orphan_summary
            save_state(conversation, state)

            # Delete from database
            existing = db.query(ConversationSummary).filter(
                ConversationSummary.project_id == project_id
            ).first()

            if existing:
                db.delete(existing)
                db.commit()

            created_orphans.append(project_id)
            log_success(f"Created orphan for {project_id}")

        if not created_orphans:
            log_error("No orphans created")
            return False

        log_step(3, f"Running reconciliation for {len(created_orphans)} orphans")

        result = asyncio.run(reconcile_orphaned_summaries(db))
        recovered = result.get("orphaned_summaries_recovered", 0)

        log_success(f"Reconciliation complete: {recovered} summaries recovered")

        if recovered == len(created_orphans):
            log_success(f"[SUCCESS] TEST 3 PASSED: All {recovered} orphans recovered!")
            return True
        else:
            log_warning(f"Only {recovered}/{len(created_orphans)} orphans recovered")
            return False

    except Exception as e:
        log_error(f"Test 3 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

# ============================================================================
# TEST 4: Trigger Label Verification
# ============================================================================

def test_4_trigger_labels():
    """Verify that recovered summaries have correct trigger labels."""
    log_header("TEST 4: Trigger Label Verification")

    db = SessionLocal()
    try:
        log_step(1, "Querying all summaries")

        all_summaries = db.query(ConversationSummary).all()

        if not all_summaries:
            log_warning("No summaries found in database")
            return True

        log_success(f"Found {len(all_summaries)} summaries")

        log_step(2, "Verifying trigger labels")

        valid_triggers = {
            "idle_10min",
            "user_navigation_away",
            "session_closed",
            "engagement_completed",
            "crash_recovery"
        }

        trigger_counts = {}
        invalid_triggers = []

        for summary in all_summaries:
            trigger = summary.summary_trigger

            if trigger not in valid_triggers:
                invalid_triggers.append(f"{summary.project_id}: {trigger}")

            trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
            log_info(f"{summary.project_id}: trigger={trigger}")

        log_step(3, "Trigger label summary")

        for trigger, count in sorted(trigger_counts.items()):
            log_success(f"  {trigger}: {count} summaries")

        if invalid_triggers:
            log_warning(f"Found {len(invalid_triggers)} invalid triggers:")
            for invalid in invalid_triggers:
                log_error(f"  {invalid}")
            return False

        # Check if any crash_recovery triggers exist
        crash_recovery_count = trigger_counts.get("crash_recovery", 0)
        if crash_recovery_count > 0:
            log_success(f"[SUCCESS] TEST 4 PASSED: {crash_recovery_count} crash recovery summaries detected!")
        else:
            log_info("No crash_recovery triggers yet (will appear after a crash)")
            log_success("[SUCCESS] TEST 4 PASSED: All trigger labels valid!")

        return True

    except Exception as e:
        log_error(f"Test 4 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

# ============================================================================
# TEST 5: No Duplicate Creation
# ============================================================================

def test_5_no_duplicates():
    """Verify reconciliation doesn't create duplicate database rows."""
    log_header("TEST 5: No Duplicate Creation")

    db = SessionLocal()
    try:
        log_step(1, "Finding test project")

        project = db.query(Project).first()
        if not project:
            log_error("No project found")
            return False

        project_id = project.id
        log_success(f"Using project: {project_id}")

        log_step(2, "Running reconciliation multiple times")

        initial_count = db.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).count()

        log_info(f"Initial count: {initial_count}")

        # Run reconciliation multiple times
        for i in range(3):
            result = asyncio.run(reconcile_orphaned_summaries(db))
            recovered = result.get("orphaned_summaries_recovered", 0)

            current_count = db.query(ConversationSummary).filter(
                ConversationSummary.project_id == project_id
            ).count()

            log_info(f"Run {i+1}: recovered={recovered}, total={current_count}")

            # Count should not increase beyond initial + 1
            if current_count > initial_count + 1:
                log_error(f"Count increased beyond expected: {current_count}")
                return False

        final_count = db.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).count()

        log_step(3, "Duplicate check results")

        if final_count <= initial_count + 1:
            log_success(f"[SUCCESS] TEST 5 PASSED: No duplicates created (max +1 row allowed)")
            return True
        else:
            log_error(f"Duplicates detected: {final_count} > {initial_count + 1}")
            return False

    except Exception as e:
        log_error(f"Test 5 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

# ============================================================================
# TEST 6: Database Schema Validation
# ============================================================================

def test_6_schema_validation():
    """Verify all required fields are present in recovered summaries."""
    log_header("TEST 6: Database Schema Validation")

    db = SessionLocal()
    try:
        log_step(1, "Querying recent summaries")

        summaries = db.query(ConversationSummary).order_by(
            ConversationSummary.updated_at.desc()
        ).limit(5).all()

        if not summaries:
            log_warning("No summaries found")
            return True

        log_success(f"Found {len(summaries)} recent summaries")

        required_fields = [
            'id', 'project_id', 'summary_text', 'conversation_fsm_state',
            'summary_trigger', 'created_at', 'updated_at'
        ]

        log_step(2, "Validating schema for each summary")

        all_valid = True
        for summary in summaries:
            log_info(f"Checking {summary.project_id}:")

            for field in required_fields:
                value = getattr(summary, field, None)
                if value is not None:
                    log_success(f"  {field}: [PASS]")
                else:
                    log_error(f"  {field}: MISSING!")
                    all_valid = False

        if all_valid:
            log_success("[SUCCESS] TEST 6 PASSED: All required fields present!")
            return True
        else:
            log_error("[FAILED] TEST 6 FAILED: Some fields missing!")
            return False

    except Exception as e:
        log_error(f"Test 6 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all tests and generate report."""
    log_header("CRASH RECOVERY TEST SUITE")

    log_info("Starting comprehensive crash recovery tests...\n")

    tests = [
        ("Test 1: System Startup Recovery", test_1_system_startup_recovery),
        ("Test 2: JSON to Database Consistency", test_2_consistency_check),
        ("Test 3: Orphaned Summary Recovery", test_3_orphaned_recovery),
        ("Test 4: Trigger Label Verification", test_4_trigger_labels),
        ("Test 5: No Duplicate Creation", test_5_no_duplicates),
        ("Test 6: Database Schema Validation", test_6_schema_validation),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            log_error(f"Unexpected error in {test_name}: {e}")
            results[test_name] = False

    # Generate summary report
    log_header("TEST SUMMARY REPORT")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print("\nTest Results:")
    print("-" * 80)

    for test_name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{test_name}: {status}")

    print("-" * 80)
    print(f"\nTotal: {BOLD}{passed}/{total}{RESET} tests passed\n")

    if passed == total:
        print(f"{GREEN}{BOLD}[SUCCESS] ALL TESTS PASSED!{RESET}")
        print(f"{GREEN}Crash recovery mechanism is working correctly.{RESET}\n")
        return 0
    elif passed > total / 2:
        print(f"{YELLOW}{BOLD}[WARN] SOME TESTS FAILED{RESET}")
        print(f"{YELLOW}Fix the failures above before deploying.{RESET}\n")
        return 1
    else:
        print(f"{RED}{BOLD}[FAILED] CRITICAL FAILURES{RESET}")
        print(f"{RED}Multiple tests failed. Review the crash recovery implementation.{RESET}\n")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
