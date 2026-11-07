"""Unit tests for InvestigatorAgent - Phase 4 failure analysis."""

import pytest
import json
from src.agents.investigator_agent import InvestigatorAgent


class TestInvestigatorAgentAnalyzeFailures:
    """Test analyze_failures() method."""

    def test_analyze_single_attempt(self):
        """Should handle single failed attempt."""
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

        assert "attempt_summaries" in result
        assert "common_patterns" in result
        assert "error_evolution" in result
        assert "total_attempts" in result
        assert result["total_attempts"] == 1
        assert len(result["attempt_summaries"]) == 1

    def test_analyze_three_attempts_same_error(self):
        """Should find common patterns when all attempts have same error."""
        agent = InvestigatorAgent()
        attempts = [
            {
                "attempt": 1,
                "error": "Chart data mismatch - missing metrics",
                "stage": "pptx_generation",
                "artifact": "pptx"
            },
            {
                "attempt": 2,
                "error": "Chart data mismatch - missing metrics",
                "stage": "pptx_generation",
                "artifact": "pptx"
            },
            {
                "attempt": 3,
                "error": "Chart data mismatch - missing metrics",
                "stage": "pptx_generation",
                "artifact": "pptx"
            }
        ]

        result = agent.analyze_failures(attempts)

        assert result["total_attempts"] == 3
        assert len(result["attempt_summaries"]) == 3
        assert len(result["common_patterns"]) > 0  # Should find "chart" or "data"
        assert "SAME stage fails every attempt" in result["error_evolution"]

    def test_analyze_three_attempts_different_errors(self):
        """Should detect when different stages fail across attempts."""
        agent = InvestigatorAgent()
        attempts = [
            {
                "attempt": 1,
                "error": "Chart data mismatch",
                "stage": "pptx_generation",
                "artifact": "pptx"
            },
            {
                "attempt": 2,
                "error": "Layout spacing issue",
                "stage": "layout_validation",
                "artifact": "pptx"
            },
            {
                "attempt": 3,
                "error": "Font rendering error",
                "stage": "visual_qa",
                "artifact": "pptx"
            }
        ]

        result = agent.analyze_failures(attempts)

        assert result["total_attempts"] == 3
        assert "Different stages fail" in result["error_evolution"]

    def test_analyze_handles_missing_fields(self):
        """Should handle attempts with missing fields gracefully."""
        agent = InvestigatorAgent()
        attempts = [
            {
                "attempt": 1,
                "error": "Some error"
                # missing stage and artifact
            },
            {
                "attempt": 2
                # missing everything
            }
        ]

        result = agent.analyze_failures(attempts)

        assert result["total_attempts"] == 2
        assert len(result["attempt_summaries"]) == 2


class TestInvestigatorAgentClassifyRootCause:
    """Test classify_root_cause() method."""

    def test_classify_returns_valid_structure(self):
        """Should return proper classification structure."""
        agent = InvestigatorAgent()
        analysis = {
            "attempt_summaries": [
                {"attempt": 1, "error": "Missing data"},
                {"attempt": 2, "error": "Missing data"},
                {"attempt": 3, "error": "Missing data"}
            ],
            "common_patterns": [{"keyword": "missing", "frequency": "3/3"}],
            "error_evolution": "SAME stage fails every attempt"
        }
        context = {
            "context_validation": {
                "has_conflicts": True,
                "overall_confidence": 0.5
            },
            "run_instruction": "Generate presentation"
        }

        result = agent.classify_root_cause(analysis, context)

        assert "root_cause" in result
        assert "category" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert result["root_cause"] in agent.root_causes.keys()
        assert 0.0 <= result["confidence"] <= 1.0

    def test_classify_confidence_bounds(self):
        """Should ensure confidence is between 0.0 and 1.0."""
        agent = InvestigatorAgent()
        analysis = {
            "attempt_summaries": [{"attempt": 1, "error": "Test error"}],
            "common_patterns": [],
            "error_evolution": "Single attempt"
        }
        context = {"context_validation": {}}

        result = agent.classify_root_cause(analysis, context)

        assert result["confidence"] >= 0.0
        assert result["confidence"] <= 1.0

    def test_classify_five_categories(self):
        """Should only return one of the 5 valid root causes."""
        agent = InvestigatorAgent()
        analysis = {
            "attempt_summaries": [{"attempt": 1, "error": "Test"}],
            "common_patterns": [],
            "error_evolution": "Test"
        }
        context = {"context_validation": {}}

        result = agent.classify_root_cause(analysis, context)

        valid_causes = list(agent.root_causes.keys())
        assert result["root_cause"] in valid_causes


class TestInvestigatorAgentGenerateChatExplanation:
    """Test generate_chat_explanation() method."""

    def test_generate_returns_string(self):
        """Should return markdown string."""
        agent = InvestigatorAgent()
        analysis = {
            "attempt_summaries": [
                {"attempt": 1, "error": "Test error 1", "stage": "generation", "artifact": "pptx"},
                {"attempt": 2, "error": "Test error 2", "stage": "generation", "artifact": "pptx"}
            ],
            "common_patterns": [{"keyword": "test", "frequency": "2/2"}],
            "error_evolution": "Same stage",
            "total_attempts": 2
        }
        classification = {
            "root_cause": "data_problem",
            "category": "🔴 Data Problem",
            "confidence": 0.85,
            "reasoning": "Missing required data"
        }

        result = agent.generate_chat_explanation(analysis, classification)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Investigator" in result or "investigator" in result.lower()

    def test_generate_includes_confidence(self):
        """Should include confidence score in message."""
        agent = InvestigatorAgent()
        analysis = {
            "attempt_summaries": [{"attempt": 1, "error": "Test", "stage": "s", "artifact": "a"}],
            "common_patterns": [],
            "error_evolution": "Test",
            "total_attempts": 1
        }
        classification = {
            "root_cause": "llm_problem",
            "category": "🟣 LLM Problem",
            "confidence": 0.92,
            "reasoning": "Model misunderstanding"
        }

        result = agent.generate_chat_explanation(analysis, classification)

        assert "92" in result or "0.92" in result

    def test_generate_includes_root_cause(self):
        """Should mention root cause in message."""
        agent = InvestigatorAgent()
        analysis = {
            "attempt_summaries": [{"attempt": 1, "error": "Test", "stage": "s", "artifact": "a"}],
            "common_patterns": [],
            "error_evolution": "Test",
            "total_attempts": 1
        }
        classification = {
            "root_cause": "approach_problem",
            "category": "🟡 Approach Problem",
            "confidence": 0.75,
            "reasoning": "Wrong methodology"
        }

        result = agent.generate_chat_explanation(analysis, classification)

        assert "Approach" in result or "approach" in result.lower()


class TestInvestigatorAgentMakeRoutingDecision:
    """Test make_routing_decision() method."""

    def test_route_data_problem_to_phase2(self):
        """Data problems should route to Phase 2."""
        agent = InvestigatorAgent()
        classification = {
            "root_cause": "data_problem",
            "confidence": 0.9
        }
        context_validation = {
            "has_conflicts": True,
            "conflicts": {
                "conflicts": [
                    {"field": "client_name", "wiki_value": "ABC", "lp_value": "XYZ"}
                ]
            }
        }

        result = agent.make_routing_decision(classification, context_validation)

        assert result["route_to"] == "phase_2"
        assert "clarification" in result.get("message", "").lower() or len(result.get("clarifications", [])) > 0

    def test_route_approach_problem_to_phase2(self):
        """Approach problems should route to Phase 2."""
        agent = InvestigatorAgent()
        classification = {
            "root_cause": "approach_problem",
            "confidence": 0.8
        }
        context_validation = {}

        result = agent.make_routing_decision(classification, context_validation)

        assert result["route_to"] == "phase_2"

    def test_route_requirements_problem_to_phase2(self):
        """Requirements problems should route to Phase 2."""
        agent = InvestigatorAgent()
        classification = {
            "root_cause": "requirements_problem",
            "confidence": 0.85
        }
        context_validation = {}

        result = agent.make_routing_decision(classification, context_validation)

        assert result["route_to"] == "phase_2"

    def test_route_llm_problem_to_phase3(self):
        """LLM problems should route to Phase 3 with guidance."""
        agent = InvestigatorAgent()
        classification = {
            "root_cause": "llm_problem",
            "confidence": 0.7
        }
        context_validation = {}

        result = agent.make_routing_decision(classification, context_validation)

        assert result["route_to"] == "phase_3"
        assert "guidance" in result

    def test_route_technical_problem_escalate(self):
        """Technical problems should escalate."""
        agent = InvestigatorAgent()
        classification = {
            "root_cause": "technical_problem",
            "confidence": 0.9
        }
        context_validation = {}

        result = agent.make_routing_decision(classification, context_validation)

        assert result["route_to"] == "escalate"
        assert "alternatives" in result

    def test_route_decision_includes_confidence(self):
        """Routing decision should include confidence."""
        agent = InvestigatorAgent()
        classification = {
            "root_cause": "llm_problem",
            "confidence": 0.65
        }
        context_validation = {}

        result = agent.make_routing_decision(classification, context_validation)

        assert "confidence" in result
        assert result["confidence"] == 0.65


class TestInvestigatorAgentFullPipeline:
    """Test investigate_and_decide() - complete pipeline."""

    def test_full_pipeline_returns_complete_result(self):
        """Complete pipeline should return all components."""
        agent = InvestigatorAgent()
        attempts = [
            {"attempt": 1, "error": "Missing data", "stage": "generation", "artifact": "pptx"},
            {"attempt": 2, "error": "Missing data", "stage": "generation", "artifact": "pptx"},
            {"attempt": 3, "error": "Missing data", "stage": "generation", "artifact": "pptx"}
        ]
        context = {
            "context_validation": {"has_conflicts": True},
            "run_instruction": "Generate report"
        }

        result = agent.investigate_and_decide(attempts, context)

        assert "analysis" in result
        assert "classification" in result
        assert "chat_message" in result
        assert "routing_decision" in result
        assert "investigator_confidence" in result
        assert "ready_to_route" in result
        assert result["ready_to_route"] is True

    def test_full_pipeline_analysis_component(self):
        """Analysis should be complete."""
        agent = InvestigatorAgent()
        attempts = [
            {"attempt": 1, "error": "Error A", "stage": "s", "artifact": "a"},
            {"attempt": 2, "error": "Error B", "stage": "s", "artifact": "a"}
        ]
        context = {"context_validation": {}}

        result = agent.investigate_and_decide(attempts, context)

        analysis = result["analysis"]
        assert "attempt_summaries" in analysis
        assert "common_patterns" in analysis
        assert "error_evolution" in analysis

    def test_full_pipeline_classification_component(self):
        """Classification should be complete."""
        agent = InvestigatorAgent()
        attempts = [
            {"attempt": 1, "error": "Test", "stage": "s", "artifact": "a"}
        ]
        context = {"context_validation": {}}

        result = agent.investigate_and_decide(attempts, context)

        classification = result["classification"]
        assert "root_cause" in classification
        assert "category" in classification
        assert "confidence" in classification
        assert "reasoning" in classification

    def test_full_pipeline_routing_component(self):
        """Routing decision should be complete."""
        agent = InvestigatorAgent()
        attempts = [
            {"attempt": 1, "error": "Test", "stage": "s", "artifact": "a"}
        ]
        context = {"context_validation": {}}

        result = agent.investigate_and_decide(attempts, context)

        routing = result["routing_decision"]
        assert "route_to" in routing
        assert routing["route_to"] in ["phase_2", "phase_3", "escalate"]


class TestInvestigatorAgentEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_empty_attempts(self):
        """Should handle empty attempts list."""
        agent = InvestigatorAgent()
        attempts = []
        context = {"context_validation": {}}

        result = agent.investigate_and_decide(attempts, context)

        # Should still produce valid result structure
        assert "analysis" in result
        assert "classification" in result

    def test_handles_malformed_context(self):
        """Should handle missing context gracefully."""
        agent = InvestigatorAgent()
        attempts = [{"attempt": 1, "error": "Test", "stage": "s", "artifact": "a"}]
        context = {}  # Empty context

        result = agent.investigate_and_decide(attempts, context)

        assert "classification" in result
        assert result["classification"]["root_cause"] is not None

    def test_handles_very_long_error_messages(self):
        """Should truncate very long error messages."""
        agent = InvestigatorAgent()
        long_error = "X" * 5000
        attempts = [
            {"attempt": 1, "error": long_error, "stage": "s", "artifact": "a"}
        ]
        context = {"context_validation": {}}

        result = agent.investigate_and_decide(attempts, context)

        # Should not crash, should truncate in analysis
        assert result["analysis"]["attempt_summaries"][0]["error"] != long_error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
