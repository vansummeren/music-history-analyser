"""Add app_logs table and poll_schedule column.

Revision ID: 20260406006
Revises: 20260326005
Create Date: 2026-04-06

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260406006"
down_revision = "20260326005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── app_logs table ───────────────────────────────────────────────────────
    op.create_table(
        "app_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("logger_name", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_logs_created_at", "app_logs", ["created_at"])
    op.create_index("ix_app_logs_level", "app_logs", ["level"])
    op.create_index("ix_app_logs_service", "app_logs", ["service"])

    # ── poll_schedule column on spotify_accounts ─────────────────────────────
    op.add_column(
        "spotify_accounts",
        sa.Column("poll_schedule", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("spotify_accounts", "poll_schedule")
    op.drop_index("ix_app_logs_service", table_name="app_logs")
    op.drop_index("ix_app_logs_level", table_name="app_logs")
    op.drop_index("ix_app_logs_created_at", table_name="app_logs")
    op.drop_table("app_logs")
