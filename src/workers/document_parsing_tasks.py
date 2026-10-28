"""Pipeline stages 2 and 3: Docling parsing into parsed_documents, then chunking into chunk_archive."""

from __future__ import annotations

import logging
import time
from importlib.metadata import version
from typing import Any

from docling.exceptions import ConversionError

from src.core.db.models import ChunkArchive, DocumentChunkLink, ParsedDocument
from src.core.db.session import session_scope
from src.core.parsing.docling_parser import get_docling_parser
from src.core.storage.seaweedfs_client import get_seaweedfs_client
from src.core.tz import ist_now
from src.memory.knowledge import practice_ingest as ingest
from src.workers.celery_app import app
from src.workers.pipeline import IngestionTask, PermanentIngestionError, update_job

logger = logging.getLogger(__name__)


@app.task(base=IngestionTask, stage="parsing")
def parse_document_with_docling(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, document_file_id = ctx["job_id"], ctx["document_file_id"]
    with session_scope() as db:
        update_job(db, job_id, status="parsing")

    started = time.monotonic()
    file_bytes = get_seaweedfs_client().get_file(ctx["s3_key"])  # read back from SeaweedFS, not local disk
    try:
        result = get_docling_parser().parse_document(file_bytes, ctx["filename"])
    except ConversionError as e:  # unreadable or unsupported file: retrying cannot help
        raise PermanentIngestionError(f"Docling could not read {ctx['filename']}: {e}") from e
    duration_ms = int((time.monotonic() - started) * 1000)

    full_text = result.pop("full_text")
    parsed_id = f"parsed_{document_file_id}"
    with session_scope() as db:
        parsed = db.get(ParsedDocument, parsed_id) or ParsedDocument(
            id=parsed_id, document_file_id=document_file_id, project_id=ctx["project_id"]
        )
        parsed.full_text = full_text
        parsed.content_json = result
        parsed.page_count = result["page_count"]
        parsed.table_count = result["table_count"]
        parsed.image_count = result["image_count"]
        parsed.parsing_status = "success"
        parsed.parsing_duration_ms = duration_ms
        parsed.parser_version = f"docling {version('docling')}"[:20]
        parsed.error_message = None
        parsed.updated_at = ist_now()
        db.add(parsed)
        update_job(db, job_id, parse_mode="docling", text_content=full_text)

    logger.info(
        "[PARSE] job=%s parsed %s: %d pages, %d tables, %d chars in %dms",
        job_id, ctx["filename"], result["page_count"], result["table_count"], len(full_text), duration_ms,
    )
    return {**ctx, "parsed_document_id": parsed_id, "page_count": result["page_count"]}


def _page_markdown(content: dict[str, Any], full_text: str) -> str:
    """Docling's per-page Markdown joined with ``[Page N]`` markers, so passages keep their page numbers."""
    pages = content.get("pages") or [{"page_number": None, "text": full_text}]
    return "\n\n".join(
        (f"[Page {p['page_number']}]\n" if p.get("page_number") else "") + (p.get("text") or "") for p in pages
    )


@app.task(base=IngestionTask, stage="chunking")
def chunk_parsed_content(ctx: dict[str, Any]) -> dict[str, Any]:
    """One chunker for everything: the Library's section-aware passages (headings, pages, overlap, citations)."""
    job_id, parsed_id, document_file_id = ctx["job_id"], ctx["parsed_document_id"], ctx["document_file_id"]
    with session_scope() as db:
        update_job(db, job_id, status="chunking")
        parsed = db.get(ParsedDocument, parsed_id)
        if parsed is None:
            raise PermanentIngestionError(f"ParsedDocument {parsed_id} not found")
        content = dict(parsed.content_json or {})
        extraction = ingest.blocks_from_markdown(_page_markdown(content, parsed.full_text or ""))
        chunks = ingest.chunk_blocks(extraction["blocks"]) if extraction["readable"] else []
        if not chunks:
            raise PermanentIngestionError(
                "Docling extracted no text. For a scanned PDF set DOCLING_OCR_ENABLED=true and restart the worker."
            )

        # Passages are content-addressed (normalised-text SHA-256): one stored copy per unique text in the library,
        # linked from every version that contains it. Re-runs replace this document's links only.
        db.query(DocumentChunkLink).filter(DocumentChunkLink.document_file_id == document_file_id).delete()
        now = ist_now()
        reused = 0
        known: set[str] = set()
        for number, chunk in enumerate(chunks, start=1):
            chunk_id = passage_id(chunk["sha256"])
            chunk["chunkId"] = chunk_id
            exists = chunk_id in known or db.get(ChunkArchive, chunk_id) is not None
            if not exists:
                db.add(
                    ChunkArchive(
                        id=chunk_id,
                        document_file_id=document_file_id,  # first document that contained the passage
                        parsed_document_id=parsed_id,
                        project_id=ctx["project_id"],
                        chunk_number=number,
                        text=chunk["text"],
                        character_count=len(chunk["text"]),
                        token_estimate=chunk["tokens"],
                        source_type="section",
                        page_number=chunk.get("page"),
                        created_at=now,
                    )
                )
                db.flush()
            reused += exists
            known.add(chunk_id)
            db.add(DocumentChunkLink(document_file_id=document_file_id, chunk_number=number, chunk_id=chunk_id,
                                     page_number=chunk.get("page"), reused=exists, created_at=now))
        # The library_validation stage reads the same blocks and passages (no second extraction).
        parsed.content_json = {
            **content,
            "library": {"blocks": extraction["blocks"], "chunks": chunks, "pages": extraction["pages"]},
        }
        update_job(db, job_id, chunk_count=len(chunks))

    logger.info("[CHUNK] job=%s %d passages: %d new, %d already in the library", job_id, len(chunks),
                len(chunks) - reused, reused)
    return {**ctx, "chunk_count": len(chunks), "reused_chunks": reused}


def passage_id(sha256: str) -> str:
    """Stable id of a passage text across the library (chunk_archive.id)."""
    return f"pas_{sha256[:40]}"
