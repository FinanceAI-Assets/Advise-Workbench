"""What a model provider can do, so callers can degrade instead of failing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    tools: bool = True  # custom tool calling (agent tool loops)
    vision: bool = True  # image input (visual QA)
    thinking: bool = True  # extended thinking (planner)
    anthropic_tools: bool = False  # Anthropic-defined bash / text-editor tools
    # The provider runs the tool loop itself (``run_tool_session``) instead of returning tool_use blocks
    # for the caller to execute. The Claude CLI does this: it calls the app's tools over a loopback MCP server.
    delegated_tools: bool = False
