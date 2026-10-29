"""Repair role column for databases incorrectly marked at revision 025.

Revision ID: 026_repair_user_role_schema
Revises: 025_user_admin_roles
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "026_repair_user_role_schema"
down_revision = "025_user_admin_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "role" not in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("role", sa.String(32), nullable=True, server_default="user"))
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR role = '' OR role IN ('member', 'reviewer')")
    op.execute("UPDATE users SET role = 'admin', is_admin = 1 WHERE is_admin = 1 OR role = 'admin'")


def downgrade() -> None:
    # The preceding migrations own the role column and its normal role values.
    pass
