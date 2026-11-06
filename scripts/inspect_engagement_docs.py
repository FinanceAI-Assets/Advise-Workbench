"""Show what the ingestion pipeline stored for an engagement's documents: SeaweedFS, Postgres and Qdrant.

Read-only. Uses the same `.env` as the app.

    .\\.venv\\Scripts\\python.exe scripts/inspect_engagement_docs.py --project p_3ac35e5cff
    .\\.venv\\Scripts\\python.exe scripts/inspect_engagement_docs.py --project p_3ac35e5cff --file workshop-notes.txt --chunks 5

For every document (latest version first): the ingestion job and its stage, the SeaweedFS object, the Postgres rows
(document_files, parsed_documents, chunk_archive, chunk_embeddings) and the Qdrant points of the engagement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import settings  # noqa: E402
from src.core.db.models import (  # noqa: E402
    ChunkArchive,
    ChunkEmbedding,
    DocumentChunkLink,
    DocumentFile,
    DocumentJob,
    ParsedDocument,
)
from src.core.db.session import session_scope  # noqa: E402


def _short(text: str | None, limit: int = 100) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _seaweedfs(key: str | None) -> str:
    if not key:
        return "no object recorded"
    try:
        from src.core.storage.seaweedfs_client import get_seaweedfs_client

        head = get_seaweedfs_client().head_file(key)
    except Exception as e:  # report, keep going
        return f"s3://{settings.s3_bucket}/{key}  (could not check: {type(e).__name__}: {_short(str(e), 80)})"
    if head is None:
        return f"s3://{settings.s3_bucket}/{key}  MISSING"
    return f"s3://{settings.s3_bucket}/{key}  ({head['size']} bytes, {head['content_type']})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", required=True, help="engagement (project) id, e.g. p_3ac35e5cff")
    ap.add_argument("--file", help="only this file name")
    ap.add_argument("--chunks", type=int, default=3, help="passages to print per document (default 3)")
    args = ap.parse_args()
    pid = args.project

    print(f"Engagement {pid}")
    print(f"  Postgres: {settings.database_url.split('@')[-1].split('?')[0]}")
    try:
        from src.core.vector_db.qdrant_client import get_qdrant_client

        store = get_qdrant_client()
        print(f"  Qdrant:   {store.collection_name}: {store.count(project_id=pid)} points with project_id={pid}")
    except Exception as e:
        store = None
        print(f"  Qdrant:   not reachable ({type(e).__name__}: {_short(str(e), 80)})")
    print()

    with session_scope() as db:
        jobs = db.query(DocumentJob).filter(DocumentJob.project_id == pid)
        if args.file:
            jobs = jobs.filter(DocumentJob.filename == args.file)
        jobs = jobs.order_by(DocumentJob.filename, DocumentJob.created_at.desc()).all()
        if not jobs:
            print("No ingestion jobs: nothing uploaded since the pipeline was enabled (use POST /api/documents/reindex).")
            return 0
        for job in jobs:
            doc = db.query(DocumentFile).filter(DocumentFile.job_id == job.job_id).first()
            print(f"== {job.filename}   job {job.job_id}")
            print(f"   status:     {job.status}" + (f" (failed at {job.failed_stage}: {_short(job.error_message, 160)})"
                                                    if job.status == "failed" else ""))
            print(f"   created:    {job.created_at}   completed: {job.completed_at or '-'}")
            if job.parse_mode == "unchanged":
                print("   content unchanged since an earlier job: nothing stored again")
            if doc is None:
                print("   SeaweedFS:  not stored by the worker yet\n")
                continue
            print(f"   SeaweedFS:  {_seaweedfs(doc.seaweedfs_file_id)}")
            parsed = db.query(ParsedDocument).filter(ParsedDocument.document_file_id == doc.id).first()
            print(f"   Postgres:   document_files {doc.id} ({doc.file_size_bytes} bytes, sha256 {str(doc.sha256_hash)[:12]})")
            if parsed is not None:
                print(f"               parsed_documents {parsed.id}: {parsed.page_count} pages, {parsed.table_count} tables, "
                      f"{len(parsed.full_text or '')} chars ({parsed.parser_version})")
            links = (db.query(DocumentChunkLink, ChunkArchive)
                     .join(ChunkArchive, ChunkArchive.id == DocumentChunkLink.chunk_id)
                     .filter(DocumentChunkLink.document_file_id == doc.id)
                     .order_by(DocumentChunkLink.chunk_number).all())
            ids = [c.id for _, c in links]
            embeddings = db.query(ChunkEmbedding).filter(ChunkEmbedding.chunk_id.in_(ids)).all() if ids else []
            dims = {e.embedding_dimension for e in embeddings}
            models = {e.model_name for e in embeddings}
            print(f"               chunk_archive: {len(links)} passages; chunk_embeddings: {len(embeddings)} "
                  f"(dimension {', '.join(map(str, dims)) or '-'}, model {', '.join(models) or '-'})")
            if store is not None:
                try:
                    print(f"   Qdrant:     {store.count(document_id=doc.id)} points for this document in {store.collection_name}")
                except Exception as e:
                    print(f"   Qdrant:     could not count ({type(e).__name__})")
            for link, chunk in links[: max(args.chunks, 0)]:
                page = f"page {link.page_number}" if link.page_number else "no page"
                print(f"     #{link.chunk_number} {chunk.id} ({page}, {chunk.character_count} chars): {_short(chunk.text)}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
