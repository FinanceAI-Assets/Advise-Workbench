"""Prompt registry: prompts live in ``config/prompts/<name>.yaml``, not in the code that uses them.

A prompt file has ``name``, ``version``, ``description`` and the texts ``system`` and/or ``user``.
Variables are written ``${name}``; rendering fails if one is missing, so a renamed variable is
caught at once. The name and version of every rendered prompt are put on the current trace span.

Prompt usage is tracked in a thread-local cache that can be read at run completion to record
which prompts (and their versions) were used in that run.
"""

from __future__ import annotations

import contextvars
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import yaml

from src.core.observability.otel_tracing import current_span

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "config" / "prompts"

# Context variable to track prompts used in the current run
_prompts_used_context: contextvars.ContextVar[set[tuple[str, str]]] = contextvars.ContextVar(
    "prompts_used", default=set()
)


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    description: str
    system: str
    user: str

    def _render(self, text: str, variables: dict[str, Any]) -> str:
        span = current_span()
        span.set_attribute("prompt.name", self.name)
        span.set_attribute("prompt.version", self.version)
        return Template(text).substitute({key: str(value) for key, value in variables.items()})

    def render_system(self, **variables: Any) -> str:
        return self._render(self.system, variables)

    def render_user(self, **variables: Any) -> str:
        return self._render(self.user, variables)


@lru_cache(maxsize=256)
def get_prompt(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data.get("name") != name:
        raise ValueError(f"{path}: name must be {name!r} (got {data.get('name')!r})")
    prompt = Prompt(
        name=name,
        version=str(data["version"]),
        description=str(data.get("description") or ""),
        system=str(data.get("system") or ""),
        user=str(data.get("user") or ""),
    )
    # Track that this prompt was used in the current run
    _record_prompt_used(prompt.name, prompt.version)
    return prompt


def _record_prompt_used(name: str, version: str) -> None:
    """Record that a prompt was used in the current run context."""
    try:
        used = _prompts_used_context.get()
        # Sets are not safe with contextvars in async, so we reset if needed
        if not isinstance(used, set):
            used = set()
        used.add((name, version))
        _prompts_used_context.set(used)
    except (LookupError, RuntimeError):
        # If context var not available, silently skip tracking
        pass


def get_prompts_used() -> list[dict[str, str]]:
    """Return all prompts used in the current run context as a list of {name, version} dicts.

    Returns prompts in sorted order by name for deterministic output.
    """
    try:
        used = _prompts_used_context.get()
        if not used:
            return []
        # Convert set of tuples to list of dicts, sorted by name
        return [{"name": name, "version": version} for name, version in sorted(used)]
    except (LookupError, RuntimeError):
        return []


def reset_prompts_used() -> None:
    """Clear the tracked prompts (used at start of new run)."""
    try:
        _prompts_used_context.set(set())
    except RuntimeError:
        pass


def list_prompts() -> list[Prompt]:
    return [get_prompt(path.stem) for path in sorted(PROMPTS_DIR.glob("*.yaml"))]
