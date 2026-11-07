"""Pre-render content guard for PPTX slide blueprints.

Removes placeholder text ("TBD", "No steps extracted", "0 workflow steps"...) and
leaked internal headings ("ObjectiveNow"...) so they never reach a client deck.
Slides left with no substantive content are dropped, except title and
section_divider slides. Pure function, never raises, returns a report.
"""
from __future__ import annotations

import re
from typing import Any

_LEAK_HEADINGS = ("ObjectiveNow", "NonNegotiables", "WhatChanged", "KnownFailures")
_LEAK_RE = re.compile(r"(?:#+\s*)?\b(?:%s)\b:?" % "|".join(_LEAK_HEADINGS))

_PLACEHOLDER_RE = re.compile(
    r"^\s*(?:tbd|tbc|todo|n/?a|none|null|lorem.*|\[(?:tbd|tbc|todo)\]|click to add.*|"
    r"no steps extracted.*|not available|to be defined|to define|"
    r"0 (?:workflow )?(?:steps|roles|systems))\s*\.?\s*$",
    re.IGNORECASE,
)
_PLACEHOLDER_INLINE_RE = re.compile(r"\[(?:tbd|tbc|todo)\]|lorem ipsum", re.IGNORECASE)

# Keys whose text is structural, not display copy.
_SKIP_KEYS = {"slide_id", "slide_type", "slide_index", "card_id", "layer_id", "fill", "accent", "icon", "kind", "pos", "type"}
_KEEP_TYPES = {"title", "section_divider"}
_NON_CONTENT_KEYS = {
    "title", "subtitle", "slide_type", "slide_id", "slide_index", "layout", "footer_note",
    "speaker_notes", "notes", "source_refs", "badges", "sources", "section",
}


def strip_leaks(text: str) -> str:
    out = _LEAK_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", out).strip(" -–—:|")


def is_placeholder(text: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(text or ""))


def _clean(value: Any, report: list[str], path: str) -> Any:
    if isinstance(value, str):
        cleaned = strip_leaks(value) if _LEAK_RE.search(value) else value
        if cleaned != value:
            report.append(f"{path}: removed internal heading")
        if is_placeholder(cleaned):
            report.append(f"{path}: removed placeholder '{cleaned[:30]}'")
            return None
        if _PLACEHOLDER_INLINE_RE.search(cleaned):
            cleaned = _PLACEHOLDER_INLINE_RE.sub("", cleaned).strip()
            report.append(f"{path}: stripped inline placeholder")
        return cleaned
    if isinstance(value, list):
        if value and all(isinstance(v, list) for v in value):
            # table rows / cell grids: keep column positions, blank out placeholders
            grid = []
            for ri, row in enumerate(value):
                cells = []
                for ci, cell in enumerate(row):
                    c = _clean(cell, report, f"{path}[{ri}][{ci}]")
                    cells.append("" if c is None else c)
                if any(str(c).strip() for c in cells):
                    grid.append(cells)
            return grid
        items = [_clean(v, report, f"{path}[{i}]") for i, v in enumerate(value)]
        return [v for v in items if v not in (None, "", [], {})]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in _SKIP_KEYS:
                out[k] = v
                continue
            c = _clean(v, report, f"{path}.{k}")
            if c not in (None, "", [], {}):
                out[k] = c
        return out
    return value


def _has_content(slide: dict[str, Any]) -> bool:
    return any(k not in _NON_CONTENT_KEYS and v not in (None, "", [], {}) for k, v in slide.items())


def sanitize_slides(slides: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (clean_slides, report). Never raises; on error returns input unchanged."""
    report: list[str] = []
    try:
        result: list[dict[str, Any]] = []
        for i, slide in enumerate(slides or []):
            if not isinstance(slide, dict):
                continue
            stype = str(slide.get("slide_type") or "").lower()
            cleaned = _clean(slide, report, f"slide{i + 1}")
            if not isinstance(cleaned, dict):
                continue
            if not cleaned.get("title"):
                cleaned["title"] = slide.get("title") if stype in _KEEP_TYPES else ""
            if stype in _KEEP_TYPES or _has_content(cleaned):
                if cleaned.get("title") or stype in _KEEP_TYPES:
                    result.append(cleaned)
                    continue
            report.append(f"slide{i + 1}: dropped (no substantive content)")
        return result, report
    except Exception:  # noqa: BLE001 — guard must never break rendering
        return list(slides or []), ["content_guard failed; slides unchanged"]
