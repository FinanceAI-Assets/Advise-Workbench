"""Batch 3: Equivalence tests for storyline builder prompts."""

from src.prompts.registry import get_prompt


class TestStorylinePrompts:
    """Test that storyline YAML prompts match their originals."""

    def test_arc_recommender_equivalence(self):
        """storyline_arc_recommender.yaml matches original."""
        yaml_prompt = get_prompt("storyline_arc_recommender").render_system()

        # Verify key phrases from original
        assert "strategic consulting copilot" in yaml_prompt
        assert "narrative arc" in yaml_prompt
        assert "recommended_arcs" in yaml_prompt

    def test_spine_builder_equivalence(self):
        """storyline_spine_builder.yaml matches original with template variables."""
        yaml_prompt = get_prompt("storyline_spine_builder").render_system(
            arc_name="test-arc",
            arc_structure="test-structure",
            visual_vocab="chart, table, bullets",
            numeric_visuals="chart, big_number"
        )

        # Verify key phrases from original
        assert "partner-level consulting storyliner" in yaml_prompt
        assert "Minto pyramid" in yaml_prompt
        assert "ASSERTION" in yaml_prompt
        assert "governing_thought" in yaml_prompt
        assert "test-arc" in yaml_prompt  # Template variable expanded


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
