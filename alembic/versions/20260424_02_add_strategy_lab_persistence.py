"""Add persisted Strategy Lab strategies and backtest runs.

Revision ID: 20260424_02
Revises: 20260424_01
Create Date: 2026-04-24 20:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_02"
down_revision = "20260424_01"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("strategies"):
        op.create_table(
            "strategies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("config_json", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.String(length=64), nullable=False),
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("backtest_runs"):
        op.create_table(
            "backtest_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("asset", sa.String(length=16), nullable=False),
            sa.Column("strategy_key", sa.String(length=64), nullable=False),
            sa.Column("lookback_years", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="complete"),
            sa.Column("started_at", sa.String(length=64), nullable=False),
            sa.Column("completed_at", sa.String(length=64)),
            sa.Column("summary_json", sa.Text(), nullable=False),
            sa.Column("result_json", sa.Text()),
            sa.Column("error_message", sa.Text()),
        )

    inspector = sa.inspect(op.get_bind())
    if not _has_index(inspector, "strategies", "idx_strategies_user_updated"):
        op.create_index("idx_strategies_user_updated", "strategies", ["user_slug", "updated_at"])
    if not _has_index(inspector, "backtest_runs", "idx_backtest_runs_user_completed"):
        op.create_index("idx_backtest_runs_user_completed", "backtest_runs", ["user_slug", "completed_at"])
    if not _has_index(inspector, "backtest_runs", "idx_backtest_runs_strategy_completed"):
        op.create_index("idx_backtest_runs_strategy_completed", "backtest_runs", ["strategy_id", "completed_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("backtest_runs"):
        if _has_index(inspector, "backtest_runs", "idx_backtest_runs_strategy_completed"):
            op.drop_index("idx_backtest_runs_strategy_completed", table_name="backtest_runs")
        if _has_index(inspector, "backtest_runs", "idx_backtest_runs_user_completed"):
            op.drop_index("idx_backtest_runs_user_completed", table_name="backtest_runs")
        op.drop_table("backtest_runs")

    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("strategies"):
        if _has_index(inspector, "strategies", "idx_strategies_user_updated"):
            op.drop_index("idx_strategies_user_updated", table_name="strategies")
        op.drop_table("strategies")
