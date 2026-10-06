"""What a model provider can do, so callers can degrade instead of failing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    tools: bool = True  # custom tool calling (agent tool loops)
    vision: bool = True  # image input (visual QA)
    thinking: bool = True  # extended thinking (planner)
    anthropic_tools: bool = False  # Anthropic-defined bash / text-editor tools
