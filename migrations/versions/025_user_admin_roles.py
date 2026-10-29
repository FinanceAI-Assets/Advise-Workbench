"""Normalize platform roles to user and admin.

Revision ID: 025_user_admin_roles
Revises: 024_user_roles
"""

from alembic import op

revision = "025_user_admin_roles"
down_revision = "024_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR role = '' OR role IN ('member', 'reviewer')")
    op.execute("UPDATE users SET role = 'admin', is_admin = 1 WHERE is_admin = 1 OR role = 'admin'")


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'member' WHERE role = 'user'")
