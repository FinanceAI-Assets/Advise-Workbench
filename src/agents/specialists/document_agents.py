"""Document agents, one module per agent. This module re-exports them so existing imports keep working.

Tests that replace a model call must patch it on ``_shared`` (see that module's docstring).
"""

from __future__ import annotations

from src.agents.specialists._shared import (  # noqa: F401
    _SWARM_READ_TOOLS,
    _SWARM_LEAD_ONLY_TOOLS,
    _SWARM_TOOL_NAMES,
    _DEBUG_LOG_PATH,
    _DEBUG_SESSION_ID,
    _append_conversation_digest_block,
    _session_debug_log,
    _model,
    _pref,
    _skill_instruction,
    _primary_skill,
    _FREEDOM_TEMPERATURE,
    _render_zoned_system_prompt,
    _SkillBuild,
    _append_archetype_prompt,
    _build_system_from_skill,
    _recover_latest_draft,
    _run_subagent_tool_loop_text,
    _apply_quality_gate,
    _run_post_processor,
    _run_pptx_post_processor,
    _TOOL_USAGE_POLICY,
    _deliverable_type_for_skill,
    _grounded_context_excerpt,
    _resolve_arc_key,
    _process_summary_for_storyline,
    _storyline_spine_block,
)
from src.agents.specialists.extraction_agent import (  # noqa: F401
    run_process_extraction,
)
from src.agents.specialists.raci_agent import (  # noqa: F401
    _raci_deterministic_updates,
    run_raci_agent,
)
from src.agents.specialists.sop_agent import (  # noqa: F401
    run_sop_agent,
)
from src.agents.specialists.narrative_agent import (  # noqa: F401
    run_narrative_agent,
)
from src.agents.specialists.process_map_agent import (  # noqa: F401
    _normalize_drawio_xml,
    _drawio_context_hints,
    run_drawio_agent,
)
from src.agents.specialists.xlsx_agent import (  # noqa: F401
    _financial_assumptions_from_context,
    run_xlsx_agent,
)
from src.agents.specialists.pdf_agent import (  # noqa: F401
    run_pdf_agent,
)
from src.agents.specialists.docx_agent import (  # noqa: F401
    run_docx_agent,
    _guard_docx_representation,
    _docx_deterministic_fallback,
)
from src.agents.specialists.pptx_agent import (  # noqa: F401
    _matching_context_lines,
    _shared_user_context_appendix,
    _pptx_deterministic_slides,
    _CHAT_MARKERS,
    _CONVERSATIONAL_PREFIXES,
    _CONVERSATIONAL_VERBS,
    _looks_like_chat_line,
    _normalise_industry,
    _title_from_discovery,
    _title_from_outline,
    _resolve_presentation_title,
    run_pptx_agent,
)

# Repair and batching helpers that tests import from here.
from src.agents.repair.docx_critique_repair import (  # noqa: F401
    _critique_and_repair_docx,
    _section_hint_indices,
    _targeted_section_rewrite,
)
from src.agents.repair.pptx_critique_repair import (  # noqa: F401
    _EVIDENCE_SOFT_BLOCK_DIRECTIVE,
    _critique_and_repair_pptx,
    _critique_slides,
    _evidence_remediation_directive,
    _merge_pptx_slides_repair,
    _normalize_pptx_slide_identities,
    _pptx_visual_feedback_indices,
    _targeted_slide_rewrite,
)
from src.agents.specialists.pptx_slide_batching import (  # noqa: F401
    _generate_slides_batched,
    _strip_title_override,
)
