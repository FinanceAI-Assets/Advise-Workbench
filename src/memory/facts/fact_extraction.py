"""Fact extraction from document text through the configured model provider (Claude CLI with LLM_PROVIDER=claude_cli)."""

from __future__ import annotations

import logging
from typing import Any

from src.llm.claude import claude_generate_json

logger = logging.getLogger(__name__)

FACT_TYPES = ("role", "activity", "risk", "metric", "dependency", "system")

_SYSTEM = (
    "You extract structured facts from business documents for a consulting knowledge base. "
    "Answer with one JSON object only, no markdown and no commentary."
)

_PROMPT = """Extract the important facts from the document excerpt below.

Return JSON: {{"facts": [{{"type": "...", "name": "...", "value": "...", "confidence": 0.0, "context": "..."}}]}}

- type: one of role, activity, risk, metric, dependency, system
  (role = a person, team or job; activity = a process step or task; risk = a risk, issue or pain point;
  metric = a number, KPI or target; dependency = something a process relies on; system = software or tool)
- name: short canonical name (2-6 words), e.g. "Accounts Payable Clerk", "Three-way match"
- value: one sentence with the specific detail from the text
- confidence: 0.0-1.0, how clearly the text states it
- context: up to 20 words quoted or paraphrased from the text

Only facts stated in the text. At most 25 facts. If there are none, return {{"facts": []}}.

Document: {filename}

EXCERPT:
{text}"""


def _clean(fact: Any) -> dict[str, Any] | None:
    if not isinstance(fact, dict):
        return None
    ftype = str(fact.get("type", "")).strip().lower()
    name = str(fact.get("name", "")).strip()
    if ftype not in FACT_TYPES or not name:
        return None
    try:
        confidence = min(1.0, max(0.0, float(fact.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    return {
        "type": ftype,
        "name": name[:255],
        "value": str(fact.get("value", "")).strip(),
        "confidence": confidence,
        "context": str(fact.get("context", "")).strip()[:500],
    }


def extract_facts(text: str, filename: str) -> list[dict[str, Any]]:
    """One model call; returns validated facts (malformed items are dropped)."""
    out = claude_generate_json(system=_SYSTEM, user=_PROMPT.format(filename=filename, text=text), temperature=0.0)
    raw = out.get("facts", []) if isinstance(out, dict) else []
    facts = [f for f in (_clean(x) for x in raw) if f]
    logger.info("[FACTS] %s: %d facts from %d chars", filename, len(facts), len(text))
    return facts


def batch_texts(texts: list[str], max_chars: int, max_batches: int) -> list[str]:
    """Join chunk texts into at most ``max_batches`` batches of about ``max_chars`` characters."""
    batches: list[str] = []
    current = ""
    for text in texts:
        if current and len(current) + len(text) > max_chars:
            batches.append(current)
            if len(batches) >= max_batches:
                return batches
            current = ""
        current = f"{current}\n\n{text}" if current else text
    if current and len(batches) < max_batches:
        batches.append(current)
    return batches
