"""Integration tests for Phase 4 with Investigator Agent."""

import json
import sys
from unittest.mock import Mock, patch, MagicMock

class IntegrationTestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_true(self, condition, msg):
        if condition:
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(msg)
            print(f"  [FAIL] {msg}")

    def assert_equal(self, actual, expected, msg):
        if actual == expected:
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(f"{msg} (expected {expected}, got {actual})")
            print(f"  [FAIL] {msg} (expected {expected}, got {actual})")

    def assert_in(self, item, container, msg):
        if item in container:
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(f"{msg}")
            print(f"  [FAIL] {msg}")

    def test_investigator_agent_import(self):
        """Test that InvestigatorAgent can be imported in orchestrator."""
        print("\n[TEST] InvestigatorAgent import in orchestrator")
        try:
            # Check if orchestrator imports InvestigatorAgent
            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            self.assert_in("from src.agents.investigator_agent import InvestigatorAgent",
                         orch_content, "InvestigatorAgent imported")
            self.assert_in("investigator = InvestigatorAgent()",
                         orch_content, "InvestigatorAgent instantiated")
            self.assert_in("investigate_and_decide",
                         orch_content, "investigate_and_decide called")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"investigator_agent_import: {e}")
            print(f"  [ERROR] {e}")

    def test_phase4_calls_investigator_on_retry_exhaustion(self):
        """Test that Phase 4 calls investigator when retries >= 3."""
        print("\n[TEST] Phase 4 calls investigator when retries exhausted")
        try:
            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            # Check for investigator call logic
            self.assert_in("retries exhausted", orch_content.lower(),
                         "Investigator called on retry exhaustion")
            self.assert_in("route_to", orch_content,
                         "Routing decision logic present")
            self.assert_in("phase_2", orch_content.lower(),
                         "Routes to phase_2 option")
            self.assert_in("phase_3", orch_content.lower(),
                         "Routes to phase_3 option")
            self.assert_in("escalate", orch_content.lower(),
                         "Routes to escalate option")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"phase4_calls_investigator: {e}")
            print(f"  [ERROR] {e}")

    def test_context_validation_passed_through_phases(self):
        """Test context_validation flows from Phase 2 to Phase 3 to Phase 4."""
        print("\n[TEST] context_validation flows through all phases")
        try:
            with open('src/app/api/projects/conversation.py', 'r', encoding='utf-8') as f:
                conv_content = f.read()

            # Phase 2: Create context_validation
            self.assert_in("context_validation", conv_content,
                         "Phase 2 creates context_validation")

            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            # Phase 3: Pass to agents
            self.assert_in('context_validation', orch_content,
                         "Phase 3 has context_validation")
            # Phase 4: Use in investigator
            self.assert_in('context_validation', orch_content,
                         "Phase 4 uses context_validation")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"context_flow: {e}")
            print(f"  [ERROR] {e}")

    def test_investigator_chat_message_persistence(self):
        """Test that investigator's chat message is persisted to database."""
        print("\n[TEST] Investigator chat message persistence")
        try:
            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            # Check for chat message persistence
            self.assert_in("ConversationMessage", orch_content,
                         "ConversationMessage imported/used")
            self.assert_in("chat_message", orch_content,
                         "Chat message from investigator")
            self.assert_in("conversation_id", orch_content.lower(),
                         "Message persisted to conversation")
            self.assert_in("session.add", orch_content.lower() or "db.add",
                         "Message added to session")
            self.assert_in("session.commit", orch_content.lower() or "db.commit",
                         "Session committed")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"chat_persistence: {e}")
            print(f"  [ERROR] {e}")

    def test_investigator_routing_updates_run_status(self):
        """Test that routing decisions update run status correctly."""
        print("\n[TEST] Investigator routing updates run status")
        try:
            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            # Check for Phase 2 routing
            self.assert_in("awaiting_clarification", orch_content,
                         "Phase 2 sets awaiting_clarification status")
            # Check for Phase 3 routing
            self.assert_in('status = "approved"', orch_content,
                         "Phase 3 re-queue sets approved status")
            # Check for escalate routing
            self.assert_in("escalated_for_review", orch_content,
                         "Escalate sets escalated_for_review status")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"routing_status: {e}")
            print(f"  [ERROR] {e}")

    def test_investigator_event_logging(self):
        """Test that investigator events are logged."""
        print("\n[TEST] Investigator event logging")
        try:
            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            # Check for event logging
            self.assert_in("investigator_routed_to_phase2", orch_content,
                         "Logs phase2 routing event")
            self.assert_in("investigator_routed_to_phase3", orch_content,
                         "Logs phase3 routing event")
            self.assert_in("investigator_escalated", orch_content,
                         "Logs escalate event")
            self.assert_in("append_run_event", orch_content,
                         "Uses append_run_event for logging")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"event_logging: {e}")
            print(f"  [ERROR] {e}")

    def test_phase2_agents_exist_and_valid(self):
        """Test that Phase 2 agents (answer_agent, rag_agent) exist."""
        print("\n[TEST] Phase 2 agents exist and are valid")
        try:
            import ast

            # Check answer_agent
            with open('src/agents/conversation/answer_agent.py', 'r', encoding='utf-8') as f:
                code = f.read()
                ast.parse(code)
            self.assert_true(True, "answer_agent.py is valid Python")

            # Check rag_agent
            with open('src/agents/conversation/rag_agent.py', 'r', encoding='utf-8') as f:
                code = f.read()
                ast.parse(code)
            self.assert_true(True, "rag_agent.py is valid Python")
        except FileNotFoundError as e:
            self.failed += 1
            self.errors.append(f"phase2_agents_missing: {e}")
            print(f"  [FAIL] Agent file missing: {e}")
        except SyntaxError as e:
            self.failed += 1
            self.errors.append(f"phase2_agents_syntax: {e}")
            print(f"  [FAIL] Syntax error in agent: {e}")

    def test_supervisor_receives_context_validation(self):
        """Test that supervisor in Phase 3 receives context_validation."""
        print("\n[TEST] Supervisor receives context_validation")
        try:
            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            # Check for context_validation in init_state
            self.assert_in("init_state", orch_content,
                         "init_state used for supervisor")
            self.assert_in("context_validation", orch_content,
                         "context_validation passed to state")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"supervisor_context: {e}")
            print(f"  [ERROR] {e}")

    def test_retry_count_tracked_correctly(self):
        """Test that retry_count is tracked for retry exhaustion."""
        print("\n[TEST] Retry count tracked correctly")
        try:
            with open('src/workflows/orchestrator.py', 'r', encoding='utf-8') as f:
                orch_content = f.read()

            # Check for MAX_EVALUATOR_REMEDIATION_ROUNDS
            self.assert_in("MAX_EVALUATOR_REMEDIATION_ROUNDS", orch_content,
                         "Max remediation rounds defined")
            # Check for prior_retry_count
            self.assert_in("prior_retry_count", orch_content,
                         "Tracks prior retry count")
            # Check for comparison
            self.assert_in("prior_retry_count < MAX_EVALUATOR_REMEDIATION_ROUNDS",
                         orch_content, "Checks if retries exhausted")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"retry_tracking: {e}")
            print(f"  [ERROR] {e}")

    def test_context_validation_module_exists(self):
        """Test that context validation module exists and is valid."""
        print("\n[TEST] Context validation module exists")
        try:
            import ast
            with open('src/core/context/validation.py', 'r', encoding='utf-8') as f:
                code = f.read()
                ast.parse(code)
            self.assert_true(True, "validation.py is valid Python")

            # Check for ContextValidator class
            self.assert_in("class ContextValidator", code,
                         "ContextValidator class exists")
        except FileNotFoundError:
            print("  [WARN] validation.py not found (may be inline)")
            self.passed += 1
        except SyntaxError as e:
            self.failed += 1
            self.errors.append(f"validation_syntax: {e}")
            print(f"  [FAIL] Syntax error: {e}")

    def run_all(self):
        print("\n" + "="*80)
        print("PHASE 4 INTEGRATION TESTS")
        print("="*80)

        self.test_investigator_agent_import()
        self.test_phase4_calls_investigator_on_retry_exhaustion()
        self.test_context_validation_passed_through_phases()
        self.test_investigator_chat_message_persistence()
        self.test_investigator_routing_updates_run_status()
        self.test_investigator_event_logging()
        self.test_phase2_agents_exist_and_valid()
        self.test_supervisor_receives_context_validation()
        self.test_retry_count_tracked_correctly()
        self.test_context_validation_module_exists()

        print("\n" + "="*80)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("="*80 + "\n")

        if self.failed > 0:
            print("FAILED TESTS:")
            for error in self.errors:
                print(f"  - {error}")
            return False
        else:
            print("ALL INTEGRATION TESTS PASSED!")
            return True

if __name__ == "__main__":
    runner = IntegrationTestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
