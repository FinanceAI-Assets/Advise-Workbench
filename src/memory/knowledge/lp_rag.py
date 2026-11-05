"""Leading Practice library retrieval as a LangGraph pipeline.

    START -> load_index -> prepare_query -> keyword  -> fuse -> select -> generate -> END
                 |                       -> semantic ->            |
                 +--> END (library is empty)                       +--> END (no answer asked for)

- load_index     the passages of the library (rebuilt when a file changes)
- prepare_query  shorten very long queries to their most frequent terms
- keyword        BM25 search
- semantic       embedding search (runs alongside keyword; skipped when LP_RAG_SEMANTIC_ENABLED=false)
- fuse           merge the two rankings (reciprocal rank fusion)
- select         drop repeated passages and keep the best ``max_results``
- generate       only when an answer is asked for: answer from the passages, citing them by number

Each node is one trace span (``rag.lp.<node>``).
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.core.config import settings
from src.core.observability.otel_tracing import start_span
from src.llm.claude import claude_generate
from src.memory.knowledge import lp_index
from src.memory.retrieval import _tokenize
from src.prompts.registry import get_prompt

_LOG = logging.getLogger(__name__)

CANDIDATES = 20  # passages each search hands to the fusion step
MAX_QUERY_TERMS = 32
RRF_K = 60
_STOPWORDS = frozenset(
    ["the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have", "had", "not", "but", "you", "your", "our", "their", "its", "can", "will", "would", "should", "could", "into", "over", "under", "about", "than", "then", "them", "they", "what", "when", "where", "which", "who", "how", "all", "any", "each", "per", "may", "also", "such", "via"]
)


class LPState(TypedDict, total=False):
    query: str
    max_results: int
    want_answer: bool
    search_text: str
    passages: int
    keyword_hits: list[tuple[int, float]]
    semantic_hits: list[tuple[int, float]]
    fused: list[tuple[int, float]]
    results: list[dict[str, Any]]
    answer: str


def _load_index(state: LPState) -> LPState:
    return {"passages": len(lp_index.load_index().chunks)}


def _prepare_query(state: LPState) -> LPState:
    query = state["query"].strip()
    terms = [t for t in _tokenize(query) if len(t) > 2 and t not in _STOPWORDS]
    if len(terms) > MAX_QUERY_TERMS:  # callers sometimes pass a whole document as the query
        query = " ".join(term for term, _ in Counter(terms).most_common(MAX_QUERY_TERMS))
    return {"search_text": query}


def _keyword(state: LPState) -> LPState:
    return {"keyword_hits": lp_index.keyword_search(lp_index.load_index(), state["search_text"], CANDIDATES)}


def _semantic(state: LPState) -> LPState:
    if not settings.lp_rag_semantic_enabled:
        return {"semantic_hits": []}
    try:
        return {"semantic_hits": lp_index.semantic_search(lp_index.load_index(), state["search_text"], CANDIDATES)}
    except Exception as exc:  # noqa: BLE001 — the embedding model may be missing; keyword search still answers
        _LOG.warning("leading practice library: semantic search unavailable: %s", exc)
        return {"semantic_hits": []}


def _fuse(state: LPState) -> LPState:
    rankings = [hits for hits in (state["keyword_hits"], state["semantic_hits"]) if hits]
    scores: dict[int, float] = {}
    for hits in rankings:
        for rank, (position, _) in enumerate(hits, start=1):
            scores[position] = scores.get(position, 0.0) + 1.0 / (RRF_K + rank)
    best = len(rankings) / (RRF_K + 1)  # the score of a passage ranked first by every search
    fused = sorted(((p, s / best) for p, s in scores.items()), key=lambda pair: pair[1], reverse=True)
    return {"fused": fused}


def _select(state: LPState) -> LPState:
    chunks = lp_index.load_index().chunks
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, score in state["fused"]:
        chunk = chunks[position]
        key = " ".join(chunk["text"].split())[:200]
        if key in seen:
            continue
        seen.add(key)
        results.append({**chunk, "relevance_score": round(score, 4)})
        if len(results) >= state["max_results"]:
            break
    return {"results": results}


def _generate(state: LPState) -> LPState:
    if not state["results"]:
        return {"answer": "The Leading Practice library has nothing on this."}
    prompt = get_prompt("lp_rag_answer")
    passages = "\n\n".join(f"[{n}] {r['heading']}\n{r['text']}" for n, r in enumerate(state["results"], start=1))
    answer = claude_generate(
        system=prompt.render_system(),
        user=prompt.render_user(question=state["query"], passages=passages),
        max_tokens=700,
    )
    return {"answer": answer.strip()}


def _traced(name: str, node: Callable[[LPState], LPState]) -> Callable[[LPState], LPState]:
    def run(state: LPState) -> LPState:
        with start_span(f"rag.lp.{name}") as span:
            update = node(state)
            for key, value in update.items():
                span.set_attribute(f"rag.{key}", len(value) if isinstance(value, list) else value)
            return update

    return run


@lru_cache(maxsize=1)
def build_lp_rag_graph() -> Any:
    graph = StateGraph(LPState)
    nodes = {
        "load_index": _load_index,
        "prepare_query": _prepare_query,
        "keyword": _keyword,
        "semantic": _semantic,
        "fuse": _fuse,
        "select": _select,
        "generate": _generate,
    }
    for name, node in nodes.items():
        graph.add_node(name, _traced(name, node))
    graph.add_edge(START, "load_index")
    graph.add_conditional_edges("load_index", lambda s: "prepare_query" if s["passages"] else END, ["prepare_query", END])
    graph.add_edge("prepare_query", "keyword")
    graph.add_edge("prepare_query", "semantic")
    graph.add_edge(["keyword", "semantic"], "fuse")
    graph.add_edge("fuse", "select")
    graph.add_conditional_edges("select", lambda s: "generate" if s["want_answer"] else END, ["generate", END])
    graph.add_edge("generate", END)
    return graph.compile()


def run_lp_rag(query: str, *, max_results: int = 5, want_answer: bool = False) -> LPState:
    """Search the library; with ``want_answer`` also write an answer that cites the passages found."""
    with start_span("rag.lp", attributes={"rag.query_chars": len(query), "rag.want_answer": want_answer}) as span:
        final = build_lp_rag_graph().invoke({"query": query, "max_results": max_results, "want_answer": want_answer})
        span.set_attribute("rag.results", len(final.get("results") or []))
        return final
