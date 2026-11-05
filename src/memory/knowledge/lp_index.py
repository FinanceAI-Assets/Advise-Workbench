"""Leading Practice library index: the library's files cut into passages, searchable by keyword and by meaning.

Sources:
- the folder named by ``LP_LIBRARY_LOCAL_PATH`` (``.md`` and ``.txt`` files, any depth);
- the shared leading-practice wiki pages under ``<workspace>/leading_practices/wiki``.

The passages are kept in ``<workspace>/.lp_index/index.json`` and their embeddings next to it.
Both are rebuilt when a source file is added, changed or removed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.memory.retrieval import TieredContextEngine, _BM25Index, _build_bm25_index

_LOG = logging.getLogger(__name__)

CHUNK_CHARS = 1200  # target passage length
RESCAN_SEC = 30  # how often the source folders are checked for changes
MIN_SIMILARITY = 0.3  # embedding matches below this are not counted as relevant
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_LOCK = threading.Lock()
_bm25 = TieredContextEngine()._bm25_scores


@dataclass
class LPIndex:
    fingerprint: str
    chunks: list[dict[str, Any]]
    bm25: _BM25Index
    embeddings: Any = None  # numpy array, one normalised row per chunk; computed on first semantic search


_index: LPIndex | None = None
_checked_at = 0.0


def _index_dir() -> Path:
    return Path(settings.workspace_root) / ".lp_index"


def _source_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    library = Path(settings.lp_library_local_path) if settings.lp_library_local_path else None
    if library and library.is_dir():
        files += [("library", p) for p in sorted(library.rglob("*")) if p.is_file() and p.suffix.lower() in {".md", ".txt"}]
    wiki = Path(settings.workspace_root) / "leading_practices" / "wiki"
    if wiki.is_dir():
        files += [("wiki", p) for p in sorted(wiki.rglob("*.md")) if ".meta" not in p.parts]
    return files


def _fingerprint(files: list[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    for _, path in files:
        stat = path.stat()
        digest.update(f"{path}|{stat.st_mtime_ns}|{stat.st_size}\n".encode())
    return digest.hexdigest()[:16]


def _chunk_file(source: str, path: Path) -> list[dict[str, Any]]:
    """Cut one file into passages: by heading, then by paragraph until a passage is about CHUNK_CHARS long."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks: list[dict[str, Any]] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        body = "\n\n".join(buffer).strip()
        buffer.clear()
        if not body:
            return
        chunk_id = hashlib.sha256(f"{path}|{len(chunks)}".encode()).hexdigest()[:16]
        chunks.append({"id": chunk_id, "path": str(path), "heading": heading[:120], "text": body, "source": source})

    for paragraph in re.split(r"\n\s*\n", text):
        lines = paragraph.strip().splitlines()
        if not lines:
            continue
        match = _HEADING_RE.match(lines[0])
        if match:
            flush()
            heading = match.group(1).strip()
            lines = lines[1:]
            if not lines:
                continue
        buffer.append("\n".join(lines))
        if sum(len(part) for part in buffer) >= CHUNK_CHARS:
            flush()
    flush()
    return chunks


def _search_text(chunk: dict[str, Any]) -> str:
    return f"{chunk['heading']}\n{chunk['text']}"


def load_index(*, force: bool = False) -> LPIndex:
    """The current index. The source folders are re-checked at most every RESCAN_SEC seconds."""
    global _index, _checked_at
    with _LOCK:
        if _index is not None and not force and time.time() - _checked_at < RESCAN_SEC:
            return _index
        files = _source_files()
        fingerprint = _fingerprint(files)
        _checked_at = time.time()
        if _index is not None and _index.fingerprint == fingerprint and not force:
            return _index
        chunks: list[dict[str, Any]] = []
        for source, path in files:
            try:
                chunks += _chunk_file(source, path)
            except OSError as exc:
                _LOG.warning("leading practice library: could not read %s: %s", path, exc)
        _index_dir().mkdir(parents=True, exist_ok=True)
        (_index_dir() / "index.json").write_text(json.dumps({"fingerprint": fingerprint, "items": chunks}, indent=2), encoding="utf-8")
        _index = LPIndex(fingerprint=fingerprint, chunks=chunks, bm25=_build_bm25_index([_search_text(c) for c in chunks]))
        _LOG.info("leading practice library: indexed %d passages from %d files", len(chunks), len(files))
        return _index


def keyword_search(index: LPIndex, query: str, top_k: int) -> list[tuple[int, float]]:
    """(chunk position, BM25 score) for the best keyword matches, best first."""
    scores = _bm25(index.bm25, query)
    ranked = sorted(((i, s) for i, s in enumerate(scores) if s > 0), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_k]


def _embed(texts: list[str]) -> Any:
    """Normalised embeddings, one row per text. The model is shared with the wiki search."""
    from sentence_transformers import SentenceTransformer

    from src.memory.knowledge import wiki_query

    if wiki_query._embed_model is None:
        wiki_query._embed_model = SentenceTransformer(EMBEDDING_MODEL)
    return wiki_query._embed_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True).astype("float32")


def _chunk_embeddings(index: LPIndex) -> Any:
    import numpy as np

    with _LOCK:
        if index.embeddings is not None:
            return index.embeddings
        vectors_path = _index_dir() / "embeddings.npy"
        meta_path = _index_dir() / "embeddings.json"
        try:
            if json.loads(meta_path.read_text(encoding="utf-8")) == {"fingerprint": index.fingerprint, "model": EMBEDDING_MODEL}:
                index.embeddings = np.load(vectors_path)
                return index.embeddings
        except (OSError, ValueError):
            pass
        index.embeddings = _embed([_search_text(c) for c in index.chunks])
        np.save(vectors_path, index.embeddings)
        meta_path.write_text(json.dumps({"fingerprint": index.fingerprint, "model": EMBEDDING_MODEL}), encoding="utf-8")
        return index.embeddings


def semantic_search(index: LPIndex, query: str, top_k: int) -> list[tuple[int, float]]:
    """(chunk position, cosine similarity) for the passages closest in meaning, best first."""
    similarities = _chunk_embeddings(index) @ _embed([query])[0]
    ranked = sorted(((int(i), float(s)) for i, s in enumerate(similarities) if s >= MIN_SIMILARITY), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_k]
