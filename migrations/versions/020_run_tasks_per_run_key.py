"""key run_tasks on (id, run_id) so task ids can repeat across runs

Revision ID: 020_run_tasks_per_run_key
Revises: 019_run_admission_index
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "020_run_tasks_per_run_key"
down_revision = "019_run_admission_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "run_tasks" not in inspector.get_table_names():
        return
    pk = inspector.get_pk_constraint("run_tasks")
    if set(pk.get("constrained_columns") or []) == {"id", "run_id"}:
        return
    if bind.dialect.name == "sqlite":
        from src.core.db.session import rebuild_sqlite_run_tasks_key

        rebuild_sqlite_run_tasks_key(bind.engine)
        return
    op.drop_constraint(pk.get("name") or "run_tasks_pkey", "run_tasks", type_="primary")
    op.create_primary_key("run_tasks_pkey", "run_tasks", ["id", "run_id"])


def downgrade() -> None:
    # Not reversible once two runs share a task id.
    pass
