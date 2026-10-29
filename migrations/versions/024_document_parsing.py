"""Add parsed_documents and chunk_archive tables for Stage 1.2

Revision ID: 024_document_parsing
Revises: 023_document_intake
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "024_document_parsing"
down_revision = "023_document_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create document parsing schema."""

    # Table 1: parsed_documents - Docling parser output
    op.create_table(
        "parsed_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_file_id", sa.String(64), sa.ForeignKey("document_files.id"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=True),  # Entire extracted text
        sa.Column("content_json", sa.JSON(), nullable=True),  # Structured content
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("table_count", sa.Integer(), default=0),
        sa.Column("image_count", sa.Integer(), default=0),
        sa.Column("parsing_status", sa.String(20), default="pending"),  # pending, success, failed
        sa.Column("parsing_duration_ms", sa.Integer(), nullable=True),
        sa.Column("parser_version", sa.String(20), nullable=True),  # docling version
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_parsed_documents_file_id", "parsed_documents", ["document_file_id"])
    op.create_index("ix_parsed_documents_project_id", "parsed_documents", ["project_id"])
    op.create_index("ix_parsed_documents_status", "parsed_documents", ["parsing_status"])
    op.create_index("ix_parsed_documents_created", "parsed_documents", ["created_at"])

    # Table 2: chunk_archive - Semantic chunks for embedding
    op.create_table(
        "chunk_archive",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_file_id", sa.String(64), sa.ForeignKey("document_files.id"), nullable=False),
        sa.Column("parsed_document_id", sa.String(64), sa.ForeignKey("parsed_documents.id"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("chunk_number", sa.Integer(), nullable=False),  # Sequential chunk number
        sa.Column("text", sa.Text(), nullable=False),  # Chunk content
        sa.Column("character_count", sa.Integer(), nullable=True),
        sa.Column("token_estimate", sa.Integer(), nullable=True),  # ~4 chars per token
        sa.Column("source_type", sa.String(20), nullable=True),  # main_text, table, image
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("table_index", sa.Integer(), nullable=True),  # If from table
        sa.Column("image_index", sa.Integer(), nullable=True),  # If from image
        sa.Column("bbox", sa.JSON(), nullable=True),  # Bounding box coordinates
        sa.Column("start_char", sa.Integer(), nullable=True),  # Position in full_text
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_chunk_archive_file_id", "chunk_archive", ["document_file_id"])
    op.create_index("ix_chunk_archive_parsed_id", "chunk_archive", ["parsed_document_id"])
    op.create_index("ix_chunk_archive_project_id", "chunk_archive", ["project_id"])
    op.create_index("ix_chunk_archive_source_type", "chunk_archive", ["source_type"])
    op.create_index("ix_chunk_archive_created", "chunk_archive", ["created_at"])
    # Composite index for efficient range queries
    op.create_index("ix_chunk_archive_file_chunk", "chunk_archive", ["document_file_id", "chunk_number"])

    # Table 3: chunk_metrics - Performance tracking for parsing
    op.create_table(
        "chunk_metrics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("parsing_duration_ms", sa.Integer(), nullable=True),  # Docling parsing time
        sa.Column("chunking_duration_ms", sa.Integer(), nullable=True),  # Chunking time
        sa.Column("total_documents_parsed", sa.Integer(), default=0),
        sa.Column("total_chunks_created", sa.Integer(), default=0),
        sa.Column("avg_chunk_size", sa.Integer(), nullable=True),
        sa.Column("failure_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_chunk_metrics_project", "chunk_metrics", ["project_id"])
    op.create_index("ix_chunk_metrics_created", "chunk_metrics", ["created_at"])
    op.create_index("ix_chunk_metrics_project_time", "chunk_metrics", ["project_id", "created_at"])


def downgrade() -> None:
    """Drop document parsing schema."""

    # Drop metrics table
    op.drop_index("ix_chunk_metrics_project_time", table_name="chunk_metrics")
    op.drop_index("ix_chunk_metrics_created", table_name="chunk_metrics")
    op.drop_index("ix_chunk_metrics_project", table_name="chunk_metrics")
    op.drop_table("chunk_metrics")

    # Drop chunk archive table
    op.drop_index("ix_chunk_archive_file_chunk", table_name="chunk_archive")
    op.drop_index("ix_chunk_archive_created", table_name="chunk_archive")
    op.drop_index("ix_chunk_archive_source_type", table_name="chunk_archive")
    op.drop_index("ix_chunk_archive_project_id", table_name="chunk_archive")
    op.drop_index("ix_chunk_archive_parsed_id", table_name="chunk_archive")
    op.drop_index("ix_chunk_archive_file_id", table_name="chunk_archive")
    op.drop_table("chunk_archive")

    # Drop parsed documents table
    op.drop_index("ix_parsed_documents_created", table_name="parsed_documents")
    op.drop_index("ix_parsed_documents_status", table_name="parsed_documents")
    op.drop_index("ix_parsed_documents_project_id", table_name="parsed_documents")
    op.drop_index("ix_parsed_documents_file_id", table_name="parsed_documents")
    op.drop_table("parsed_documents")
