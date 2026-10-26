"""Query pipeline: the one path every question takes to find supporting content.

1. Understanding: follow-up questions are rewritten into a standalone question (one small model call, only
   when there is history and the question needs it); expansion adds a keyword variant (no model call);
   all variants are embedded in one batch.
2. Retrieval: vector search over the project's chunks and wiki pages, verification against Postgres (only
   current, existing content; full text from the source of truth), reranking (vector score + keyword overlap,
   near-duplicates dropped).
3. Answer: sources packed into a character budget, one model call that must cite [S#], citations mapped
   back to files and pages.
4. Errors: no supporting content -> "insufficient evidence" without calling the model; a failing model ->
   the retrieved sources are returned with status "llm_unavailable".
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.db.models import ChunkArchive, DocumentFile, DocumentJob, WikiPageFinal
from src.core.embeddings.embedding_service import get_embedding_service
from src.core.vector_db.qdrant_client import get_qdrant_client
from src.llm.claude import claude_generate

logger = logging.getLogger(__name__)

INSUFFICIENT = "insufficient_evidence"
_INSUFFICIENT_TEXT = "Insufficient evidence: the project's documents do not contain information that answers this question."

_STOPWORDS = set(
    "a an and are as at be by can could did do does for from had has have how i if in is it its me my of on or our "
    "please should so tell than that the their them then there these they this to us was we were what when where "
    "which who why will with would you your about into over under any all more most some such only also just".split()
)
_FOLLOW_UP = re.compile(
    r"^(and|but|also|so|what about|how about|why|then)\b|\b(it|its|they|them|their|this|that|these|those|he|she|"
    r"his|her|same|above|previous|earlier|more)\b",
    re.I,
)
_CITATION = re.compile(r"\[S(\d+)\]")


@dataclass
class Source:
    kind: str  # chunk | wiki
    key: str  # chunk_archive.id or wiki_pages_final.id
    score: float
    text: str = ""
    filename: str | None = None
    page_number: int | None = None
    chunk_number: int | None = None
    title: str | None = None
    rank_score: float = 0.0

    def label(self) -> str:
        if self.kind == "wiki":
            return f"Wiki: {self.title}"
        page = f", page {self.page_number}" if self.page_number else ""
        return f"{self.filename}{page}"


@dataclass
class QueryResult:
    status: str  # answered | insufficient_evidence | llm_unavailable
    answer: str
    standalone_question: str
    queries: list[str]
    citations: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    model_calls: int = 0
    timings_ms: dict[str, int] = field(default_factory=dict)


# ------------------------------------------------------------------------------ 1. understanding
def terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower()) if w not in _STOPWORDS]


def needs_rewrite(question: str, history: list[dict[str, str]]) -> bool:
    return bool(history) and (len(terms(question)) <= 3 or bool(_FOLLOW_UP.search(question)))


def rewrite_question(question: str, history: list[dict[str, str]]) -> str:
    """One short model call: turn a follow-up into a standalone question."""
    turns = "\n".join(f"{t.get('role', 'user')}: {str(t.get('content', ''))[:400]}" for t in history[-settings.query_history_turns :])
    out = claude_generate(
        system="Rewrite the user's last question as one standalone question. Reply with the question only.",
        user=f"Conversation:\n{turns}\n\nLast question: {question}",
        temperature=0.0,
        max_tokens=120,
        cache_system=False,
    )
    rewritten = out.strip().strip('"').splitlines()[0].strip() if out.strip() else ""
    return rewritten or question


def expand(question: str) -> list[str]:
    """The question plus a keyword-only variant (helps short, noisy questions); no model call."""
    keywords = " ".join(dict.fromkeys(terms(question)))
    return [question] + ([keywords] if keywords and keywords.lower() != question.lower() else [])


# --------------------------------------------------------------------------------- 2. retrieval
def search(project_id: str, vectors: list[list[float]]) -> list[Source]:
    hits: dict[tuple[str, str], Source] = {}
    for kind, store in (("chunk", get_qdrant_client()), ("wiki", get_qdrant_client(settings.qdrant_wiki_collection))):
        for vec in vectors:
            for hit in store.search(vec, project_id=project_id, limit=settings.query_candidates):
                meta = hit["metadata"]
                key = meta.get("chunk_id") if kind == "chunk" else meta.get("wiki_id")
                if not key or hit["score"] < settings.query_min_score:
                    continue
                prev = hits.get((kind, key))
                if prev is None or hit["score"] > prev.score:
                    hits[(kind, key)] = Source(kind=kind, key=key, score=float(hit["score"]))
    return list(hits.values())


def verify(db: Session, project_id: str, sources: list[Source]) -> list[Source]:
    """Keep only content that still exists for this project; take full text from Postgres."""
    chunk_ids = [s.key for s in sources if s.kind == "chunk"]
    wiki_ids = [s.key for s in sources if s.kind == "wiki"]
    chunks = {}
    if chunk_ids:
        rows = (
            db.query(ChunkArchive, DocumentFile.filename)
            .join(DocumentFile, DocumentFile.id == ChunkArchive.document_file_id)
            .join(DocumentJob, DocumentJob.job_id == DocumentFile.job_id)
            .filter(
                ChunkArchive.id.in_(chunk_ids),
                ChunkArchive.project_id == project_id,
                DocumentJob.status.notin_(["deleted", "failed"]),
            )
            .all()
        )
        chunks = {c.id: (c, fname) for c, fname in rows}
    wikis = {}
    if wiki_ids:
        wikis = {
            w.id: w
            for w in db.query(WikiPageFinal).filter(
                WikiPageFinal.id.in_(wiki_ids), WikiPageFinal.project_id == project_id, WikiPageFinal.is_published.is_(True)
            )
        }
    verified = []
    for s in sources:
        if s.kind == "chunk" and s.key in chunks:
            c, fname = chunks[s.key]
            s.text, s.filename, s.page_number, s.chunk_number = c.text, fname, c.page_number, c.chunk_number
            verified.append(s)
        elif s.kind == "wiki" and s.key in wikis:
            w = wikis[s.key]
            s.text, s.title = w.content, w.entity_name
            verified.append(s)
    return verified


def rerank(question: str, sources: list[Source], top_k: int) -> list[Source]:
    """Vector score blended with keyword overlap; near-duplicate texts are dropped."""
    q_terms = set(terms(question))
    for s in sources:
        overlap = len(q_terms & set(terms(s.text))) / len(q_terms) if q_terms else 0.0
        s.rank_score = 0.75 * s.score + 0.25 * overlap + (0.02 if s.kind == "chunk" else 0.0)
    picked: list[Source] = []
    seen: list[set[str]] = []
    for s in sorted(sources, key=lambda x: x.rank_score, reverse=True):
        words = set(terms(s.text))
        if any(words and len(words & w) / max(len(words | w), 1) > 0.8 for w in seen):
            continue
        picked.append(s)
        seen.append(words)
        if len(picked) >= top_k:
            break
    return picked


# ---------------------------------------------------------------------------------- 3. answer
def build_context(sources: list[Source], max_chars: int) -> tuple[str, list[Source]]:
    """Number the sources [S1].. and fit them into the character budget (later sources are trimmed/dropped)."""
    parts, used, budget = [], [], max_chars
    for s in sources:
        header = f"[S{len(used) + 1}] {s.label()}\n"
        room = budget - len(header)
        if room < 200:
            break
        body = s.text if len(s.text) <= room else s.text[: room - 3] + "..."
        parts.append(header + body)
        used.append(s)
        budget -= len(header) + len(body) + 2
    return "\n\n".join(parts), used


_ANSWER_SYSTEM = (
    "You answer questions about a consulting project using only the numbered sources provided. "
    "Cite every claim with its source number in square brackets, e.g. [S1] or [S2][S3]. "
    "Be concise. If the sources do not contain the answer, reply exactly: INSUFFICIENT_EVIDENCE"
)


def citations_for(answer: str, used: list[Source]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for n in (int(m) for m in _CITATION.findall(answer)):
        if 1 <= n <= len(used) and n not in seen:
            seen.add(n)
            s = used[n - 1]
            out.append(
                {
                    "ref": f"S{n}",
                    "type": s.kind,
                    "id": s.key,
                    "filename": s.filename,
                    "page_number": s.page_number,
                    "chunk_number": s.chunk_number,
                    "title": s.title,
                    "score": round(s.score, 3),
                    "snippet": s.text[:240],
                }
            )
    return out


def _source_view(s: Source) -> dict[str, Any]:
    return {
        "type": s.kind,
        "id": s.key,
        "label": s.label(),
        "score": round(s.score, 3),
        "rank_score": round(s.rank_score, 3),
        "snippet": s.text[:240],
    }


def format_answer(result: QueryResult) -> str:
    """Plain-text reply for chat surfaces: the answer plus a numbered source list."""
    if result.status == "answered":
        lines = [
            f"[{c['ref']}] " + (f"Wiki: {c['title']}" if c["type"] == "wiki" else f"{c['filename']}"
                                + (f", page {c['page_number']}" if c.get("page_number") else ""))
            for c in result.citations
        ]
        return result.answer + ("\n\nSources:\n" + "\n".join(lines) if lines else "")
    if result.status == "llm_unavailable" and result.sources:
        return result.answer + "\n" + "\n".join(f"- {s['label']}" for s in result.sources[:5])
    return result.answer


def answer_question(
    db: Session, project_id: str, question: str, history: list[dict[str, str]] | None = None, top_k: int | None = None
) -> QueryResult:
    history = history or []
    timings: dict[str, int] = {}
    calls = 0
    t = time.monotonic()

    standalone = question.strip()
    if needs_rewrite(standalone, history):
        try:
            standalone = rewrite_question(standalone, history)
            calls += 1
        except Exception as e:  # rewriting is an optimisation; the raw question still works
            logger.warning("[QUERY] follow-up rewrite failed: %s", e)
    queries = expand(standalone)
    vectors = get_embedding_service().embed_batch(queries)
    timings["understanding"] = int((time.monotonic() - t) * 1000)

    t = time.monotonic()
    ranked = rerank(standalone, verify(db, project_id, search(project_id, vectors)), top_k or settings.query_top_k)
    timings["retrieval"] = int((time.monotonic() - t) * 1000)
    result = QueryResult(
        status=INSUFFICIENT, answer=_INSUFFICIENT_TEXT, standalone_question=standalone, queries=queries,
        sources=[_source_view(s) for s in ranked], model_calls=calls, timings_ms=timings,
    )
    if not ranked:
        logger.info("[QUERY] no supporting content for %r", standalone)
        return result

    t = time.monotonic()
    context, used = build_context(ranked, settings.query_context_max_chars)
    try:
        text = claude_generate(
            system=_ANSWER_SYSTEM,
            user=f"SOURCES:\n{context}\n\nQUESTION: {standalone}",
            temperature=0.0,
            max_tokens=settings.query_max_answer_tokens,
        )
        result.model_calls += 1
    except Exception as e:
        logger.error("[QUERY] answer generation failed: %s", e)
        result.status = "llm_unavailable"
        result.answer = "The model is unavailable right now; the most relevant sources are listed below."
        timings["answer"] = int((time.monotonic() - t) * 1000)
        return result
    timings["answer"] = int((time.monotonic() - t) * 1000)

    cites = citations_for(text, used)
    if "INSUFFICIENT_EVIDENCE" in text or not cites:
        return result  # an answer that cites nothing is not supported by the sources
    result.status, result.answer, result.citations = "answered", text.strip(), cites
    return result
