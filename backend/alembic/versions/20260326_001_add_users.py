"""add users table

Revision ID: 20260326001
Revises:
Create Date: 2026-03-26 09:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260326001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sub", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sub"),
    )


def downgrade() -> None:
    op.drop_table("users")
