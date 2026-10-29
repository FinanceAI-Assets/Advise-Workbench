"""Wiki deduplication: match new wiki drafts to existing project pages (or to each other) by name and embedding."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Candidate:
    key: str  # wiki_pages_final.id for existing pages, draft id for new ones
    entity_type: str
    normalized_name: str
    vector: list[float]


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb / denom) if denom else 0.0


def assign_drafts(
    drafts: list[Candidate], existing: list[Candidate], threshold: float
) -> list[tuple[str, str | None]]:
    """For each draft (in order) return ("existing", page_id), ("draft", earlier_draft_id) or ("new", None).

    Same type + same normalized name is always a match; otherwise the most similar page at or above
    ``threshold`` cosine similarity wins. Existing pages are preferred over drafts of this batch.
    """
    accepted: list[Candidate] = []
    result: list[tuple[str, str | None]] = []
    for draft in drafts:
        match = _best(draft, existing, threshold)
        if match:
            result.append(("existing", match))
            continue
        match = _best(draft, accepted, threshold)
        if match:
            result.append(("draft", match))
            continue
        accepted.append(draft)
        result.append(("new", None))
    return result


def _best(draft: Candidate, pool: list[Candidate], threshold: float) -> str | None:
    for c in pool:
        if c.entity_type == draft.entity_type and c.normalized_name == draft.normalized_name:
            return c.key
    scored = [(_cosine(draft.vector, c.vector), c.key) for c in pool if c.vector]
    if not scored:
        return None
    score, key = max(scored)
    return key if score >= threshold else None
