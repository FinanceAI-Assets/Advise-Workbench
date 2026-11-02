"""Pipeline stages 5-8: knowledge building through the configured model provider (Claude CLI).

extracting_facts -> extracted_facts; generating_wiki -> wiki_pages_draft; deduplicating -> wiki_pages_final
(merged with the project's existing pages); indexing_wiki -> Qdrant <prefix>wiki_pages + embeddings_metadata.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from src.core.config import settings
from src.core.db.models import ChunkArchive, DocumentChunkLink, EmbeddingsMetadata, ExtractedFact, WikiPageDraft, WikiPageFinal
from src.core.db.session import session_scope
from src.core.embeddings.embedding_service import get_embedding_service
from src.core.tz import ist_now
from src.core.vector_db.qdrant_client import get_qdrant_client, point_id_for
from src.memory.facts.fact_extraction import batch_texts, extract_facts
from src.memory.wiki.deduplication import Candidate, assign_drafts
from src.memory.wiki.wiki_page_generator import generate_wiki_pages as write_wiki_pages
from src.memory.wiki.wiki_page_generator import group_entities, normalize_name
from src.workers.celery_app import app
from src.workers.pipeline import IngestionTask, complete_job, update_job

logger = logging.getLogger(__name__)


def _page_text(name: str, content: str) -> str:
    return f"{name}\n\n{content}"


@app.task(base=IngestionTask, stage="extracting_facts")
def extract_facts_from_chunks(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, parsed_id = ctx["job_id"], ctx["parsed_document_id"]
    with session_scope() as db:
        update_job(db, job_id, status="extracting_facts")
        texts = [
            t
            for (t,) in db.query(ChunkArchive.text)
            .join(DocumentChunkLink, DocumentChunkLink.chunk_id == ChunkArchive.id)
            .filter(DocumentChunkLink.document_file_id == ctx["document_file_id"])
            .order_by(DocumentChunkLink.chunk_number)
        ]
    batches = batch_texts(texts, settings.knowledge_fact_batch_chars, settings.knowledge_max_fact_calls)
    facts = [f for batch in batches for f in extract_facts(batch, ctx["filename"])]

    with session_scope() as db:
        db.query(ExtractedFact).filter(ExtractedFact.parsed_document_id == parsed_id).delete()
        now = ist_now()
        for f in facts:
            db.add(
                ExtractedFact(
                    id=f"fact_{uuid.uuid4().hex[:20]}",
                    parsed_document_id=parsed_id,
                    project_id=ctx["project_id"],
                    fact_type=f["type"],
                    fact_name=f["name"],
                    fact_value={"value": f["value"], "context": f["context"]},
                    confidence_score=f["confidence"],
                    source_context=f["context"] or None,
                    created_at=now,
                )
            )
    logger.info("[FACTS] job=%s stored %d facts from %d model call(s)", job_id, len(facts), len(batches))
    return {**ctx, "fact_count": len(facts)}


@app.task(base=IngestionTask, stage="generating_wiki")
def generate_wiki_pages(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, parsed_id = ctx["job_id"], ctx["parsed_document_id"]
    with session_scope() as db:
        update_job(db, job_id, status="generating_wiki")
        facts = [
            {
                "type": f.fact_type,
                "name": f.fact_name,
                "value": (f.fact_value or {}).get("value", "") if isinstance(f.fact_value, dict) else "",
                "context": f.source_context or "",
                "confidence": f.confidence_score or 0.5,
            }
            for f in db.query(ExtractedFact).filter(ExtractedFact.parsed_document_id == parsed_id)
        ]
    pages = write_wiki_pages(group_entities(facts, settings.knowledge_max_wiki_pages), ctx["filename"])

    with session_scope() as db:
        db.query(WikiPageDraft).filter(WikiPageDraft.parsed_document_id == parsed_id).delete()
        now = ist_now()
        for p in pages:
            db.add(
                WikiPageDraft(
                    id=f"wdraft_{uuid.uuid4().hex[:20]}",
                    parsed_document_id=parsed_id,
                    project_id=ctx["project_id"],
                    entity_name=p["entity_name"][:255],
                    entity_type=p["entity_type"],
                    content=p["content"],
                    source_facts=p["source_facts"],
                    is_deduplicated=False,
                    created_at=now,
                )
            )
    logger.info("[WIKI] job=%s wrote %d draft page(s)", job_id, len(pages))
    return {**ctx, "wiki_drafts": len(pages)}


@app.task(base=IngestionTask, stage="deduplicating")
def deduplicate_wiki_pages(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, parsed_id, doc_id = ctx["job_id"], ctx["parsed_document_id"], ctx["document_file_id"]
    with session_scope() as db:
        update_job(db, job_id, status="deduplicating")
        drafts = db.query(WikiPageDraft).filter(WikiPageDraft.parsed_document_id == parsed_id).all()
        finals = db.query(WikiPageFinal).filter(WikiPageFinal.project_id == ctx["project_id"]).all()
        touched: list[str] = []
        merged = created = 0
        if drafts:
            draft_vecs = get_embedding_service().embed_batch(
                [_page_text(d.entity_name, d.content) for d in drafts], settings.embedding_batch_size
            )
            final_vecs = get_qdrant_client(settings.qdrant_wiki_collection).get_vectors([f.id for f in finals])
            existing = [
                Candidate(f.id, f.entity_type, normalize_name(f.entity_name), final_vecs.get(f.id, [])) for f in finals
            ]
            candidates = [
                Candidate(d.id, d.entity_type, normalize_name(d.entity_name), v) for d, v in zip(drafts, draft_vecs)
            ]
            by_id = {f.id: f for f in finals}
            final_for_draft: dict[str, WikiPageFinal] = {}
            now = ist_now()
            for draft, (kind, target) in zip(drafts, assign_drafts(candidates, existing, settings.wiki_deduplication_threshold)):
                if kind == "new":
                    page = WikiPageFinal(
                        id=f"wiki_{uuid.uuid4().hex[:20]}",
                        project_id=ctx["project_id"],
                        entity_name=draft.entity_name,
                        entity_type=draft.entity_type,
                        content=draft.content,
                        aliases=[],
                        source_facts=list(draft.source_facts or []),
                        merge_info={"source_documents": [doc_id], "merged_from": [], "merge_count": 0},
                        is_published=False,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(page)
                    created += 1
                else:
                    page = by_id[target] if kind == "existing" else final_for_draft[target]
                    _merge_into(page, draft, doc_id)
                    merged += 1
                final_for_draft[draft.id] = page
                draft.is_deduplicated = True
                if page.id not in touched:
                    touched.append(page.id)
        db.commit()
    logger.info("[DEDUP] job=%s: %d new page(s), %d merged into existing", job_id, created, merged)
    return {**ctx, "wiki_new": created, "wiki_merged": merged, "wiki_page_ids": touched}


def _merge_into(page: WikiPageFinal, draft: WikiPageDraft, doc_id: str) -> None:
    aliases = list(page.aliases or [])
    if normalize_name(draft.entity_name) != normalize_name(page.entity_name) and draft.entity_name not in aliases:
        aliases.append(draft.entity_name)
    facts = list(page.source_facts or [])
    facts += [f for f in (draft.source_facts or []) if f not in facts]
    info = dict(page.merge_info or {})
    info["source_documents"] = sorted(set(info.get("source_documents", [])) | {doc_id})
    info["merged_from"] = list(info.get("merged_from", [])) + [draft.id]
    info["merge_count"] = int(info.get("merge_count", 0)) + 1
    page.aliases, page.source_facts, page.merge_info = aliases, facts, info
    page.updated_at = ist_now()


@app.task(base=IngestionTask, stage="indexing_wiki")
def index_wiki_pages(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id = ctx["job_id"]
    ids = ctx.get("wiki_page_ids", [])
    with session_scope() as db:
        update_job(db, job_id, status="indexing_wiki")
        pages = db.query(WikiPageFinal).filter(WikiPageFinal.id.in_(ids)).all() if ids else []
        if pages:
            embedder = get_embedding_service()
            vectors = embedder.embed_batch([_page_text(p.entity_name, p.content) for p in pages], settings.embedding_batch_size)
            store = get_qdrant_client(settings.qdrant_wiki_collection)
            store.store_embeddings_batch(
                [
                    {
                        "chunk_id": p.id,
                        "embedding": v,
                        "metadata": {
                            "wiki_id": p.id,
                            "project_id": p.project_id,
                            "entity_name": p.entity_name,
                            "entity_type": p.entity_type,
                            "source_documents": (p.merge_info or {}).get("source_documents", []),
                            "text": p.content[:1000],
                        },
                    }
                    for p, v in zip(pages, vectors)
                ]
            )
            db.query(EmbeddingsMetadata).filter(EmbeddingsMetadata.wiki_id.in_(ids)).delete(synchronize_session=False)
            now = ist_now()
            for p, v in zip(pages, vectors):
                p.is_published = True
                p.updated_at = now
                db.add(
                    EmbeddingsMetadata(
                        id=f"wemb_{p.id}"[:64],
                        wiki_id=p.id,
                        project_id=p.project_id,
                        embedding_model=embedder.model_name[:50],
                        embedding_dimension=len(v),
                        qdrant_collection=store.collection_name[:50],
                        qdrant_point_id=point_id_for(p.id),
                        created_at=now,
                    )
                )
            db.commit()
        summary = (
            f"{ctx.get('chunk_count', 0)} chunks indexed for search; {ctx.get('fact_count', 0)} facts; "
            f"wiki: {ctx.get('wiki_new', 0)} new page(s), {ctx.get('wiki_merged', 0)} merged into existing pages"
        )
        complete_job(db, ctx, summary)
    logger.info("[WIKI_INDEX] job=%s published %d wiki page(s)", job_id, len(pages))
    return {**ctx, "wiki_indexed": len(pages)}
