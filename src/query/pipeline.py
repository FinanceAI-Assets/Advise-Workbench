"""Query pipeline: the one path every question takes to a cited answer.

Callers: ``src.query.service.ask`` (used by ``POST /api/query``, Sheldon's rag_agent and Talk to data). A
``QueryScope`` says what is searched: the indexed Leading Practice Library (released content only) and/or one
engagement's uploaded documents. Both are indexed by the ingestion pipeline (``src.workers.pipeline``) into Postgres and
Qdrant, under ``project_id`` = ``LIBRARY_SCOPE`` or the engagement id.

1. Understanding
   - Analysis (no model call): intent, question type, entities, keywords, language; the conversation's earlier
     turns are loaded by the caller and passed as ``history``.
   - Expansion: a follow-up is rewritten into a standalone question (one small model call, only when needed); a
     focused variant (entities + keywords) and a keyword variant are added without a model call; model-written
     variants: an English translation of a non-English question (``query_llm_variants=auto``), or also a clearer
     rewrite and a paraphrase (``always``). Variants are ranked by kind and all returned (stored with the turn).
   - Embedding: every variant is embedded in one batch and scored by similarity to the main question; variants
     that drift below ``query_variant_min_similarity`` are dropped; the best ``query_max_variants`` are searched.
2. Retrieval
   - Vector search over the library's chunks and wiki pages (``query_candidates`` per variant and collection) and
     over the engagement's document chunks.
   - Validation against Postgres: only current, existing, released content, with full text from the source of
     truth. Every wiki page in the rerank pool is scored 0-1 against the source chunks it was written from
     (details kept on the source) and dropped below ``query_min_verification``.
   - Reranking: a cross-encoder (``query_reranker_base_url`` for a hosted /rerank service, or a local
     ``query_reranker_model``), else vector score + keyword overlap; near-duplicates dropped; best ``top_k`` kept.
3. Answer
   - Context: the final sources plus the source chunks behind each wiki page, deduplicated, packed into
     ``query_context_max_tokens``.
   - One model call (``query_llm_timeout_sec`` each, retried ``query_llm_retries`` times on timeouts and API errors)
     that must answer from the sources only and cite [S#]; an answer citing too few of its sentences is rejected.
   - Citations: extracted, validated (references to sources that were not given are removed), linked, with
     practice metadata.
4. Failures: no results, low-confidence or unverified results -> "insufficient evidence" without a model call;
   a model that still fails -> "Unable to process question now" with the sources. Every outcome is logged and
   counted (``src.core.observability.metrics``, also sent to OpenObserve when enabled).

Verification reads chunk text from ``chunk_archive`` rather than SeaweedFS: S3 holds the original binary
(PDF/DOCX), and ``chunk_archive`` is the text extracted from exactly those bytes (hash-pinned at intake).
The same holds for engagement uploads; their passages are stored per engagement, never shared with another scope.

Concurrency: every request has its own session and state; answer calls run on one bounded pool
(``query_max_concurrent_answers``), so calls that overrun their limit cannot pile up threads or model processes.
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import json
import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.db.models import ChunkArchive, DocumentChunkLink, DocumentFile, DocumentJob, LpPractice, WikiPageFinal
from src.core.embeddings.embedding_service import get_embedding_service
from src.core.observability import metrics
from src.core.vector_db.qdrant_client import get_qdrant_client
from src.llm import gateway
from src.llm.claude import claude_generate
from src.memory.knowledge.library_release import LIBRARY_SCOPE, released_document_ids

logger = logging.getLogger(__name__)

INSUFFICIENT = "insufficient_evidence"
LLM_UNAVAILABLE = "llm_unavailable"
_INSUFFICIENT_TEXT = "Insufficient evidence: the available documents do not contain information that answers this question."
_UNAVAILABLE_TEXT = "Unable to process question now. The most relevant sources are listed below."

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
_WH_WORDS = ("who", "whom", "whose", "what", "when", "where", "why", "how", "which")
_WHAT_VERBS = ("explain", "describe", "tell", "list", "summarize", "summarise", "define", "outline", "give", "show")
_YES_NO = re.compile(r"^(is|are|was|were|do|does|did|can|could|should|will|would|has|have|had|may|must)\b", re.I)
_ENTITY = re.compile(r"\b[A-Z][\w&\-]*(?:\s+(?:of|and|for|&)?\s*[A-Z][\w&\-]*)*")
_QUOTED = re.compile(r"\"([^\"]{2,80})\"|“([^”]{2,80})”|'([^']{2,80})'")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_CITATIONS_ONLY = re.compile(r"^(\[S\d+\]\s*)+[.;,]?$")
# Intent, first match wins: what the user wants back, which shapes how an answer should read.
_INTENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("comparison", re.compile(r"\b(compare|comparison|difference|differ|versus|vs\.?|better than|pros and cons)\b", re.I)),
    ("recommendation", re.compile(r"\b(should (i|we)|recommend|best practice|best way|advise|suggest)\b", re.I)),
    ("procedure", re.compile(r"^\s*how (do|does|can|should|to|is|are)\b|\b(steps?|process|procedure|workflow|how to)\b", re.I)),
    ("definition", re.compile(r"^\s*(what (is|are|does) (a |an |the )?\S+( \S+)?\??$|define\b)|\b(meaning of|definition)\b", re.I)),
    ("reason", re.compile(r"^\s*why\b|\b(reason|purpose|rationale)\b", re.I)),
    ("list", re.compile(r"^\s*(list|name|enumerate)\b|\b(what are the|which are the|examples? of|types of|kinds of)\b", re.I)),
    ("summary", re.compile(r"^\s*(summari[sz]e|overview|explain|describe|tell me about|outline)\b", re.I)),
    ("verification", _YES_NO),
    ("fact", re.compile(r"^\s*(who|when|where|which|how (many|much|long|often))\b", re.I)),
)
# Expansion order = how likely a variant is to find the answer.
_VARIANT_PRIORITY = ("standalone", "original", "translated", "clarified", "paraphrase", "focused", "keywords")
# Model errors worth retrying; the others (not configured, budget, circuit open) fail the same way again.
_RETRYABLE = {"timeout", "rate_limit", "api_error"}


@dataclass(frozen=True)
class QueryScope:
    """What a question searches.

    ``index``: the project id of indexed content (Qdrant + Postgres); the Leading Practice Library is
    ``LIBRARY_SCOPE`` (released versions only), None searches no library content. ``engagement_id``: also search
    that engagement's uploaded documents (indexed under its own id). ``practice_ids``: only these library practices."""

    index: str | None = LIBRARY_SCOPE
    engagement_id: str | None = None
    practice_ids: tuple[str, ...] = ()


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
    verification: float = 1.0  # chunks are the source text; wiki pages are scored against their source chunks
    verification_details: dict[str, Any] = field(default_factory=lambda: {"method": "source_passage"})
    practice_id: str | None = None
    practice_title: str | None = None
    source_documents: list[str] = field(default_factory=list)  # wiki: document_files it was written from
    evidence: list[dict[str, Any]] = field(default_factory=list)  # wiki: the source chunks that support it
    evidence_sources: list[Source] = field(default_factory=list)  # the same chunks, for the model's context
    supports: str | None = None  # chunk added as the evidence of this wiki page
    engagement_id: str | None = None  # set for content of an engagement's uploads

    @property
    def scope(self) -> str:
        return "engagement" if self.engagement_id else "library"

    def label(self) -> str:
        if self.kind == "wiki":
            return f"Wiki: {self.title}"
        page = f", page {self.page_number}" if self.page_number else ""
        return f"{self.filename}{page}"

    def display_title(self) -> str:
        if self.kind == "wiki":
            return self.title or "Wiki page"
        name = self.practice_title or self.filename or "Source"
        return f"{name}, page {self.page_number}" if self.page_number else name

    def link(self) -> str:
        link = f"/api/query/sources/{self.kind}/{self.key}"
        return f"{link}?engagement_id={self.engagement_id}" if self.engagement_id else link


@dataclass
class QueryResult:
    status: str  # answered | insufficient_evidence | llm_unavailable
    answer: str
    standalone_question: str
    queries: list[str]  # the variants that were embedded and searched
    question: str = ""
    reason: str | None = None  # no_results | low_confidence | low_verification | model_declined | uncited_answer | llm_failed
    answer_markdown: str = ""
    understanding: dict[str, Any] = field(default_factory=dict)
    variants: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    answer_metadata: dict[str, Any] = field(default_factory=dict)
    model_calls: int = 0
    timings_ms: dict[str, int] = field(default_factory=dict)


# ------------------------------------------------------------------------------ 1. understanding
def terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower()) if w not in _STOPWORDS]


def _stems(text: str) -> set[str]:
    """Terms with a plural/verb "s" removed, so a summary's "payment" matches its source's "payments"."""
    return {w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w for w in terms(text)}


def needs_rewrite(question: str, history: list[dict[str, str]]) -> bool:
    return bool(history) and (len(terms(question)) <= 3 or bool(_FOLLOW_UP.search(question)))


def question_type(question: str) -> str:
    words = re.findall(r"[a-z]+", question.lower())
    for word in words[:4]:
        if word in _WH_WORDS:
            return {"whom": "who", "whose": "who"}.get(word, word)
    if words and words[0] in _WHAT_VERBS:
        return "what"
    return "yes_no" if _YES_NO.match(question.strip()) else "other"


def intent(question: str) -> str:
    """comparison | recommendation | procedure | definition | reason | list | summary | verification | fact | other"""
    return next((name for name, pattern in _INTENTS if pattern.search(question)), "other")


def entities(question: str) -> list[str]:
    """Quoted phrases and capitalised names (a lone capitalised first word is just the start of the sentence)."""
    found = [next(g for g in m.groups() if g) for m in _QUOTED.finditer(question)]
    first = re.match(r"\s*([A-Za-z]+)", question)
    for m in _ENTITY.finditer(question):
        name = m.group(0).strip()
        if m.start() == (first.start(1) if first else -1) and " " not in name:
            continue
        if name.lower() in _STOPWORDS or name.lower() in _WH_WORDS:
            continue
        found.append(name)
    return list(dict.fromkeys(found))[:8]


def language_of(question: str) -> str:
    letters = [c for c in question if c.isalpha()]
    other = sum(1 for c in letters if not c.isascii())
    return "other" if letters and other / len(letters) > 0.3 else "en"


def understand(question: str, history: list[dict[str, str]]) -> dict[str, Any]:
    names = entities(question)
    name_words = {w for n in names for w in terms(n)}
    return {
        "intent": intent(question),
        "question_type": question_type(question),
        "is_follow_up": needs_rewrite(question, history),
        "context_turns": sum(1 for t in history if t.get("role") == "user"),
        "entities": names,
        "keywords": [t for t in dict.fromkeys(terms(question)) if t not in name_words][:8],
        "language": language_of(question),
    }


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


def model_variants(question: str, language: str, *, paraphrase: bool) -> list[dict[str, str]]:
    """One short model call: an English translation (non-English questions) or a clearer rewrite, and optionally
    a paraphrase in different words."""
    first = ("translated", "the question translated into English as one clear, specific search question") if language != "en" \
        else ("clarified", "the question rewritten as one clear, specific search question, keeping every name and term")
    kinds = [first] + ([("paraphrase", "the same question in different words (synonyms), keeping every name")] if paraphrase else [])
    out = claude_generate(
        system="Write search queries for a question. " + " ".join(f"Line {i}: {desc}." for i, (_, desc) in enumerate(kinds, 1))
        + " Reply with the lines only, no numbering.",
        user=question,
        temperature=0.0,
        max_tokens=200,
        cache_system=False,
    )
    lines = [re.sub(r"^\s*(line\s*)?\d+[.:)]\s*", "", ln, flags=re.I).strip().strip('"') for ln in out.splitlines() if ln.strip()]
    return [{"text": text, "kind": kind} for (kind, _), text in zip(kinds, lines, strict=False) if text]  # the model may return fewer lines


def expand(question: str) -> list[str]:
    """The question plus a keyword-only variant (helps short, noisy questions); no model call."""
    keywords = " ".join(dict.fromkeys(terms(question)))
    return [question] + ([keywords] if keywords and keywords.lower() != question.lower() else [])


def build_variants(original: str, standalone: str, extras: list[dict[str, str]], understanding: dict[str, Any]) -> list[dict[str, Any]]:
    """Every variant, ranked by kind (most likely to find the answer first) and without duplicates."""
    found = [{"text": standalone, "kind": "standalone"}] if standalone != original else []
    found.append({"text": original, "kind": "original"})
    found += extras
    if understanding["entities"]:
        found.append({"text": " ".join(understanding["entities"] + understanding["keywords"][:4]), "kind": "focused"})
    found += [{"text": v, "kind": "keywords"} for v in expand(standalone)[1:]]
    seen: set[str] = set()
    variants = []
    for v in sorted(found, key=lambda v: _VARIANT_PRIORITY.index(v["kind"])):
        if v["text"].strip() and v["text"].lower() not in seen:
            seen.add(v["text"].lower())
            variants.append({**v, "score": None, "embedded": False})
    return variants


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def select_variants(variants: list[dict[str, Any]], vectors: list[list[float]]) -> list[list[float]]:
    """Score each variant by similarity to the main question (the first variant); keep the best that stay on topic.

    A translation is kept regardless: an English-only embedding model sees little similarity across languages."""
    main = vectors[0]
    chosen: list[list[float]] = []
    for v, vec in zip(variants, vectors, strict=True):
        v["score"] = round(_cosine(main, vec), 3)
        on_topic = v is variants[0] or v["kind"] == "translated" or v["score"] >= settings.query_variant_min_similarity
        if on_topic and len(chosen) < settings.query_max_variants:
            v["embedded"] = True
            chosen.append(vec)
    return chosen


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


def search_engagement(db: Session, engagement_id: str, vectors: list[list[float]]) -> list[Source]:
    """The engagement's uploaded passages closest to the query: the pipeline's index under the engagement's id,
    validated against Postgres like the library (current versions of documents that were not deleted)."""
    found = verify(db, engagement_id, search(engagement_id, vectors))
    for s in found:
        s.engagement_id = engagement_id
    return found


def _split_key(name: str) -> tuple[str | None, str]:
    """Library document keys are ``<practice>/<JOB-n>/<file>``; other keys are just the file name."""
    parts = name.split("/", 2)
    return (parts[0], parts[2]) if len(parts) == 3 else (None, name.rsplit("/", 1)[-1])


def _source_documents(page: WikiPageFinal) -> list[str]:
    info = page.merge_info
    if isinstance(info, str):
        try:
            info = json.loads(info)
        except ValueError:
            info = {}
    return list((info or {}).get("source_documents", []))


def verify(db: Session, project_id: str, sources: list[Source]) -> list[Source]:
    """Keep only content that still exists (and, for the library, is released); take full text from Postgres."""
    released = released_document_ids(db) if project_id == LIBRARY_SCOPE else None
    chunk_ids = [s.key for s in sources if s.kind == "chunk"]
    wiki_ids = [s.key for s in sources if s.kind == "wiki"]
    chunks = {}
    if chunk_ids:
        # A passage is stored once and linked from every document version that contains it.
        rows = (
            db.query(ChunkArchive, DocumentChunkLink, DocumentFile.filename)
            .join(DocumentChunkLink, DocumentChunkLink.chunk_id == ChunkArchive.id)
            .join(DocumentFile, DocumentFile.id == DocumentChunkLink.document_file_id)
            .join(DocumentJob, DocumentJob.job_id == DocumentFile.job_id)
            .filter(
                ChunkArchive.id.in_(chunk_ids),
                ChunkArchive.project_id == project_id,
                DocumentJob.status.notin_(["deleted", "failed"]),
            )
            .all()
        )
        if released is not None:
            # Users only retrieve the released version of Approved practices, never candidates in review.
            rows = [r for r in rows if r[1].document_file_id in released]
        for c, link, fname in rows:
            chunks.setdefault(c.id, (c, link, fname))
    wikis: dict[str, tuple[WikiPageFinal, list[str]]] = {}
    if wiki_ids:
        for w in db.query(WikiPageFinal).filter(
            WikiPageFinal.id.in_(wiki_ids), WikiPageFinal.project_id == project_id, WikiPageFinal.is_published.is_(True)
        ):
            docs = _source_documents(w)
            if released is not None:
                docs = [d for d in docs if d in released]
                if not docs:
                    continue  # written only from candidates or superseded versions
            wikis[w.id] = (w, docs)
    verified = []
    for s in sources:
        if s.kind == "chunk" and s.key in chunks:
            c, link, fname = chunks[s.key]
            s.text, s.page_number, s.chunk_number = c.text, link.page_number, link.chunk_number
            s.practice_id, s.filename = _split_key(fname)
            verified.append(s)
        elif s.kind == "wiki" and s.key in wikis:
            w, docs = wikis[s.key]
            s.text, s.title, s.source_documents = w.content, w.entity_name, docs
            verified.append(s)
    _attach_practices(db, verified)
    return verified


def _attach_practices(db: Session, sources: list[Source]) -> None:
    ids = {s.practice_id for s in sources if s.practice_id}
    if not ids:
        return
    titles = {p.id: p.title for p in db.query(LpPractice).filter(LpPractice.id.in_(ids))}
    for s in sources:
        if s.practice_id:
            s.practice_title = titles.get(s.practice_id)


def verify_wiki_pages(db: Session, sources: list[Source]) -> None:
    """Score each wiki page 0-1: the share of its terms found in the source chunks that best support it.

    The best ``query_verify_evidence`` chunks of the page's source documents are attached as its evidence, and
    the details of the check are kept in ``verification_details``."""
    pages = [s for s in sources if s.kind == "wiki"]
    doc_ids = sorted({d for s in pages for d in s.source_documents})
    by_doc: dict[str, list[tuple[ChunkArchive, DocumentChunkLink, str]]] = {}
    if doc_ids:
        rows = (
            db.query(ChunkArchive, DocumentChunkLink, DocumentFile.filename)
            .join(DocumentChunkLink, DocumentChunkLink.chunk_id == ChunkArchive.id)
            .join(DocumentFile, DocumentFile.id == DocumentChunkLink.document_file_id)
            .filter(DocumentChunkLink.document_file_id.in_(doc_ids))
            .all()
        )
        for c, link, fname in rows:
            by_doc.setdefault(link.document_file_id, []).append((c, link, fname))
    for s in pages:
        page_terms = _stems(f"{s.title or ''} {s.text}")
        candidates = [(len(page_terms & _stems(c.text)), c, link, fname) for d in s.source_documents for c, link, fname in by_doc.get(d, [])]
        best = sorted((x for x in candidates if x[0]), key=lambda x: x[0], reverse=True)[: settings.query_verify_evidence]
        supported = set().union(*(_stems(c.text) for _, c, _, _ in best)) & page_terms if best else set()
        s.verification = round(len(supported) / len(page_terms), 3) if page_terms else 0.0
        s.evidence, s.evidence_sources = [], []
        for _, c, link, fname in best:
            practice, filename = _split_key(fname)
            s.evidence.append({
                "id": c.id, "filename": filename, "practice_id": practice, "page_number": link.page_number,
                "chunk_number": link.chunk_number, "snippet": c.text[:240], "link": f"/api/query/sources/chunk/{c.id}",
            })
            s.evidence_sources.append(Source(
                kind="chunk", key=c.id, score=s.score, text=c.text, filename=filename, page_number=link.page_number,
                chunk_number=link.chunk_number, practice_id=practice, supports=s.key,
            ))
        s.verification_details = {
            "method": "term_support",
            "supported_terms": len(supported),
            "total_terms": len(page_terms),
            "unsupported_terms": sorted(page_terms - supported)[:12],
            "evidence_ids": [e["id"] for e in s.evidence],
            "source_documents": len(s.source_documents),
            "threshold": settings.query_min_verification,
            "passed": s.verification >= settings.query_min_verification,
        }
        if s.practice_id is None and s.evidence:
            s.practice_id = s.evidence[0]["practice_id"]
    _attach_practices(db, pages + [e for s in pages for e in s.evidence_sources])


_cross_encoder: Any = None  # loaded on first use; False once loading failed
_cross_encoder_lock = threading.Lock()


def _get_cross_encoder() -> Any:
    global _cross_encoder
    if not settings.query_reranker_model or settings.query_reranker_base_url:
        return None
    with _cross_encoder_lock:  # concurrent first questions load the model once
        if _cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder

                _cross_encoder = CrossEncoder(settings.query_reranker_model)
            except Exception as e:
                logger.warning("[QUERY] cross-encoder %s unavailable, using keyword rerank: %s", settings.query_reranker_model, e)
                _cross_encoder = False
    return _cross_encoder or None


def reranker_name() -> str:
    if settings.query_reranker_base_url:
        return f"cross-encoder:{settings.query_reranker_model or 'remote'}"
    return f"cross-encoder:{settings.query_reranker_model}" if _get_cross_encoder() else "keyword"


def _remote_rerank(question: str, texts: list[str]) -> list[float]:
    """Text Embeddings Inference style API: POST {base}/rerank {"query", "texts"} -> [{"index", "score"}]."""
    key = settings.query_reranker_api_key or settings.embedding_api_key
    resp = httpx.post(
        f"{settings.query_reranker_base_url.rstrip('/')}/rerank",
        json={"query": question, "texts": texts, "truncate": True},
        headers={"authorization": f"Bearer {key}"} if key else {},
        timeout=settings.embedding_timeout_sec,
    )
    resp.raise_for_status()
    scores = [0.0] * len(texts)
    for item in resp.json():
        scores[int(item["index"])] = float(item["score"])
    return scores


def cross_encoder_scores(question: str, sources: list[Source]) -> list[float] | None:
    if not sources:
        return None
    texts = [s.text[:2000] for s in sources]
    try:
        if settings.query_reranker_base_url:
            return _remote_rerank(question, texts)
        model = _get_cross_encoder()
        return [float(x) for x in model.predict([(question, t) for t in texts])] if model is not None else None
    except Exception as e:
        logger.warning("[QUERY] cross-encoder scoring failed, using keyword rerank: %s", e)
        metrics.increment("query_rerank_fallback_total")
        return None


def rerank(question: str, sources: list[Source], top_k: int) -> list[Source]:
    """Cross-encoder relevance when configured, else vector score blended with keyword overlap; near-duplicate
    texts are dropped."""
    q_terms = set(terms(question))
    scores = cross_encoder_scores(question, sources)
    for i, s in enumerate(sources):
        if scores is not None:
            s.rank_score = scores[i]
        else:
            overlap = len(q_terms & set(terms(s.text))) / len(q_terms) if q_terms else 0.0
            s.rank_score = 0.75 * s.score + 0.25 * overlap + (0.02 if s.kind != "wiki" else 0.0)
    picked: list[Source] = []
    seen: list[set[str]] = []
    for s in sorted(sources, key=lambda x: x.rank_score, reverse=True):
        words = set(terms(s.text))
        if _near_duplicate(words, seen):
            continue
        picked.append(s)
        seen.append(words)
        if len(picked) >= top_k:
            break
    return picked


def _near_duplicate(words: set[str], seen: list[set[str]]) -> bool:
    return any(words and len(words & w) / max(len(words | w), 1) > 0.8 for w in seen)


def retrieve(db: Session, scope: QueryScope, question: str, vectors: list[list[float]], top_k: int) -> tuple[list[Source], dict[str, Any]]:
    """Search the scope, validate, score wiki pages against their sources, rerank. Returns the sources and counts."""
    hits = search(scope.index, vectors) if scope.index else []
    existing = verify(db, scope.index, hits) if hits else []
    documents = search_engagement(db, scope.engagement_id, vectors) if scope.engagement_id else []
    pool = sorted(existing + documents, key=lambda s: s.score, reverse=True)[: settings.query_rerank_pool]
    verify_wiki_pages(db, pool)
    if scope.practice_ids:  # "ask selected sources only": library content of those practices (wiki pages via evidence)
        pool = [s for s in pool if s.engagement_id or s.practice_id in scope.practice_ids]
    faithful = [s for s in pool if s.verification >= settings.query_min_verification]
    ranked = rerank(question, faithful, top_k)
    stats = {
        "candidates": len(hits) + len(documents),
        "engagement_candidates": len(documents),
        "verified": len(existing) + len(documents),
        "dropped_low_verification": len(pool) - len(faithful),
        "top_score": round(max((s.score for s in faithful), default=0.0), 3),
        "reranker": reranker_name(),
        "final": len(ranked),
    }
    return ranked, stats


# ---------------------------------------------------------------------------------- 3. answer
def assemble_context(sources: list[Source]) -> list[Source]:
    """The final sources, each wiki page followed by the source chunks behind it; duplicates removed."""
    out: list[Source] = []
    keys: set[tuple[str, str]] = set()
    seen: list[set[str]] = []
    for s in sources:
        for item in [s] + s.evidence_sources[: settings.query_evidence_per_wiki]:
            words = set(terms(item.text))
            if (item.kind, item.key) in keys or _near_duplicate(words, seen):
                continue
            keys.add((item.kind, item.key))
            seen.append(words)
            out.append(item)
    return out


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
    "You answer questions using only the numbered sources provided: passages from the engagement's uploaded "
    "documents and from the Leading Practice Library. "
    "Do not use outside knowledge. Cite every claim with its source number in square brackets, e.g. [S1] or "
    "[S2][S3]. Be concise. If the sources do not contain the answer, reply exactly: INSUFFICIENT_EVIDENCE"
)


class AnswerFailed(Exception):
    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__(errors[-1]["message"] if errors else "answer generation failed")
        self.errors = errors


def classify_error(exc: BaseException) -> str:
    """timeout | rate_limit | not_configured | budget | circuit_open | api_error"""
    name, text = type(exc).__name__, str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in name.lower() or "timed out" in text:
        return "timeout"
    if "ratelimit" in name.lower() or "429" in text or "rate limit" in text or "overloaded" in text:
        return "rate_limit"
    if "budget" in name.lower():
        return "budget"
    if "circuit breaker" in text:
        return "circuit_open"
    if "not configured" in text or "not found; install" in text or "no model configured" in text:
        return "not_configured"
    return "api_error"


_answer_pool: concurrent.futures.ThreadPoolExecutor | None = None
_answer_pool_lock = threading.Lock()


def _get_answer_pool() -> concurrent.futures.ThreadPoolExecutor:
    """One bounded pool for every answer call in this process (``query_max_concurrent_answers``)."""
    global _answer_pool
    with _answer_pool_lock:
        if _answer_pool is None:
            _answer_pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, settings.query_max_concurrent_answers), thread_name_prefix="query-answer"
            )
        return _answer_pool


def _call_with_timeout(context: str, question: str) -> str:
    """The answer call under ``query_llm_timeout_sec``, which is also passed to the provider so the model call
    itself stops at the limit (the Claude CLI process is killed). Waiting for a free slot counts toward it."""
    limit = settings.query_llm_timeout_sec
    future = _get_answer_pool().submit(
        contextvars.copy_context().run, claude_generate,
        system=_ANSWER_SYSTEM, user=f"SOURCES:\n{context}\n\nQUESTION: {question}",
        temperature=0.0, max_tokens=settings.query_max_answer_tokens, timeout_sec=limit,
    )
    try:
        return future.result(timeout=limit)
    except concurrent.futures.TimeoutError:
        future.cancel()  # still queued: never runs
        raise TimeoutError(f"answer took longer than {limit:.0f}s") from None


def generate_answer(context: str, question: str) -> tuple[str, int, list[dict[str, Any]]]:
    """The answer call, retried ``query_llm_retries`` times on timeouts and API errors.

    Returns the text, the number of attempts and the errors of the failed attempts; raises ``AnswerFailed``."""
    attempts = settings.query_llm_retries + 1
    errors: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        try:
            return _call_with_timeout(context, question), attempt, errors
        except Exception as e:
            kind = classify_error(e)
            errors.append({"attempt": attempt, "kind": kind, "message": str(e)[:300]})
            metrics.increment(f"query_llm_errors_{kind}_total")
            logger.warning("[QUERY] answer generation failed (attempt %d/%d, %s): %s", attempt, attempts, kind, e)
            if kind not in _RETRYABLE or attempt == attempts:
                raise AnswerFailed(errors) from e
            metrics.increment("query_llm_retries_total")
            wait = settings.query_llm_retry_backoff_sec * attempt * (2 if kind == "rate_limit" else 1)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _model_info() -> dict[str, str]:
    try:
        return {"provider": gateway.provider_name(), "model": gateway.model_for("default")}
    except Exception:
        logger.debug("[QUERY] model provider details unavailable", exc_info=True)
        return {"provider": "unknown", "model": "unknown"}


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
                    "scope": s.scope,
                    "id": s.key,
                    "title": s.display_title(),
                    "filename": s.filename,
                    "page_number": s.page_number,
                    "chunk_number": s.chunk_number,
                    "practice_id": s.practice_id,
                    "practice_title": s.practice_title,
                    "supports": s.supports,
                    "score": round(s.score, 3),
                    "verification": s.verification,
                    "snippet": s.text[:240],
                    "link": s.link(),
                    "markdown": f"[{s.display_title()}]({s.key})",
                }
            )
    return out


def remove_invalid_citations(answer: str, used_count: int) -> str:
    """Drop [S#] markers that point at no source given to the model."""
    cleaned = _CITATION.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= used_count else "", answer)
    return re.sub(r"[ \t]+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", cleaned)).strip()


def link_citations(answer: str, used: list[Source]) -> str:
    """The answer with each valid [S#] turned into a markdown link to its source."""
    def sub(m: re.Match[str]) -> str:
        n = int(m.group(1))
        return f"[S{n}]({used[n - 1].key})" if 1 <= n <= len(used) else m.group(0)

    return _CITATION.sub(sub, answer)


def claim_coverage(answer: str, used_count: int) -> dict[str, Any]:
    """Which sentences of the answer cite a source. Headings, lead-ins and very short fragments are not claims."""
    claims: list[str] = []
    for part in (p.strip() for p in _SENTENCE.split(answer)):
        if not part:
            continue
        if _CITATIONS_ONLY.match(part) and claims:
            claims[-1] += f" {part}"  # "... is a risk. [S1]" cites the sentence before it
        elif len(terms(part)) >= 3 and not part.endswith(":") and not part.startswith("#"):
            claims.append(part)
    cited = [c for c in claims if _CITATION.search(c)]
    uncited = [c[:200] for c in claims if not _CITATION.search(c)]
    invalid = sorted({f"S{n}" for n in map(int, _CITATION.findall(answer)) if not 1 <= n <= used_count}, key=lambda r: int(r[1:]))
    return {"claims": len(claims), "cited": len(cited), "uncited": uncited, "fully_cited": not uncited and not invalid,
            "invalid_refs": invalid, "ratio": round(len(cited) / len(claims), 3) if claims else 1.0}


def _source_view(s: Source) -> dict[str, Any]:
    return {
        "type": s.kind,
        "scope": s.scope,
        "id": s.key,
        "label": s.label(),
        "title": s.display_title(),
        "filename": s.filename,
        "page_number": s.page_number,
        "practice_id": s.practice_id,
        "practice_title": s.practice_title,
        "score": round(s.score, 3),
        "rank_score": round(s.rank_score, 3),
        "verification": s.verification,
        "verification_details": s.verification_details,
        "snippet": s.text[:240],
        "link": s.link(),
    }


def source_detail(
    db: Session, kind: str, key: str, *, index: str = LIBRARY_SCOPE, engagement_id: str | None = None
) -> dict[str, Any] | None:
    """A cited source in full, with the same visibility rules as retrieval (None when the caller may not see it).

    With ``engagement_id`` the source is looked up in that engagement's uploads; the caller checks access to it."""
    found = verify(db, engagement_id or index, [Source(kind=kind, key=key, score=0.0, engagement_id=engagement_id)])
    if not found:
        return None
    s = found[0]
    verify_wiki_pages(db, [s])
    view = {k: v for k, v in _source_view(s).items() if k not in ("score", "rank_score")}  # no query here
    return {**view, "text": s.text, "chunk_number": s.chunk_number, "evidence": s.evidence}


def format_answer(result: QueryResult) -> str:
    """Plain-text reply for chat surfaces: the answer plus a numbered source list."""
    if result.status == "answered":
        lines = [
            f"[{c['ref']}] " + (f"Wiki: {c['title']}" if c["type"] == "wiki" else f"{c['filename']}"
                                + (f", page {c['page_number']}" if c.get("page_number") else ""))
            + (" (engagement document)" if c.get("scope") == "engagement" else " (Leading Practice Library)")
            for c in result.citations
        ]
        return result.answer + ("\n\nSources:\n" + "\n".join(lines) if lines else "")
    if result.status == LLM_UNAVAILABLE and result.sources:
        return result.answer + "\n" + "\n".join(f"- {s['label']}" for s in result.sources[:5])
    return result.answer


def _finish(result: QueryResult, started: float) -> QueryResult:
    """Log and count the outcome."""
    result.timings_ms["total"] = int((time.monotonic() - started) * 1000)
    metrics.increment("query_requests_total")
    metrics.increment(f"query_status_{result.status}_total")
    if result.reason:
        metrics.increment(f"query_reason_{result.reason}_total")
    metrics.observe_latency("query_total", result.timings_ms["total"])
    if result.status == INSUFFICIENT and result.reason in {"no_results", "low_confidence", "low_verification"}:
        logger.warning("[QUERY] retrieval failure (%s) for %r: %s", result.reason, result.standalone_question, result.retrieval)
    cited = ", ".join(f"{c['ref']}={c['filename'] or c['title']} ({c['scope']})" for c in result.citations) or "-"
    logger.info("[QUERY] done: status=%s reason=%s citations=[%s] coverage=%s timings=%s, %d model call(s)",
                result.status, result.reason or "-", cited, result.coverage.get("ratio", "-"), result.timings_ms,
                result.model_calls)
    return result


def _short(text: str, limit: int = 120) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def answer_question(
    db: Session, scope: QueryScope, question: str, history: list[dict[str, str]] | None = None, top_k: int | None = None
) -> QueryResult:
    """Answer one question from ``scope``. ``history``: earlier turns as ``{role, content}``, for follow-ups.

    Callers check access first (``src.query.service.ask``)."""
    history = history or []
    timings: dict[str, int] = {}
    calls = 0
    started = t = time.monotonic()
    logger.info("[QUERY] start: engagement=%s library=%s practices=%s history=%d question=%r",
                scope.engagement_id or "-", scope.index == LIBRARY_SCOPE, list(scope.practice_ids) or "all",
                len(history), _short(question))

    # 1. understanding: analysis, expansion, embedding
    original = question.strip()
    understanding = understand(original, history)
    standalone = original
    if understanding["is_follow_up"]:
        try:
            standalone = rewrite_question(original, history)
            calls += 1
        except Exception as e:  # rewriting is an optimisation; the raw question still works
            logger.warning("[QUERY] follow-up rewrite failed: %s", e)
    extras: list[dict[str, str]] = []
    mode = settings.query_llm_variants
    if mode == "always" or (mode == "auto" and understanding["language"] != "en"):
        try:
            extras = model_variants(standalone, understanding["language"], paraphrase=mode == "always")
            calls += 1
        except Exception as e:  # a variant only widens the search
            logger.warning("[QUERY] query variants failed: %s", e)
    variants = build_variants(original, standalone, extras, understanding)
    vectors = select_variants(variants, get_embedding_service().embed_batch([v["text"] for v in variants]))
    queries = [v["text"] for v in variants if v["embedded"]]
    timings["understanding"] = int((time.monotonic() - t) * 1000)
    logger.info("[QUERY] 1/3 understanding: intent=%s type=%s language=%s follow_up=%s standalone=%r; %d variants, "
                "%d embedded and searched %s (%d ms)", understanding["intent"], understanding["question_type"],
                understanding["language"], understanding["is_follow_up"], _short(standalone), len(variants),
                len(queries), [_short(q, 60) for q in queries], timings["understanding"])

    # 2. retrieval: search, validation, reranking
    t = time.monotonic()
    ranked, stats = retrieve(db, scope, standalone, vectors, top_k or settings.query_top_k)
    timings["retrieval"] = int((time.monotonic() - t) * 1000)
    logger.info("[QUERY] 2/3 retrieval: Qdrant hits library=%d engagement=%d -> verified in Postgres=%d, dropped "
                "(low verification)=%d, reranker=%s, top_score=%.3f, kept=%d (%d ms)",
                stats["candidates"] - stats["engagement_candidates"], stats["engagement_candidates"], stats["verified"],
                stats["dropped_low_verification"], stats["reranker"], stats["top_score"], stats["final"],
                timings["retrieval"])
    for n, s in enumerate(ranked[:5], start=1):
        logger.info("[QUERY]     #%d %s score=%.3f rank=%.3f %s: %s", n, s.scope, s.score, s.rank_score, s.label(),
                    _short(s.text, 80))
    result = QueryResult(
        status=INSUFFICIENT, answer=_INSUFFICIENT_TEXT, answer_markdown=_INSUFFICIENT_TEXT, question=original,
        standalone_question=standalone, queries=queries, understanding=understanding, variants=variants,
        sources=[_source_view(s) for s in ranked], retrieval=stats, model_calls=calls, timings_ms=timings,
    )
    if not ranked:
        result.reason = "low_verification" if stats["dropped_low_verification"] else "no_results"
        return _finish(result, started)
    if stats["top_score"] < settings.query_min_confidence:
        result.reason = "low_confidence"  # only weak matches: answering from them would be guesswork
        return _finish(result, started)

    # 3. answer: context, generation, citations
    t = time.monotonic()
    context, used = build_context(assemble_context(ranked), settings.query_context_max_tokens * 4)
    meta: dict[str, Any] = {
        **_model_info(),
        "context": {"sources": len(used), "chars": len(context), "tokens_est": len(context) // 4,
                    "max_tokens": settings.query_context_max_tokens},
    }
    result.answer_metadata = meta
    try:
        text, attempts, errors = generate_answer(context, standalone)
    except AnswerFailed as e:
        timings["answer"] = int((time.monotonic() - t) * 1000)
        result.model_calls += len(e.errors)
        meta.update({"attempts": len(e.errors), "errors": e.errors, "latency_ms": timings["answer"]})
        result.status, result.reason = LLM_UNAVAILABLE, "llm_failed"
        result.answer = result.answer_markdown = _UNAVAILABLE_TEXT
        return _finish(result, started)
    timings["answer"] = int((time.monotonic() - t) * 1000)
    result.model_calls += attempts
    meta.update({"attempts": attempts, "errors": errors, "latency_ms": timings["answer"], "answer_chars": len(text)})
    logger.info("[QUERY] 3/3 answer: %s/%s, context %d sources ~%d tokens, %d attempt(s), %d chars (%d ms)",
                meta.get("provider"), meta.get("model"), len(used), len(context) // 4, attempts, len(text),
                timings["answer"])

    if "INSUFFICIENT_EVIDENCE" in text:
        result.reason = "model_declined"
        return _finish(result, started)
    coverage = claim_coverage(text, len(used))
    answer = remove_invalid_citations(text, len(used))
    cites = citations_for(answer, used)
    if not cites or coverage["ratio"] < settings.query_min_citation_coverage:
        result.reason = "uncited_answer"  # not grounded in the sources: evidence-only answers are enforced
        result.coverage = coverage
        return _finish(result, started)
    result.status, result.answer, result.citations, result.coverage = "answered", answer, cites, coverage
    result.answer_markdown = link_citations(answer, used)
    result.sources = [_source_view(s) for s in used]
    return _finish(result, started)
