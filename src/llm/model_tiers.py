"""Model-tier resolution for the Deloitte-quality program (Pillar A).

Planning and critique passes use stronger models; bulk slide/section drafting
stays on the configured default model (haiku). Routing is gated by
``settings.model_tiering_enabled`` so a single flag reverts to flat routing.
"""
from __future__ import annotations

from src.core.config import settings
from src.llm import gateway


def planning_model() -> str:
    """Model for narrative-spine / outline planning. Falls back to the default."""
    # gateway imported at module level (line ~10)
    return gateway.model_for("planning" if getattr(settings, "model_tiering_enabled", True) else "default")


def critique_model() -> str:
    """Model for design-review / critique passes. Falls back to the default."""
    # gateway imported at module level (line ~10)
    return gateway.model_for("critique" if getattr(settings, "model_tiering_enabled", True) else "default")
