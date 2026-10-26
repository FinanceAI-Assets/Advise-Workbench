"""Pipeline stages 2 and 3: Docling parsing into parsed_documents, then chunking into chunk_archive."""

from __future__ import annotations

import logging
import time
from importlib.metadata import version
from typing import Any

from docling.exceptions import ConversionError

from src.core.config import settings
from src.core.db.models import ChunkArchive, ChunkEmbedding, ParsedDocument
from src.core.db.session import session_scope
from src.core.parsing.chunking_service import get_chunking_service
from src.core.parsing.docling_parser import get_docling_parser
from src.core.storage.seaweedfs_client import get_seaweedfs_client
from src.core.tz import ist_now
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


@app.task(base=IngestionTask, stage="chunking")
def chunk_parsed_content(ctx: dict[str, Any]) -> dict[str, Any]:
    job_id, parsed_id, document_file_id = ctx["job_id"], ctx["parsed_document_id"], ctx["document_file_id"]
    with session_scope() as db:
        update_job(db, job_id, status="chunking")
        parsed = db.get(ParsedDocument, parsed_id)
        if parsed is None:
            raise PermanentIngestionError(f"ParsedDocument {parsed_id} not found")
        content = dict(parsed.content_json or {})
        content["full_text"] = parsed.full_text or ""
        chunks = get_chunking_service(settings.chunk_size_characters, settings.chunk_overlap_characters)
        groups = chunks.create_chunks_from_parsed(content)
        all_chunks = groups["main_text"] + groups["table_text"] + groups["image_text"]
        if not all_chunks:
            raise PermanentIngestionError(
                "Docling extracted no text. For a scanned PDF set DOCLING_OCR_ENABLED=true and restart the worker."
            )

        # Re-runs replace the document's chunks instead of adding duplicates.
        db.query(ChunkEmbedding).filter(ChunkEmbedding.document_file_id == document_file_id).delete()
        db.query(ChunkArchive).filter(ChunkArchive.document_file_id == document_file_id).delete()
        now = ist_now()
        for chunk in all_chunks:
            source = chunk.get("source", {})
            db.add(
                ChunkArchive(
                    id=f"{document_file_id}_c{chunk['chunk_number']:05d}",
                    document_file_id=document_file_id,
                    parsed_document_id=parsed_id,
                    project_id=ctx["project_id"],
                    chunk_number=chunk["chunk_number"],
                    text=chunk["text"],
                    character_count=chunk["character_count"],
                    token_estimate=chunk["token_estimate"],
                    source_type=source.get("source_type"),
                    page_number=source.get("page_number"),
                    table_index=source.get("table_index"),
                    image_index=source.get("image_index"),
                    start_char=chunk.get("start_char"),
                    end_char=chunk.get("end_char"),
                    created_at=now,
                )
            )
        update_job(db, job_id, chunk_count=len(all_chunks))

    logger.info(
        "[CHUNK] job=%s stored %d chunks (%d text, %d table)",
        job_id, len(all_chunks), len(groups["main_text"]), len(groups["table_text"]),
    )
    return {**ctx, "chunk_count": len(all_chunks)}
