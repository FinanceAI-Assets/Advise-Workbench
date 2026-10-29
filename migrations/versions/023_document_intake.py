"""Add document_files, intake_metadata, and intake_metrics tables

Revision ID: 023_document_intake
Revises: 022_document_jobs
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "023_document_intake"
down_revision = "022_document_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create document intake schema."""

    # Table 1: document_files - Original file metadata
    op.create_table(
        "document_files",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_id", sa.String(255), sa.ForeignKey("document_jobs.job_id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_format", sa.String(20), nullable=True),  # pdf, docx, xlsx, etc
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column("seaweedfs_file_id", sa.String(255), nullable=True),
        sa.Column("seaweedfs_volume_id", sa.Integer(), nullable=True),
        sa.Column("upload_source", sa.String(50), nullable=True, server_default="api_upload"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Indexes for common queries
    op.create_index("ix_document_files_project_id", "document_files", ["project_id"])
    op.create_index("ix_document_files_job_id", "document_files", ["job_id"])
    op.create_index("ix_document_files_sha256", "document_files", ["sha256_hash"])
    op.create_index("ix_document_files_seaweedfs_id", "document_files", ["seaweedfs_file_id"])
    op.create_index("ix_document_files_created", "document_files", ["created_at"])

    # Table 2: document_intake_metadata - Additional file properties
    op.create_table(
        "document_intake_metadata",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_file_id", sa.String(64), sa.ForeignKey("document_files.id"), nullable=False),
        sa.Column("extracted_pages", sa.Integer(), nullable=True),  # Page count for PDFs
        sa.Column("has_images", sa.Boolean(), server_default="false"),
        sa.Column("has_tables", sa.Boolean(), server_default="false"),
        sa.Column("has_embedded_files", sa.Boolean(), server_default="false"),
        sa.Column("language_detected", sa.String(10), nullable=True),  # en, fr, de, etc
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_document_intake_metadata_file_id", "document_intake_metadata", ["document_file_id"])
    op.create_index("ix_document_intake_metadata_language", "document_intake_metadata", ["language_detected"])

    # Table 3: document_intake_metrics - Performance monitoring
    op.create_table(
        "document_intake_metrics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("upload_duration_ms", sa.Integer(), nullable=True),  # Time to SeaweedFS
        sa.Column("validation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("total_files_uploaded", sa.Integer(), server_default="1"),
        sa.Column("total_bytes_uploaded", sa.BigInteger(), server_default="0"),
        sa.Column("failure_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_document_intake_metrics_project", "document_intake_metrics", ["project_id"])
    op.create_index("ix_document_intake_metrics_created", "document_intake_metrics", ["created_at"])
    op.create_index("ix_document_intake_metrics_project_time", "document_intake_metrics", ["project_id", "created_at"])


def downgrade() -> None:
    """Drop document intake schema."""

    # Drop metrics table
    op.drop_index("ix_document_intake_metrics_project_time", table_name="document_intake_metrics")
    op.drop_index("ix_document_intake_metrics_created", table_name="document_intake_metrics")
    op.drop_index("ix_document_intake_metrics_project", table_name="document_intake_metrics")
    op.drop_table("document_intake_metrics")

    # Drop metadata table
    op.drop_index("ix_document_intake_metadata_language", table_name="document_intake_metadata")
    op.drop_index("ix_document_intake_metadata_file_id", table_name="document_intake_metadata")
    op.drop_table("document_intake_metadata")

    # Drop files table
    op.drop_index("ix_document_files_created", table_name="document_files")
    op.drop_index("ix_document_files_seaweedfs_id", table_name="document_files")
    op.drop_index("ix_document_files_sha256", table_name="document_files")
    op.drop_index("ix_document_files_job_id", table_name="document_files")
    op.drop_index("ix_document_files_project_id", table_name="document_files")
    op.drop_table("document_files")
