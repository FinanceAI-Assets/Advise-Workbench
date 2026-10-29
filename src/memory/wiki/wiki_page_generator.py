"""Wiki page generation from extracted facts through the configured model provider (Claude CLI)."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

from src.llm.claude import claude_generate_json

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You write concise, factual wiki pages for a consulting knowledge base. "
    "Use only the facts given. Answer with one JSON object only, no markdown fences and no commentary."
)

_PROMPT = """Write one wiki page for each entity below, using only its facts.

Return JSON: {{"pages": [{{"entity_name": "...", "entity_type": "...", "content": "..."}}]}}

content is Markdown (at most 200 words) with: a one or two sentence overview, then short sections
"Key points", "Related" and "Risks and metrics" where the facts support them. Keep entity_name and
entity_type exactly as given. Source document: {filename}

ENTITIES:
{entities}"""


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def group_entities(facts: list[dict[str, Any]], max_entities: int) -> list[dict[str, Any]]:
    """Group facts by (type, normalized name); keep the entities with the most and most confident facts."""
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"facts": []})
    for f in facts:
        key = (f["type"], normalize_name(f["name"]))
        g = groups[key]
        g.setdefault("entity_name", f["name"])
        g["entity_type"] = f["type"]
        g["facts"].append(f)
    ranked = sorted(
        groups.values(),
        key=lambda g: (len(g["facts"]), sum(f["confidence"] for f in g["facts"])),
        reverse=True,
    )
    return ranked[:max_entities]


def generate_wiki_pages(entities: list[dict[str, Any]], filename: str) -> list[dict[str, Any]]:
    """One model call for all entities; returns pages matched back to the requested entities."""
    if not entities:
        return []
    listing = "\n".join(
        f"- {e['entity_name']} ({e['entity_type']}):\n"
        + "\n".join(f"  * {f['name']}: {f['value'] or f['context']}" for f in e["facts"][:12])
        for e in entities
    )
    out = claude_generate_json(
        system=_SYSTEM, user=_PROMPT.format(filename=filename, entities=listing), temperature=0.2, max_tokens=8000
    )
    wanted = {(e["entity_type"], normalize_name(e["entity_name"])): e for e in entities}
    pages = []
    for p in out.get("pages", []) if isinstance(out, dict) else []:
        if not isinstance(p, dict) or not str(p.get("content", "")).strip():
            continue
        entity = wanted.get((str(p.get("entity_type", "")).lower(), normalize_name(str(p.get("entity_name", "")))))
        if entity is None:
            continue
        pages.append(
            {
                "entity_name": entity["entity_name"],
                "entity_type": entity["entity_type"],
                "content": str(p["content"]).strip(),
                "source_facts": [f["name"] for f in entity["facts"]],
            }
        )
    logger.info("[WIKI_GEN] %s: %d/%d pages generated", filename, len(pages), len(entities))
    return pages
