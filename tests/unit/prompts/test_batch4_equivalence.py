"""Batch 4: Equivalence tests for Sheldon conversation copilot prompts."""

from src.prompts.registry import get_prompt


class TestSheldonPrompts:
    """Test that Sheldon YAML prompts match their original inline versions."""

    def test_discovery_question_equivalence(self):
        """sheldon_discovery_question.yaml matches original."""
        yaml_prompt = get_prompt("sheldon_discovery_question").render_system(
            known_summary_context=""
        )

        # Verify key phrases from original
        assert "thoughtful colleague" in yaml_prompt
        assert "single most important missing question" in yaml_prompt
        assert "2-3 sentences" in yaml_prompt

    def test_context_reply_equivalence(self):
        """sheldon_context_reply.yaml matches original."""
        yaml_prompt = get_prompt("sheldon_context_reply").render_system(
            wiki_insight_context=""
        )

        # Verify key phrases from original
        assert "ground every response" in yaml_prompt
        assert "vending machine" in yaml_prompt
        assert "text-only interface" in yaml_prompt
        assert "Type \"go\" to queue the run" in yaml_prompt

    def test_acknowledgment_equivalence(self):
        """sheldon_acknowledgment.yaml matches original."""
        yaml_prompt = get_prompt("sheldon_acknowledgment").render_system()

        # Verify key phrases
        assert "energetic creative partner" in yaml_prompt
        assert "brief acknowledgment" in yaml_prompt
        assert "1-2 sentences" in yaml_prompt
        assert "text-only interface" in yaml_prompt

    def test_conversation_summary_equivalence(self):
        """sheldon_conversation_summary.yaml matches original."""
        yaml_prompt = get_prompt("sheldon_conversation_summary").render_system()

        # Verify key phrases
        assert "concise summarizer" in yaml_prompt
        assert "third-person summary" in yaml_prompt
        assert "max 200 words" in yaml_prompt
        assert "plain prose" in yaml_prompt

    def test_followup_handler_equivalence(self):
        """sheldon_followup_handler.yaml matches original."""
        yaml_prompt = get_prompt("sheldon_followup_handler").render_system()

        # Verify key phrases
        assert "execution partner" in yaml_prompt
        assert "follow-up question" in yaml_prompt
        assert "direct, helpful response" in yaml_prompt
        assert "2-3 sentences" in yaml_prompt

    def test_out_of_scope_equivalence(self):
        """sheldon_out_of_scope.yaml matches original."""
        yaml_prompt = get_prompt("sheldon_out_of_scope").render_system()

        # Verify key phrases
        assert "helpful and witty digital teammate" in yaml_prompt
        assert "outside your current capabilities" in yaml_prompt
        assert "SHORT (2-3 sentences max)" in yaml_prompt
        assert "proposals, models, reports, documentation" in yaml_prompt


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
