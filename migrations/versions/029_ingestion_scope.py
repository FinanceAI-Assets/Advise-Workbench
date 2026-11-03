"""Ingestion tables are scoped by a scope id ("library"), not by an engagement project.

Revision ID: 029_ingestion_scope
Revises: 028_merge_heads
Create Date: 2026-10-27
"""

from __future__ import annotations

from alembic import op

revision = "029_ingestion_scope"
down_revision = "028_merge_heads"
branch_labels = None
depends_on = None

# Postgres names unnamed foreign keys <table>_<column>_fkey.
TABLES = (
    "document_jobs",
    "document_files",
    "parsed_documents",
    "chunk_archive",
    "chunk_embeddings",
    "extracted_facts",
    "wiki_pages_draft",
    "wiki_pages_final",
    "embeddings_metadata",
    "in_app_notifications",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite does not enforce these foreign keys
    for table in TABLES:
        op.execute(f'ALTER TABLE IF EXISTS {table} DROP CONSTRAINT IF EXISTS "{table}_project_id_fkey"')


def downgrade() -> None:
    pass  # library rows have no project; restoring the constraint would reject them
