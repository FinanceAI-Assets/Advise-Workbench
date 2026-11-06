"""Leading Practice library: index, LangGraph retrieval pipeline, service and the prompt registry."""

from __future__ import annotations

import json
import uuid

import numpy as np
import pytest
from sqlalchemy import delete

from src.core.cache import cache_service
from src.core.config import settings
from src.core.db.models import WorkbenchRecord
from src.core.db.session import session_scope
from src.core.storage import workspace_path
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


@pytest.fixture(autouse=True)
def _only_file_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests cover the file sources; released practices (from the shared test database) are left out."""
    monkeypatch.setattr(lp_index, "_released_passages", lambda: [])


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
    assert (workspace_path(".lp_index") / "index.json").is_file()


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


def test_practice_filter_keeps_only_passages_of_those_practices(library, monkeypatch: pytest.MonkeyPatch) -> None:
    def released() -> list[dict]:
        return [
            {"id": f"rel-{pid}", "path": f"published/{pid}", "heading": heading, "text": text, "source": "published",
             "practice_id": pid, "job_id": f"job-{pid}"}
            for pid, heading, text in (
                ("lp-001", "Invoice controls", "Match every invoice to its purchase order before payment."),
                ("lp-002", "Invoice approvals", "Route each invoice to a named approver before payment."),
            )
        ]

    monkeypatch.setattr(lp_index, "_released_passages", released)
    lp_index._index = None
    everything = lp_rag.run_lp_rag("invoice before payment", max_results=8)["results"]
    assert {r.get("practice_id") for r in everything} >= {"lp-001", "lp-002", None}
    only = lp_rag.run_lp_rag("invoice before payment", max_results=8, practice_ids=["lp-002"])["results"]
    assert [r["practice_id"] for r in only] == ["lp-002"]


def test_chosen_sources_are_answered_from_even_when_the_question_shares_no_words(
    library, monkeypatch: pytest.MonkeyPatch
) -> None:
    def released() -> list[dict]:
        return [
            {"id": f"rel-{n}", "path": f"published/{pid}", "heading": f"{pid} part {n}", "text": f"Guidance {n} of {pid}.",
             "source": "published", "practice_id": pid, "job_id": f"job-{pid}"}
            for n, pid in enumerate(["lp-001", "lp-001", "lp-001", "lp-002", "lp-003"])
        ]

    monkeypatch.setattr(lp_index, "_released_passages", released)
    monkeypatch.setattr(settings, "lp_rag_semantic_enabled", False)
    monkeypatch.setattr(lp_rag, "claude_generate", lambda **kwargs: "From the passages [1].")
    lp_index._index = None

    answered = service.answer("zzzz qqqq", max_results=3, practice_ids=["lp-001", "lp-002"])
    # Each chosen practice is represented before a second passage of any one, and nothing else gets in.
    assert [s["practice_id"] for s in answered["sources"]] == ["lp-001", "lp-002", "lp-001"]
    assert answered["answer"] == "From the passages [1]."

    # Searching is not asking about them: no match still means no results.
    assert lp_rag.run_lp_rag("zzzz qqqq", practice_ids=["lp-001"])["results"] == []
    # Without a choice of sources nothing is invented for a question that matches nothing.
    assert service.answer("zzzz qqqq")["sources"] == []
    # A chosen practice with no passages has nothing to answer from.
    assert service.answer("zzzz qqqq", practice_ids=["lp-009"])["sources"] == []


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


def test_project_scoped_search_returns_nothing_without_linked_practices(library, monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = f"p_{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(lp_index, "load_index", lambda force=False: type("Idx", (), {"fingerprint": "fp-test"})())
    called: dict[str, object] = {}

    def fake_run(query: str, *, max_results: int = 5, want_answer: bool = False, practice_ids=None):
        called["query"] = query
        called["practice_ids"] = practice_ids
        return {"results": [{"heading": "should not be returned"}]}

    monkeypatch.setattr(lp_rag, "run_lp_rag", fake_run)
    monkeypatch.setattr("src.memory.knowledge.leading_practices.run_lp_rag", fake_run)
    monkeypatch.setattr(cache_service, "get", lambda key: None)

    results = service.search("invoice controls", project_id=project_id, max_results=3)
    assert results == []
    assert called == {}


def test_project_scoped_search_uses_only_linked_practices(library, monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = f"p_{uuid.uuid4().hex[:10]}"
    with session_scope() as db:
        db.add(
            WorkbenchRecord(
                collection="engagement_practices",
                record_id=f"{project_id}:lp-002",
                project_id=project_id,
                payload_json=json.dumps({"practiceId": "lp-002", "title": "Invoice approvals"}),
            )
        )
    monkeypatch.setattr(lp_index, "load_index", lambda force=False: type("Idx", (), {"fingerprint": "fp-test"})())
    call: dict[str, object] = {}

    def fake_run(query: str, *, max_results: int = 5, want_answer: bool = False, practice_ids=None):
        call["query"] = query
        call["max_results"] = max_results
        call["practice_ids"] = practice_ids
        return {"results": [{"heading": "Invoice approvals", "practice_id": "lp-002"}]}

    monkeypatch.setattr(lp_rag, "run_lp_rag", fake_run)
    monkeypatch.setattr("src.memory.knowledge.leading_practices.run_lp_rag", fake_run)
    monkeypatch.setattr(cache_service, "get", lambda key: None)

    try:
        results = service.search("invoice controls", project_id=project_id, max_results=4)
        assert [r["practice_id"] for r in results] == ["lp-002"]
        assert call["practice_ids"] == ["lp-002"]
    finally:
        with session_scope() as db:
            db.execute(
                delete(WorkbenchRecord).where(
                    WorkbenchRecord.collection == "engagement_practices",
                    WorkbenchRecord.project_id == project_id,
                )
            )
