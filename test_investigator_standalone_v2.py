"""Standalone test runner for updated InvestigatorAgent LangGraph implementation."""

import sys
from src.agents.investigator_agent import investigate_and_decide

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_in(self, key, obj, msg):
        if key in obj:
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
            print(f"  [FAIL] {msg}")

    def assert_true(self, condition, msg):
        if condition:
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(msg)
            print(f"  [FAIL] {msg}")

    def test_full_pipeline_single_attempt(self):
        print("\n[TEST] Full pipeline - single attempt")
        try:
            attempts = [
                {"attempt": 1, "error": "Chart mismatch", "stage": "pptx", "artifact": "pptx"}
            ]
            context = {"context_validation": {}}
            result = investigate_and_decide(attempts, context)

            self.assert_in("analysis", result, "Has analysis")
            self.assert_in("classification", result, "Has classification")
            self.assert_in("chat_message", result, "Has chat_message")
            self.assert_in("routing_decision", result, "Has routing_decision")
            self.assert_true(result.get("ready_to_route"), "Ready to route")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"test_full_pipeline: {str(e)}")
            print(f"  [ERROR] {e}")

    def test_data_problem_detection(self):
        print("\n[TEST] Data problem detection")
        try:
            attempts = [
                {"attempt": 1, "error": "Missing metric", "stage": "gen", "artifact": "a"},
                {"attempt": 2, "error": "Missing metric", "stage": "gen", "artifact": "a"},
                {"attempt": 3, "error": "Missing metric", "stage": "gen", "artifact": "a"}
            ]
            context = {"context_validation": {"has_conflicts": True}}
            result = investigate_and_decide(attempts, context)

            classification = result.get("classification", {})
            self.assert_equal(classification.get("root_cause"), "data_problem",
                            "Classified as data_problem")
            routing = result.get("routing_decision", {})
            self.assert_equal(routing.get("route_to"), "phase_2", "Routes to phase_2")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"test_data_problem: {str(e)}")
            print(f"  [ERROR] {e}")

    def test_llm_problem_detection(self):
        print("\n[TEST] LLM problem detection")
        try:
            attempts = [
                {"attempt": 1, "error": "Wrong scale", "stage": "pptx", "artifact": "a"},
                {"attempt": 2, "error": "Wrong narrative", "stage": "doc", "artifact": "b"},
                {"attempt": 3, "error": "Wrong format", "stage": "xlsx", "artifact": "c"}
            ]
            context = {"context_validation": {}}
            result = investigate_and_decide(attempts, context)

            classification = result.get("classification", {})
            self.assert_equal(classification.get("root_cause"), "llm_problem",
                            "Classified as llm_problem")
            routing = result.get("routing_decision", {})
            self.assert_equal(routing.get("route_to"), "phase_3", "Routes to phase_3")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"test_llm_problem: {str(e)}")
            print(f"  [ERROR] {e}")

    def test_technical_problem_escalation(self):
        print("\n[TEST] Technical problem escalation")
        try:
            attempts = [
                {"attempt": 1, "error": "Unsupported 3D", "stage": "draw", "artifact": "a"},
                {"attempt": 2, "error": "Tool limit", "stage": "xlsx", "artifact": "b"},
                {"attempt": 3, "error": "Format error", "stage": "pdf", "artifact": "c"}
            ]
            context = {"context_validation": {}}
            result = investigate_and_decide(attempts, context)

            classification = result.get("classification", {})
            self.assert_equal(classification.get("root_cause"), "technical_problem",
                            "Classified as technical_problem")
            routing = result.get("routing_decision", {})
            self.assert_equal(routing.get("route_to"), "escalate", "Routes to escalate")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"test_technical_problem: {str(e)}")
            print(f"  [ERROR] {e}")

    def test_confidence_scoring(self):
        print("\n[TEST] Confidence scoring")
        try:
            attempts = [
                {"attempt": 1, "error": "Data error 1", "stage": "s", "artifact": "a"},
                {"attempt": 2, "error": "Data error 2", "stage": "s", "artifact": "a"}
            ]
            context = {"context_validation": {}}
            result = investigate_and_decide(attempts, context)

            confidence = result.get("investigator_confidence", 0)
            self.assert_true(0.0 <= confidence <= 1.0, "Confidence in range [0, 1]")
            self.assert_true(confidence > 0.5, "Confidence > 0.5")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"test_confidence: {str(e)}")
            print(f"  [ERROR] {e}")

    def test_chat_message_generated(self):
        print("\n[TEST] Chat message generation")
        try:
            attempts = [
                {"attempt": 1, "error": "Test error", "stage": "gen", "artifact": "a"}
            ]
            context = {"context_validation": {}}
            result = investigate_and_decide(attempts, context)

            message = result.get("chat_message", "")
            self.assert_true(len(message) > 50, "Chat message substantial")
            self.assert_true("Investigator" in message or "investigator" in message.lower(),
                           "Message mentions investigator")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"test_chat_message: {str(e)}")
            print(f"  [ERROR] {e}")

    def run_all(self):
        print("\n" + "="*80)
        print("LANGGRAPH INVESTIGATOR AGENT - UPDATED TESTS")
        print("="*80)

        self.test_full_pipeline_single_attempt()
        self.test_data_problem_detection()
        self.test_llm_problem_detection()
        self.test_technical_problem_escalation()
        self.test_confidence_scoring()
        self.test_chat_message_generated()

        print("\n" + "="*80)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("="*80 + "\n")

        if self.failed > 0:
            print("FAILED TESTS:")
            for error in self.errors:
                print(f"  - {error}")
            return False
        else:
            print("ALL TESTS PASSED!")
            print("\nThe InvestigatorAgent LangGraph implementation is working correctly!")
            return True

if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
