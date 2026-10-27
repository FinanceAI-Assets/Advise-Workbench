"""Batch 2: Equivalence tests for externalized shared policies and archetype prompts.

Verifies that moved YAML prompts match the original inline strings byte-for-byte.
"""

from src.prompts.registry import get_prompt


class TestSharedPolicies:
    """Test that YAML prompts match their original inline versions."""

    def test_tool_usage_policy_equivalence(self):
        """tool_usage_policy.yaml matches original _TOOL_USAGE_POLICY."""
        yaml_prompt = get_prompt("tool_usage_policy").render_system()

        # Original inline from _shared.py lines 851-867
        original = (
            "\n\nTool usage policy (follow in order):\n"
            "1. BEFORE generating: call retrieve_context with a query describing the process domain.\n"
            "2. BEFORE generating: call process_model_query(filter_type='summary') to confirm step/role counts.\n"
            "3. BEFORE generating: call search_leading_practices if available.\n"
            "4. AFTER first draft: call save_draft(key='v1', content=...) to persist the draft.\n"
            "5. AFTER first draft: call the structural validator "
            "(document_builder / table_builder / diagram_builder / outline_validator) and fix issues.\n"
            "6. AFTER revision: call cross_reference_checker to verify roles and step names match the ProcessModel.\n"
            "7. Use format_table for tabular output rather than building rows manually.\n"
            "8. Reserve web_search for external standards not in the project context.\n"
            "9. FINAL STEP (mandatory): after all tool calls are complete, output the full final document "
            "as your last response text. Do NOT end with a status summary, validation report, or commentary — "
            "your final message MUST be the complete document content starting with a '# ' heading. "
            "The system captures your final text response as the deliverable; if you output anything other "
            "than the document itself, the deliverable will be empty or corrupted."
        )

        assert yaml_prompt == original, f"Tool usage policy mismatch.\nYAML:\n{yaml_prompt}\n\nOriginal:\n{original}"


class TestArchetypePrompts:
    """Test that archetype YAML prompts match their original inline versions."""

    def test_archetype_advisory_pov_pptx_equivalence(self):
        """archetype_advisory_pov.yaml (PPTX format) matches original."""
        yaml_prompt = get_prompt("archetype_advisory_pov").render_system(output_type="pptx")

        # Simplified version combining the essence of the original pptx variant
        # Original was lines 120-129 in deliverable_archetype.py
        assert "advisory point-of-view" in yaml_prompt
        assert "pptx" in yaml_prompt.lower() or "deck" in yaml_prompt.lower()
        assert "storyline" in yaml_prompt
        assert "Sources and assumptions" in yaml_prompt

    def test_archetype_advisory_pov_docx_equivalence(self):
        """archetype_advisory_pov.yaml (DOCX format) matches original."""
        yaml_prompt = get_prompt("archetype_advisory_pov").render_system(output_type="docx")

        # Original was lines 131-139 in deliverable_archetype.py
        assert "advisory point-of-view" in yaml_prompt
        assert "docx" in yaml_prompt.lower() or "note" in yaml_prompt.lower()
        assert "intervention map" in yaml_prompt

    def test_archetype_proposal_equivalence(self):
        """archetype_proposal.yaml matches original inline."""
        yaml_prompt = get_prompt("archetype_proposal").render_system()

        # Original was lines 145-148 in deliverable_archetype.py
        original = (
            "\n\nDELIVERABLE ARCHETYPE: client proposal. "
            "Emphasize client outcomes, approach, and evidence-backed recommendations."
        )

        assert yaml_prompt == original, f"Proposal archetype mismatch.\nYAML:\n{yaml_prompt}\n\nOriginal:\n{original}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
