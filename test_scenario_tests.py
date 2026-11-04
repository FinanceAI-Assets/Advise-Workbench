"""Scenario tests - realistic failure patterns for Phase 4."""

import sys
from src.agents.investigator_agent import InvestigatorAgent

class ScenarioTestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_equal(self, actual, expected, msg):
        if actual == expected:
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(f"{msg} (expected {expected}, got {actual})")
            print(f"  [FAIL] {msg}")

    def assert_in(self, item, container, msg):
        if item in container:
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(f"{msg}")
            print(f"  [FAIL] {msg}")

    def assert_true(self, condition, msg):
        if condition:
            self.passed += 1
            print(f"  [OK] {msg}")
        else:
            self.failed += 1
            self.errors.append(msg)
            print(f"  [FAIL] {msg}")

    def scenario_1_data_problem_all_same_error(self):
        """SCENARIO 1: All 3 attempts fail with same data error."""
        print("\n[SCENARIO 1] Data Problem - All 3 attempts fail with same error")
        print("-" * 60)

        try:
            agent = InvestigatorAgent()

            # Simulate 3 failed attempts with same data error
            attempts = [
                {
                    "attempt": 1,
                    "error": "Missing required metric: Revenue for Q1 2024 not found in retrieved documents",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                },
                {
                    "attempt": 2,
                    "error": "Missing required metric: Revenue for Q1 2024 not found in retrieved documents",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                },
                {
                    "attempt": 3,
                    "error": "Missing required metric: Revenue for Q1 2024 not found in retrieved documents",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                }
            ]

            context = {
                "context_validation": {
                    "has_conflicts": True,
                    "conflicts": {
                        "conflicts": [
                            {"field": "Q1_revenue", "wiki_value": "2M", "lp_value": "Use actual"}
                        ]
                    }
                },
                "run_instruction": "Create Q1 revenue presentation"
            }

            # Run investigation
            result = agent.investigate_and_decide(attempts, context)

            # Verify classification
            classification = result["classification"]
            self.assert_equal(classification["root_cause"], "data_problem",
                            "Correctly classified as data_problem")
            self.assert_true(classification["confidence"] >= 0.7,
                           "Confidence is high (>= 0.7)")

            # Verify routing
            routing = result["routing_decision"]
            self.assert_equal(routing["route_to"], "phase_2",
                            "Routed to Phase 2 for data clarification")
            self.assert_true(len(routing.get("clarifications", [])) > 0,
                           "Has clarification questions")

            # Verify chat message exists
            self.assert_true(len(result["chat_message"]) > 100,
                           "Chat message is substantial")
            self.assert_in("data", result["chat_message"].lower(),
                         "Chat mentions data issue")

            print("  [PASSED] Scenario 1 completed successfully")

        except Exception as e:
            self.failed += 1
            self.errors.append(f"Scenario 1: {str(e)}")
            print(f"  [ERROR] {e}")

    def scenario_2_llm_problem_model_misunderstanding(self):
        """SCENARIO 2: LLM Problem - Model keeps misunderstanding requirements."""
        print("\n[SCENARIO 2] LLM Problem - Model misunderstanding across attempts")
        print("-" * 60)

        try:
            agent = InvestigatorAgent()

            # Simulate 3 attempts where LLM generates wrong content
            attempts = [
                {
                    "attempt": 1,
                    "error": "Generated charts with incorrect scale - used linear instead of log",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                },
                {
                    "attempt": 2,
                    "error": "Slide narrative mismatch - discussed Q4 instead of Q1 metrics",
                    "stage": "narrative_generation",
                    "artifact": "docx"
                },
                {
                    "attempt": 3,
                    "error": "Table formatting wrong - columns in wrong order despite explicit instructions",
                    "stage": "xlsx_generation",
                    "artifact": "xlsx"
                }
            ]

            context = {
                "context_validation": {
                    "has_conflicts": False,
                    "overall_confidence": 0.95
                },
                "run_instruction": "Generate Q1 analysis with specific chart types and narrative flow"
            }

            # Run investigation
            result = agent.investigate_and_decide(attempts, context)

            # Verify classification
            classification = result["classification"]
            self.assert_equal(classification["root_cause"], "llm_problem",
                            "Correctly classified as llm_problem")

            # Verify routing
            routing = result["routing_decision"]
            self.assert_equal(routing["route_to"], "phase_3",
                            "Routed to Phase 3 for guidance/retry")
            self.assert_true("guidance" in routing,
                           "Provides guidance for retry")

            # Verify chat explains LLM issue
            self.assert_in("llm", result["chat_message"].lower(),
                         "Chat mentions LLM/model issue")

            print("  [PASSED] Scenario 2 completed successfully")

        except Exception as e:
            self.failed += 1
            self.errors.append(f"Scenario 2: {str(e)}")
            print(f"  [ERROR] {e}")

    def scenario_3_approach_problem_wrong_methodology(self):
        """SCENARIO 3: Approach Problem - Wrong methodology chosen."""
        print("\n[SCENARIO 3] Approach Problem - Wrong methodology")
        print("-" * 60)

        try:
            agent = InvestigatorAgent()

            # Simulate approach problem
            attempts = [
                {
                    "attempt": 1,
                    "error": "Presentation layout too dense - too many metrics per slide",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                },
                {
                    "attempt": 2,
                    "error": "Slide count excessive - 50 slides with detail instead of executive summary",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                },
                {
                    "attempt": 3,
                    "error": "Visual hierarchy wrong - all elements same emphasis level",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                }
            ]

            context = {
                "context_validation": {"has_conflicts": False},
                "run_instruction": "Create executive summary presentation"
            }

            # Run investigation
            result = agent.investigate_and_decide(attempts, context)

            # Verify classification
            classification = result["classification"]
            self.assert_equal(classification["root_cause"], "approach_problem",
                            "Correctly classified as approach_problem")

            # Verify routing
            routing = result["routing_decision"]
            self.assert_equal(routing["route_to"], "phase_2",
                            "Routed to Phase 2 for approach discussion")

            print("  [PASSED] Scenario 3 completed successfully")

        except Exception as e:
            self.failed += 1
            self.errors.append(f"Scenario 3: {str(e)}")
            print(f"  [ERROR] {e}")

    def scenario_4_requirements_problem_ambiguous_specs(self):
        """SCENARIO 4: Requirements Problem - Ambiguous specifications."""
        print("\n[SCENARIO 4] Requirements Problem - Ambiguous specs")
        print("-" * 60)

        try:
            agent = InvestigatorAgent()

            # Simulate requirements problem
            attempts = [
                {
                    "attempt": 1,
                    "error": "Unclear which audience - generated B2B content but user expected B2C",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                },
                {
                    "attempt": 2,
                    "error": "Scope ambiguous - user didn't specify: include competitors or not?",
                    "stage": "narrative_generation",
                    "artifact": "docx"
                },
                {
                    "attempt": 3,
                    "error": "Unclear definition of success - no acceptance criteria provided",
                    "stage": "qa_check",
                    "artifact": "multiple"
                }
            ]

            context = {
                "context_validation": {"has_conflicts": False},
                "run_instruction": "Generate business analysis"
            }

            # Run investigation
            result = agent.investigate_and_decide(attempts, context)

            # Verify classification
            classification = result["classification"]
            self.assert_equal(classification["root_cause"], "requirements_problem",
                            "Correctly classified as requirements_problem")

            # Verify routing
            routing = result["routing_decision"]
            self.assert_equal(routing["route_to"], "phase_2",
                            "Routed to Phase 2 for clarification")
            self.assert_in("clarify", routing.get("message", "").lower(),
                         "Message asks for clarification")

            print("  [PASSED] Scenario 4 completed successfully")

        except Exception as e:
            self.failed += 1
            self.errors.append(f"Scenario 4: {str(e)}")
            print(f"  [ERROR] {e}")

    def scenario_5_technical_problem_unsupported_format(self):
        """SCENARIO 5: Technical Problem - Unsupported format/limitation."""
        print("\n[SCENARIO 5] Technical Problem - Unsupported format")
        print("-" * 60)

        try:
            agent = InvestigatorAgent()

            # Simulate technical problem
            attempts = [
                {
                    "attempt": 1,
                    "error": "PDF generation failed - unsupported custom font requested",
                    "stage": "pdf_generation",
                    "artifact": "pdf"
                },
                {
                    "attempt": 2,
                    "error": "Drawing tool limitation - cannot create 3D charts with current library",
                    "stage": "drawio_generation",
                    "artifact": "drawio"
                },
                {
                    "attempt": 3,
                    "error": "Excel limitation - requested over 1M rows, exceeds max",
                    "stage": "xlsx_generation",
                    "artifact": "xlsx"
                }
            ]

            context = {
                "context_validation": {"has_conflicts": False},
                "run_instruction": "Generate complex data visualization"
            }

            # Run investigation
            result = agent.investigate_and_decide(attempts, context)

            # Verify classification
            classification = result["classification"]
            self.assert_equal(classification["root_cause"], "technical_problem",
                            "Correctly classified as technical_problem")

            # Verify routing
            routing = result["routing_decision"]
            self.assert_equal(routing["route_to"], "escalate",
                            "Escalated to user for technical issue")
            self.assert_true("alternatives" in routing,
                           "Provides alternatives")

            print("  [PASSED] Scenario 5 completed successfully")

        except Exception as e:
            self.failed += 1
            self.errors.append(f"Scenario 5: {str(e)}")
            print(f"  [ERROR] {e}")

    def scenario_6_mixed_errors_with_context_conflicts(self):
        """SCENARIO 6: Mixed errors + context conflicts."""
        print("\n[SCENARIO 6] Mixed errors with context validation conflicts")
        print("-" * 60)

        try:
            agent = InvestigatorAgent()

            # Simulate mixed errors with context conflicts
            attempts = [
                {
                    "attempt": 1,
                    "error": "Data mismatch - wiki says ABC Corp revenue is 10M, LP profile says 15M",
                    "stage": "pptx_generation",
                    "artifact": "pptx"
                },
                {
                    "attempt": 2,
                    "error": "Conflicting metrics - different sheets show different Q1 totals",
                    "stage": "xlsx_generation",
                    "artifact": "xlsx"
                },
                {
                    "attempt": 3,
                    "error": "Data currency issue - Q4 2023 data used instead of Q1 2024",
                    "stage": "narrative_generation",
                    "artifact": "docx"
                }
            ]

            context = {
                "context_validation": {
                    "has_conflicts": True,
                    "is_stale": True,
                    "age_days": 200,
                    "overall_confidence": 0.45,
                    "conflicts": {
                        "conflicts": [
                            {"field": "revenue_abc", "wiki_value": "10M", "lp_value": "15M"},
                            {"field": "data_date", "wiki_value": "Q4 2023", "lp_value": "Q1 2024"}
                        ]
                    }
                },
                "run_instruction": "Generate ABC Corp quarterly review"
            }

            # Run investigation
            result = agent.investigate_and_decide(attempts, context)

            # Verify classification - should identify data problem due to conflicts
            classification = result["classification"]
            self.assert_equal(classification["root_cause"], "data_problem",
                            "Correctly classified as data_problem despite mixed errors")

            # Verify routing - should route to Phase 2 due to conflicts
            routing = result["routing_decision"]
            self.assert_equal(routing["route_to"], "phase_2",
                            "Routed to Phase 2 for conflict clarification")

            # Verify clarifications include context issues
            clarifications = routing.get("clarifications", [])
            self.assert_true(len(clarifications) > 0,
                           "Provides clarification questions for conflicts")

            print("  [PASSED] Scenario 6 completed successfully")

        except Exception as e:
            self.failed += 1
            self.errors.append(f"Scenario 6: {str(e)}")
            print(f"  [ERROR] {e}")

    def run_all(self):
        print("\n" + "="*80)
        print("SCENARIO TESTS - REALISTIC FAILURE PATTERNS")
        print("="*80)

        self.scenario_1_data_problem_all_same_error()
        self.scenario_2_llm_problem_model_misunderstanding()
        self.scenario_3_approach_problem_wrong_methodology()
        self.scenario_4_requirements_problem_ambiguous_specs()
        self.scenario_5_technical_problem_unsupported_format()
        self.scenario_6_mixed_errors_with_context_conflicts()

        print("\n" + "="*80)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("="*80 + "\n")

        if self.failed > 0:
            print("FAILED SCENARIOS:")
            for error in self.errors:
                print(f"  - {error}")
            return False
        else:
            print("ALL SCENARIO TESTS PASSED!")
            return True

if __name__ == "__main__":
    runner = ScenarioTestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
