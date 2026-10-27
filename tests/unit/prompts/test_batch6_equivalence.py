"""Batch 6: Equivalence tests for swarm and workflow orchestration prompts."""

from src.prompts.registry import get_prompt


class TestSwarmPrompts:
    """Test that swarm YAML prompts match their original inline versions."""

    def test_task_executor_equivalence(self):
        """swarm_task_executor.yaml matches original."""
        yaml_prompt = get_prompt("swarm_task_executor").render_system()

        # Verify key phrases
        assert "complete short workflow tasks" in yaml_prompt
        assert "document run" in yaml_prompt
        assert "concisely" in yaml_prompt

    def test_orchestration_json_equivalence(self):
        """swarm_orchestration_json.yaml matches original."""
        yaml_prompt = get_prompt("swarm_orchestration_json").render_system()

        # Verify key phrases
        assert "valid minified JSON" in yaml_prompt
        assert "task orchestration" in yaml_prompt


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
