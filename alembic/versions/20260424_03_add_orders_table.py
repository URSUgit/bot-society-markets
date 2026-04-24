"""Add normalized trading orders table.

Revision ID: 20260424_03
Revises: 20260424_02
Create Date: 2026-04-24 21:05:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_03"
down_revision = "20260424_02"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("predictions.id", ondelete="SET NULL")),
            sa.Column("venue", sa.String(length=64), nullable=False),
            sa.Column("asset", sa.String(length=16), nullable=False),
            sa.Column("side", sa.String(length=16), nullable=False),
            sa.Column("order_type", sa.String(length=16), nullable=False),
            sa.Column("is_paper", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("notional_usd", sa.Float(), nullable=False),
            sa.Column("price", sa.Float()),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("filled_quantity", sa.Float(), nullable=False, server_default="0"),
            sa.Column("avg_fill_price", sa.Float()),
            sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
            sa.Column("fee_currency", sa.String(length=16), nullable=False, server_default="USD"),
            sa.Column("exchange_order_id", sa.String(length=255)),
            sa.Column("rejection_reason", sa.Text()),
            sa.Column("submitted_at", sa.String(length=64), nullable=False),
            sa.Column("filled_at", sa.String(length=64)),
            sa.Column("cancelled_at", sa.String(length=64)),
            sa.Column("metadata_json", sa.Text()),
        )

    inspector = sa.inspect(op.get_bind())
    if not _has_index(inspector, "orders", "idx_orders_user_submitted"):
        op.create_index("idx_orders_user_submitted", "orders", ["user_slug", "submitted_at"])
    if not _has_index(inspector, "orders", "idx_orders_status_submitted"):
        op.create_index("idx_orders_status_submitted", "orders", ["status", "submitted_at"])
    if not _has_index(inspector, "orders", "idx_orders_asset_submitted"):
        op.create_index("idx_orders_asset_submitted", "orders", ["asset", "submitted_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("orders"):
        if _has_index(inspector, "orders", "idx_orders_asset_submitted"):
            op.drop_index("idx_orders_asset_submitted", table_name="orders")
        if _has_index(inspector, "orders", "idx_orders_status_submitted"):
            op.drop_index("idx_orders_status_submitted", table_name="orders")
        if _has_index(inspector, "orders", "idx_orders_user_submitted"):
            op.drop_index("idx_orders_user_submitted", table_name="orders")
        op.drop_table("orders")
