"""Batch 5: Equivalence tests for evaluation and quality assessment prompts."""

from src.prompts.registry import get_prompt


class TestEvaluationPrompts:
    """Test that evaluation YAML prompts match their original inline versions."""

    def test_visual_qa_reviewer_equivalence(self):
        """visual_qa_reviewer.yaml matches original."""
        yaml_prompt = get_prompt("visual_qa_reviewer").render_system(
            visual_criteria_mode="Use strict visual criteria (layout, typography, spacing, hierarchy, table quality) because these are native document renders."
        )

        # Verify key phrases
        assert "document visual QA reviewer" in yaml_prompt
        assert "inspect the provided rendered document images" in yaml_prompt.lower()
        assert "strict JSON" in yaml_prompt

    def test_editorial_reviewer_equivalence(self):
        """editorial_reviewer.yaml matches original."""
        yaml_prompt = get_prompt("editorial_reviewer").render_system()

        # Verify key phrases
        assert "expert editorial reviewer" in yaml_prompt
        assert "JSON" in yaml_prompt

    def test_narrative_coherence_equivalence(self):
        """narrative_coherence_reviewer.yaml matches original."""
        yaml_prompt = get_prompt("narrative_coherence_reviewer").render_system()

        # Verify key phrases
        assert "narrative deliverables" in yaml_prompt
        assert "coherence" in yaml_prompt
        assert "strict JSON" in yaml_prompt

    def test_wiki_relationship_analyzer_equivalence(self):
        """wiki_relationship_analyzer.yaml matches original."""
        yaml_prompt = get_prompt("wiki_relationship_analyzer").render_system()

        # Verify key phrases
        assert "knowledge management assistant" in yaml_prompt
        assert "semantic relationships" in yaml_prompt
        assert "wiki pages" in yaml_prompt

    def test_wiki_qa_reviewer_equivalence(self):
        """wiki_qa_reviewer.yaml matches original."""
        yaml_prompt = get_prompt("wiki_qa_reviewer").render_system()

        # Verify key phrases
        assert "QA reviewer" in yaml_prompt
        assert "strict JSON" in yaml_prompt

    def test_pptx_title_critic_equivalence(self):
        """pptx_title_critic.yaml matches original."""
        yaml_prompt = get_prompt("pptx_title_critic").render_system()

        # Verify key phrases
        assert "critique" in yaml_prompt
        assert "executive-deck slide titles" in yaml_prompt
        assert "JSON" in yaml_prompt


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
