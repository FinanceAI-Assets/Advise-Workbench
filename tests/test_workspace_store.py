import os

import pytest

from src.core.workspace_store import DbS3Store, FsStore, _clean_rel


def test_fs_round_trip(tmp_path):
    store = FsStore(root=str(tmp_path))
    store.write_bytes("p1", "source_docs/a.md", b"hello")
    assert store.read_bytes("p1", "source_docs/a.md") == b"hello"
    assert store.exists("p1", "source_docs/a.md")
    assert store.list_files("p1") == ["source_docs/a.md"]
    store.delete("p1", "source_docs/a.md")
    assert store.read_bytes("p1", "source_docs/a.md") is None


def test_fs_missing_returns_none(tmp_path):
    store = FsStore(root=str(tmp_path))
    assert store.read_bytes("nope", "x.md") is None
    assert store.list_files("nope") == []


@pytest.mark.parametrize("bad", ["../secret.txt", "/etc/passwd", "a/../../b", ""])
def test_rejects_paths_outside_project(bad):
    with pytest.raises(ValueError):
        _clean_rel(bad)


@pytest.mark.skipif(os.getenv("AW_STORE_INTEGRATION") != "1",
                    reason="writes to the shared Postgres and S3; set AW_STORE_INTEGRATION=1 to run")
def test_db_s3_round_trip():
    from src.core.config import settings

    store = DbS3Store()
    project = "_store_test"
    try:
        store.write_bytes(project, "notes/t.md", "héllo".encode("utf-8"))
        store.write_bytes(project, "runs/out.xlsx", b"\x00\x01binary")
        assert store.read_bytes(project, "notes/t.md") == "héllo".encode("utf-8")
        assert store.read_bytes(project, "runs/out.xlsx") == b"\x00\x01binary"
        assert sorted(store.list_files(project)) == ["notes/t.md", "runs/out.xlsx"]
    finally:
        for rel in ("notes/t.md", "runs/out.xlsx"):
            store.delete(project, rel)
        assert store.list_files(project) == []
    assert settings.s3_bucket
