"""Add explicit platform roles to users.

Revision ID: 024_user_roles
Revises: 023_workbench_ui
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "024_user_roles"
down_revision = "023_workbench_ui"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(32), nullable=True, server_default="member"))
    op.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
    op.execute("UPDATE users SET role = 'member' WHERE role IS NULL OR role = ''")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
