"""add listening history tables and polling config to spotify_accounts

Revision ID: 20260326005
Revises: 20260326004
Create Date: 2026-03-26 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260326005"
down_revision = "20260326004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── artists ───────────────────────────────────────────────────────────────
    op.create_table(
        "artists",
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider", "external_id"),
    )

    # ── albums ────────────────────────────────────────────────────────────────
    op.create_table(
        "albums",
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider", "external_id"),
    )

    # ── tracks ────────────────────────────────────────────────────────────────
    op.create_table(
        "tracks",
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("album_provider", sa.String(50), nullable=True),
        sa.Column("album_external_id", sa.String(255), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("media_type", sa.String(50), nullable=False, server_default="track"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["album_provider", "album_external_id"],
            ["albums.provider", "albums.external_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("provider", "external_id"),
    )

    # ── track_artists (junction) ───────────────────────────────────────────────
    op.create_table(
        "track_artists",
        sa.Column("track_provider", sa.String(50), nullable=False),
        sa.Column("track_external_id", sa.String(255), nullable=False),
        sa.Column("artist_provider", sa.String(50), nullable=False),
        sa.Column("artist_external_id", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(
            ["track_provider", "track_external_id"],
            ["tracks.provider", "tracks.external_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["artist_provider", "artist_external_id"],
            ["artists.provider", "artists.external_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "track_provider", "track_external_id", "artist_provider", "artist_external_id"
        ),
    )

    # ── play_events ────────────────────────────────────────────────────────────
    op.create_table(
        "play_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("streaming_account_id", sa.Uuid(), nullable=False),
        sa.Column("track_provider", sa.String(50), nullable=False),
        sa.Column("track_external_id", sa.String(255), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["streaming_account_id"],
            ["spotify_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["track_provider", "track_external_id"],
            ["tracks.provider", "tracks.external_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "streaming_account_id",
            "track_provider",
            "track_external_id",
            "played_at",
            name="uq_play_events_account_track_time",
        ),
    )

    # ── polling config columns on spotify_accounts ────────────────────────────
    op.add_column(
        "spotify_accounts",
        sa.Column(
            "poll_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.add_column(
        "spotify_accounts",
        sa.Column(
            "polling_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "spotify_accounts",
        sa.Column(
            "last_polled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Remove polling config columns from spotify_accounts
    op.drop_column("spotify_accounts", "last_polled_at")
    op.drop_column("spotify_accounts", "polling_enabled")
    op.drop_column("spotify_accounts", "poll_interval_minutes")

    # Drop new tables in reverse dependency order
    op.drop_table("play_events")
    op.drop_table("track_artists")
    op.drop_table("tracks")
    op.drop_table("albums")
    op.drop_table("artists")
