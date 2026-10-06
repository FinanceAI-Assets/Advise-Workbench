"""Prompt registry: prompts live in ``config/prompts/<name>.yaml``, not in the code that uses them.

A prompt file has ``name``, ``version``, ``description`` and the texts ``system`` and/or ``user``.
Variables are written ``${name}``; rendering fails if one is missing, so a renamed variable is
caught at once. The name and version of every rendered prompt are put on the current trace span.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import yaml

from src.core.observability.otel_tracing import current_span

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "config" / "prompts"


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
    return Prompt(
        name=name,
        version=str(data["version"]),
        description=str(data.get("description") or ""),
        system=str(data.get("system") or ""),
        user=str(data.get("user") or ""),
    )


def list_prompts() -> list[Prompt]:
    return [get_prompt(path.stem) for path in sorted(PROMPTS_DIR.glob("*.yaml"))]
