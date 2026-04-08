"""Add signal quality scoring fields.

Revision ID: 20260409_03
Revises: 20260409_02
Create Date: 2026-04-09 23:45:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260409_03"
down_revision = "20260409_02"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _has_column(inspector, "signals", "provider_trust_score"):
        op.add_column("signals", sa.Column("provider_trust_score", sa.Float(), nullable=False, server_default="0.7"))
    if not _has_column(inspector, "signals", "freshness_score"):
        op.add_column("signals", sa.Column("freshness_score", sa.Float(), nullable=False, server_default="0.7"))
    if not _has_column(inspector, "signals", "source_quality_score"):
        op.add_column("signals", sa.Column("source_quality_score", sa.Float(), nullable=False, server_default="0.7"))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if _has_column(inspector, "signals", "source_quality_score"):
        op.drop_column("signals", "source_quality_score")
    if _has_column(inspector, "signals", "freshness_score"):
        op.drop_column("signals", "freshness_score")
    if _has_column(inspector, "signals", "provider_trust_score"):
        op.drop_column("signals", "provider_trust_score")
