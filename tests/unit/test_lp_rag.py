"""Leading Practice library: index, LangGraph retrieval pipeline, service and the prompt registry."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.cache import cache_service
from src.core.config import settings
from src.memory.knowledge import lp_index, lp_rag
from src.memory.knowledge.leading_practices import leading_practice_library_service as service
from src.prompts.registry import get_prompt, list_prompts

P2P = """# Procure to pay

Intro paragraph about procurement.

## Three-way match

Match the purchase order, goods receipt and invoice before payment. Automate the match and route
exceptions to a named owner within two days.

## Supplier onboarding

Collect tax and bank details through a portal and verify bank accounts independently.
"""
R2R = """# Record to report

## Close calendar

Publish a close calendar with owners and deadlines. Leading teams close the books in five working days.
"""

_CONCEPTS = ["invoice", "close", "supplier"]


def _fake_embed(texts: list[str]) -> np.ndarray:
    """One dimension per concept, so 'meaning' is predictable without loading the real model."""
    synonyms = {"invoice": ["invoice", "bill", "payment"], "close": ["close", "month-end", "books"], "supplier": ["supplier", "vendor"]}
    rows = []
    for text in texts:
        row = np.array([float(any(word in text.lower() for word in synonyms[c])) for c in _CONCEPTS], dtype="float32")
        rows.append(row / (np.linalg.norm(row) or 1.0))
    return np.stack(rows)


@pytest.fixture
def library(tmp_path, monkeypatch: pytest.MonkeyPatch):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "p2p.md").write_text(P2P, encoding="utf-8")
    (folder / "r2r.md").write_text(R2R, encoding="utf-8")
    monkeypatch.setattr(settings, "lp_library_local_path", str(folder))
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspace"))
    monkeypatch.setattr(lp_index, "_embed", _fake_embed)
    monkeypatch.setattr(settings, "lp_rag_semantic_enabled", True)
    monkeypatch.setattr(lp_index, "_index", None)
    monkeypatch.setattr(cache_service, "get", lambda key: None)
    yield folder
    lp_index._index = None


def test_files_are_cut_into_passages_by_heading(library) -> None:
    index = lp_index.load_index()
    assert [c["heading"] for c in index.chunks] == ["Procure to pay", "Three-way match", "Supplier onboarding", "Close calendar"]
    assert all(c["source"] == "library" and len(c["id"]) == 16 for c in index.chunks)
    assert (library.parent / "workspace" / ".lp_index" / "index.json").is_file()


def test_keyword_search_finds_the_matching_passage(library, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lp_rag_semantic_enabled", False)
    results = service.search("three-way match purchase order", max_results=2)
    assert results[0]["heading"] == "Three-way match"
    assert results[0]["relevance_score"] == 1.0
    assert set(results[0]) == {"id", "path", "heading", "text", "source", "relevance_score"}


def test_semantic_search_finds_a_passage_that_shares_no_words(library) -> None:
    results = service.search("month-end timetable", max_results=3)
    assert [r["heading"] for r in results] == ["Close calendar"]


def test_a_passage_found_by_both_searches_ranks_first(library) -> None:
    final = lp_rag.run_lp_rag("vendor onboarding bank details", max_results=5)
    assert final["results"][0]["heading"] == "Supplier onboarding"
    assert final["keyword_hits"] and final["semantic_hits"]


def test_a_whole_document_as_the_query_is_shortened(library) -> None:
    long_query = " ".join(f"filler{n}" for n in range(200)) + " invoice" * 50
    final = lp_rag.run_lp_rag(long_query, max_results=1)
    assert len(final["search_text"].split()) == lp_rag.MAX_QUERY_TERMS
    assert final["results"][0]["heading"] == "Three-way match"


def test_index_is_rebuilt_when_a_file_changes(library) -> None:
    assert service.search("cash forecasting") == []
    (library / "treasury.md").write_text("# Treasury\n\nRolling thirteen-week cash forecasting.\n", encoding="utf-8")
    service.ensure_index(force=True)
    assert service.search("cash forecasting")[0]["heading"] == "Treasury"


def test_empty_library_returns_nothing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lp_library_local_path", "")
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(lp_index, "_index", None)
    monkeypatch.setattr(cache_service, "get", lambda key: None)
    assert service.search("anything") == []
    assert service.answer("anything") == {"answer": "The Leading Practice library is empty.", "sources": []}
    lp_index._index = None


def test_answer_is_written_from_the_passages_with_the_registry_prompt(library, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, str] = {}

    def fake_generate(*, system: str, user: str, **_: object) -> str:
        sent.update(system=system, user=user)
        return " Match PO, receipt and invoice first [1]. "

    monkeypatch.setattr(lp_rag, "claude_generate", fake_generate)
    out = service.answer("How should invoices be checked before payment?", max_results=2)
    assert out["answer"] == "Match PO, receipt and invoice first [1]."
    assert out["sources"][0]["heading"] == "Three-way match"
    assert "Question: How should invoices be checked before payment?" in sent["user"]
    assert "[1] Three-way match" in sent["user"]
    assert sent["system"] == get_prompt("lp_rag_answer").system


def test_prompt_registry_files_are_valid() -> None:
    prompts = list_prompts()
    assert "lp_rag_answer" in [p.name for p in prompts]
    assert all(p.version and (p.system or p.user) for p in prompts)
    with pytest.raises(KeyError):
        get_prompt("lp_rag_answer").render_user(question="only one variable")
