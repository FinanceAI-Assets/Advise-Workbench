"""retrieve_context must find text in uploaded documents, whose chunks are stored as records."""

from __future__ import annotations

import json

import pytest

from src.tools import registry


@pytest.fixture
def parsed_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    folder = tmp_path / "p_chunks" / "parsed_docs"
    folder.mkdir(parents=True)
    (folder / "a.json").write_text(
        json.dumps(
            {
                "filename": "05_baseline_metrics_memo.md",
                "text": "...",
                "chunks": [
                    {"text": "Invoice match exceptions cost Northwind 2.1M a year.", "filename": "05_baseline_metrics_memo.md", "page": 1},
                    {"text": "", "filename": "05_baseline_metrics_memo.md", "page": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    (folder / "b.json").write_text(json.dumps({"chunks": ["Older file: three-way match in SAP."]}), encoding="utf-8")
    monkeypatch.setattr(registry, "workspace_path", lambda pid: tmp_path / pid)
    monkeypatch.setattr(registry, "_get_embed_model", lambda: None)  # keyword search path
    return folder


def test_record_and_plain_chunks_are_both_searched(parsed_dir) -> None:
    found = registry.retrieve_context(query="Northwind invoice match exceptions", project_id="p_chunks")
    texts = [c["text"] for c in found["chunks"]]
    assert "Invoice match exceptions cost Northwind 2.1M a year." in texts
    assert "Older file: three-way match in SAP." in texts
    assert found["chunks"][0]["source"] == "05_baseline_metrics_memo.md (page 1)"
    assert "2.1M" in found["context_text"]


def test_chunks_are_loaded_for_the_semantic_index(parsed_dir) -> None:
    chunks, sources = registry._load_chunks(parsed_dir)
    assert chunks == ["Invoice match exceptions cost Northwind 2.1M a year.", "Older file: three-way match in SAP."]
    assert sources[0] == "05_baseline_metrics_memo.md (page 1)"
