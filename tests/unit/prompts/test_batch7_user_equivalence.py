"""
Equivalence tests: verify that externalized user prompts (YAML) match original hardcoded versions.
"""
from src.prompts.registry import get_prompt


class TestExtractionProcessUserEquivalence:
    """Extraction agent user prompt equivalence."""

    def test_extraction_process_user_core_structure(self):
        """Verify extraction_process_user YAML contains the key schema definitions."""
        prompt = get_prompt("extraction_process_user")
        user = prompt.user

        assert "ProcessStep schema:" in user
        assert "DecisionBranch schema:" in user
        assert "MetricFact schema:" in user
        assert "Edge-case rules:" in user
        assert "process_name   string —" in user
        assert "roles          string[]" in user


class TestDocxPromptEquivalence:
    """DOCX agent user prompts equivalence."""

    def test_docx_sop_user_contains_structure(self):
        prompt = get_prompt("docx_sop_user")
        user = prompt.user
        assert "## Purpose" in user
        assert "## Scope" in user
        assert "## Roles" in user
        assert "## Procedure" in user
        assert "## Decision Points" in user
        assert "## References" in user

    def test_docx_narrative_user_contains_structure(self):
        prompt = get_prompt("docx_narrative_user")
        user = prompt.user
        assert "## What This Process Does" in user
        assert "## Key Activities" in user
        assert "## Roles and Accountability" in user
        assert "## Recommended Next Actions" in user

    def test_docx_raci_user_contains_structure(self):
        prompt = get_prompt("docx_raci_user")
        user = prompt.user
        assert "## Assignment Rules" in user
        assert "## RACI Table" in user
        assert "Activity | Responsible | Accountable | Consulted | Informed" in user

    def test_docx_brd_user_contains_structure(self):
        prompt = get_prompt("docx_brd_user")
        user = prompt.user
        assert "## Executive Summary" in user
        assert "## Current State" in user
        assert "## Business Requirements" in user

    def test_docx_generic_user_contains_structure(self):
        prompt = get_prompt("docx_generic_user")
        user = prompt.user
        assert "## Purpose" in user
        assert "## Scope" in user
        assert "## Procedure" in user

    def test_docx_proposal_user_has_template_variables(self):
        prompt = get_prompt("docx_proposal_user")
        user = prompt.user
        assert "${sections}" in user
        assert "${constraints}" in user


class TestPdfPromptEquivalence:
    """PDF agent user prompts equivalence."""

    def test_pdf_narrative_user_contains_structure(self):
        prompt = get_prompt("pdf_narrative_user")
        user = prompt.user
        assert "## What This Process Does" in user
        assert "## Key Activities" in user

    def test_pdf_sop_user_contains_structure(self):
        prompt = get_prompt("pdf_sop_user")
        user = prompt.user
        assert "## Purpose" in user
        assert "## Procedure" in user

    def test_pdf_generic_user_contains_structure(self):
        prompt = get_prompt("pdf_generic_user")
        user = prompt.user
        assert "## Executive Summary" in user
        assert "## Workflow Overview" in user
        assert "## Operational Considerations" in user


class TestXlsxPromptEquivalence:
    """XLSX agent user prompts equivalence."""

    def test_xlsx_raci_user_contains_structure(self):
        prompt = get_prompt("xlsx_raci_user")
        user = prompt.user
        assert "Activity" in user
        assert "Responsible" in user
        assert "Accountable" in user
        assert "Consulted" in user
        assert "Informed" in user

    def test_xlsx_generic_user_contains_structure(self):
        prompt = get_prompt("xlsx_generic_user")
        user = prompt.user
        assert "Activity" in user
        assert "Owner" in user
        assert "Inputs" in user
        assert "Outputs" in user


class TestLegacyAgentPromptEquivalence:
    """Legacy specialist agent user prompts equivalence."""

    def test_sop_user_contains_structure(self):
        prompt = get_prompt("sop_user")
        user = prompt.user
        assert "## Purpose" in user
        assert "## Scope" in user
        assert "## Roles" in user
        assert "## Procedure" in user
        assert "## Decision Points" in user

    def test_raci_user_contains_rules(self):
        prompt = get_prompt("raci_user")
        user = prompt.user
        assert "Responsible (R):" in user
        assert "Accountable (A):" in user
        assert "Consulted (C):" in user
        assert "Informed (I):" in user


class TestStorylinePromptEquivalence:
    """Storyline builder user prompts equivalence."""

    def test_storyline_arc_recommender_user_has_structure(self):
        prompt = get_prompt("storyline_arc_recommender_user")
        user = prompt.user
        assert "${client_name}" in user
        assert "${primary_outcome}" in user
        assert "${win_themes}" in user
        assert "${arc_descriptions}" in user

    def test_storyline_spine_builder_user_has_structure(self):
        prompt = get_prompt("storyline_spine_builder_user")
        user = prompt.user
        assert "${client_name}" in user
        assert "${primary_outcome}" in user
        assert "${audience}" in user
        assert "${target_slides}" in user
