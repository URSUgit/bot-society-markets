"""Add social discovery run ledger.

Revision ID: 20260514_01
Revises: 20260424_03
Create Date: 2026-05-14 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260514_01"
down_revision = "20260424_03"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("social_discovery_runs"):
        op.create_table(
            "social_discovery_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("provider", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("youtube_configured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("started_at", sa.String(length=64), nullable=False),
            sa.Column("completed_at", sa.String(length=64), nullable=False),
        )

    inspector = sa.inspect(op.get_bind())
    if not _has_index(inspector, "social_discovery_runs", "idx_social_discovery_runs_started"):
        op.create_index("idx_social_discovery_runs_started", "social_discovery_runs", ["started_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("social_discovery_runs"):
        if _has_index(inspector, "social_discovery_runs", "idx_social_discovery_runs_started"):
            op.drop_index("idx_social_discovery_runs_started", table_name="social_discovery_runs")
        op.drop_table("social_discovery_runs")
