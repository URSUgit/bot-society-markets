"""Add signal provenance and demo workspace fields.

Revision ID: 20260409_02
Revises: 20260409_01
Create Date: 2026-04-09 18:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260409_02"
down_revision = "20260409_01"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _has_column(inspector, "signals", "provider_name"):
        op.add_column("signals", sa.Column("provider_name", sa.String(length=120), nullable=False, server_default="seed-provider"))
    if not _has_column(inspector, "signals", "source_type"):
        op.add_column("signals", sa.Column("source_type", sa.String(length=32), nullable=False, server_default="news"))
    if not _has_column(inspector, "signals", "author_handle"):
        op.add_column("signals", sa.Column("author_handle", sa.String(length=255), nullable=True))
    if not _has_column(inspector, "signals", "engagement_score"):
        op.add_column("signals", sa.Column("engagement_score", sa.Float(), nullable=True))
    if not _has_index(inspector, "signals", "idx_signals_source_type_observed_at"):
        op.create_index("idx_signals_source_type_observed_at", "signals", ["source_type", "observed_at"], unique=False)

    if not _has_column(inspector, "users", "is_demo_user"):
        op.add_column("users", sa.Column("is_demo_user", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE users SET is_demo_user = 1 WHERE slug = 'demo-operator'")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if _has_column(inspector, "users", "is_demo_user"):
        op.drop_column("users", "is_demo_user")
    if _has_index(inspector, "signals", "idx_signals_source_type_observed_at"):
        op.drop_index("idx_signals_source_type_observed_at", table_name="signals")
    if _has_column(inspector, "signals", "engagement_score"):
        op.drop_column("signals", "engagement_score")
    if _has_column(inspector, "signals", "author_handle"):
        op.drop_column("signals", "author_handle")
    if _has_column(inspector, "signals", "source_type"):
        op.drop_column("signals", "source_type")
    if _has_column(inspector, "signals", "provider_name"):
        op.drop_column("signals", "provider_name")
