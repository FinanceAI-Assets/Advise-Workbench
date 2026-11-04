"""Standalone test runner for InvestigatorAgent - no pytest required."""

import sys
import traceback
from src.agents.investigator_agent import investigate_and_decide, InvestigatorAgent

class TestRunner:
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
            self.errors.append(f"{msg} ({item} not in {container})")
            print(f"  [FAIL] {msg}")

    def assert_isinstance(self, obj, cls, msg):
        if isinstance(obj, cls):
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(f"{msg} (got {type(obj).__name__})")
            print(f"  [FAIL] {msg}")

    def test_analyze_failures_single_attempt(self):
        print("\n[TEST] analyze_failures - single attempt")
        try:
            agent = InvestigatorAgent()
            attempts = [
                {
                    "attempt": 1,
                    "error": "Chart data mismatch in PPTX",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                }
            ]
            result = agent.analyze_failures(attempts)

            self.assert_in("attempt_summaries", result, "Has attempt_summaries")
            self.assert_in("common_patterns", result, "Has common_patterns")
            self.assert_in("error_evolution", result, "Has error_evolution")
            self.assert_in("total_attempts", result, "Has total_attempts")
            self.assert_equal(result["total_attempts"], 1, "Total attempts = 1")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"analyze_failures_single: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_analyze_failures_three_same_errors(self):
        print("\n[TEST] analyze_failures - three same errors")
        try:
            agent = InvestigatorAgent()
            attempts = [
                {"attempt": 1, "error": "Chart data mismatch", "stage": "pptx", "artifact": "pptx"},
                {"attempt": 2, "error": "Chart data mismatch", "stage": "pptx", "artifact": "pptx"},
                {"attempt": 3, "error": "Chart data mismatch", "stage": "pptx", "artifact": "pptx"}
            ]
            result = agent.analyze_failures(attempts)

            self.assert_equal(result["total_attempts"], 3, "Total attempts = 3")
            self.assert_true("SAME stage fails every attempt" in result["error_evolution"],
                           "Evolution shows same stage fails")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"analyze_failures_three_same: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_classify_returns_valid_structure(self):
        print("\n[TEST] classify_root_cause - valid structure")
        try:
            agent = InvestigatorAgent()
            analysis = {
                "attempt_summaries": [
                    {"attempt": 1, "error": "Missing data"},
                    {"attempt": 2, "error": "Missing data"}
                ],
                "common_patterns": [{"keyword": "missing", "frequency": "2/2"}],
                "error_evolution": "SAME stage fails"
            }
            context = {
                "context_validation": {"has_conflicts": True, "overall_confidence": 0.5},
                "run_instruction": "Generate presentation"
            }

            result = agent.classify_root_cause(analysis, context)

            self.assert_in("root_cause", result, "Has root_cause")
            self.assert_in("category", result, "Has category")
            self.assert_in("confidence", result, "Has confidence")
            self.assert_in("reasoning", result, "Has reasoning")
            self.assert_in(result["root_cause"], agent.root_causes.keys(),
                         f"Root cause is valid: {result['root_cause']}")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"classify_returns_structure: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_classify_confidence_bounds(self):
        print("\n[TEST] classify_root_cause - confidence bounds")
        try:
            agent = InvestigatorAgent()
            analysis = {
                "attempt_summaries": [{"attempt": 1, "error": "Test"}],
                "common_patterns": [],
                "error_evolution": "Test"
            }
            context = {"context_validation": {}}

            result = agent.classify_root_cause(analysis, context)

            self.assert_true(result["confidence"] >= 0.0, "Confidence >= 0.0")
            self.assert_true(result["confidence"] <= 1.0, "Confidence <= 1.0")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"classify_confidence_bounds: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_generate_chat_explanation_returns_string(self):
        print("\n[TEST] generate_chat_explanation - returns string")
        try:
            agent = InvestigatorAgent()
            analysis = {
                "attempt_summaries": [
                    {"attempt": 1, "error": "Error 1", "stage": "gen", "artifact": "pptx"}
                ],
                "common_patterns": [],
                "error_evolution": "Test",
                "total_attempts": 1
            }
            classification = {
                "root_cause": "data_problem",
                "category": "Data Problem",
                "confidence": 0.85,
                "reasoning": "Missing data"
            }

            result = agent.generate_chat_explanation(analysis, classification)

            self.assert_isinstance(result, str, "Returns string")
            self.assert_true(len(result) > 0, "String is not empty")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"generate_chat_explanation: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_route_data_problem_to_phase2(self):
        print("\n[TEST] make_routing_decision - data problem -> Phase 2")
        try:
            agent = InvestigatorAgent()
            classification = {"root_cause": "data_problem", "confidence": 0.9}
            context_validation = {
                "has_conflicts": True,
                "conflicts": {"conflicts": [{"field": "test"}]}
            }

            result = agent.make_routing_decision(classification, context_validation)

            self.assert_equal(result["route_to"], "phase_2", "Routes to phase_2")
            self.assert_in("message", result, "Has message")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"route_data_problem: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_route_llm_problem_to_phase3(self):
        print("\n[TEST] make_routing_decision - LLM problem -> Phase 3")
        try:
            agent = InvestigatorAgent()
            classification = {"root_cause": "llm_problem", "confidence": 0.7}
            context_validation = {}

            result = agent.make_routing_decision(classification, context_validation)

            self.assert_equal(result["route_to"], "phase_3", "Routes to phase_3")
            self.assert_in("guidance", result, "Has guidance")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"route_llm_problem: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_route_technical_problem_escalate(self):
        print("\n[TEST] make_routing_decision - technical problem -> escalate")
        try:
            agent = InvestigatorAgent()
            classification = {"root_cause": "technical_problem", "confidence": 0.9}
            context_validation = {}

            result = agent.make_routing_decision(classification, context_validation)

            self.assert_equal(result["route_to"], "escalate", "Routes to escalate")
            self.assert_in("alternatives", result, "Has alternatives")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"route_technical_problem: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def test_full_pipeline_returns_complete_result(self):
        print("\n[TEST] investigate_and_decide - complete pipeline")
        try:
            agent = InvestigatorAgent()
            attempts = [
                {"attempt": 1, "error": "Missing data", "stage": "gen", "artifact": "pptx"},
                {"attempt": 2, "error": "Missing data", "stage": "gen", "artifact": "pptx"}
            ]
            context = {
                "context_validation": {"has_conflicts": True},
                "run_instruction": "Generate report"
            }

            result = agent.investigate_and_decide(attempts, context)

            self.assert_in("analysis", result, "Has analysis")
            self.assert_in("classification", result, "Has classification")
            self.assert_in("chat_message", result, "Has chat_message")
            self.assert_in("routing_decision", result, "Has routing_decision")
            self.assert_in("investigator_confidence", result, "Has confidence")
            self.assert_in("ready_to_route", result, "Has ready_to_route")
            self.assert_equal(result["ready_to_route"], True, "ready_to_route = True")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"full_pipeline: {str(e)}")
            print(f"  [ERROR] EXCEPTION: {e}")

    def run_all(self):
        print("\n" + "="*80)
        print("INVESTIGATOR AGENT UNIT TESTS")
        print("="*80)

        self.test_analyze_failures_single_attempt()
        self.test_analyze_failures_three_same_errors()
        self.test_classify_returns_valid_structure()
        self.test_classify_confidence_bounds()
        self.test_generate_chat_explanation_returns_string()
        self.test_route_data_problem_to_phase2()
        self.test_route_llm_problem_to_phase3()
        self.test_route_technical_problem_escalate()
        self.test_full_pipeline_returns_complete_result()

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
            return True

if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
