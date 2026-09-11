"""Add strategy bot deployment controls.

Revision ID: 20260909_01
Revises: 20260908_01
Create Date: 2026-09-09 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260909_01"
down_revision = "20260908_01"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("strategy_deployments"):
        op.create_table(
            "strategy_deployments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("execution_mode", sa.String(length=16), nullable=False, server_default="paper"),
            sa.Column("venue", sa.String(length=64), nullable=False, server_default="paper"),
            sa.Column("max_notional_usd", sa.Float()),
            sa.Column("max_position_pct", sa.Float(), nullable=False, server_default="0.25"),
            sa.Column("daily_loss_limit_pct", sa.Float(), nullable=False, server_default="0.05"),
            sa.Column("max_open_positions", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("min_backtest_win_rate", sa.Float(), nullable=False, server_default="0.45"),
            sa.Column("kill_switch_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("last_backtest_run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id", ondelete="SET NULL")),
            sa.Column("last_order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL")),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text()),
            sa.Column("created_at", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.String(length=64), nullable=False),
            sa.Column("stopped_at", sa.String(length=64)),
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("strategy_deployment_events"):
        op.create_table(
            "strategy_deployment_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("strategy_deployments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("payload_json", sa.Text()),
            sa.Column("created_at", sa.String(length=64), nullable=False),
        )

    inspector = sa.inspect(op.get_bind())
    if not _has_index(inspector, "strategy_deployments", "idx_strategy_deployments_user_updated"):
        op.create_index("idx_strategy_deployments_user_updated", "strategy_deployments", ["user_slug", "updated_at"])
    if not _has_index(inspector, "strategy_deployments", "idx_strategy_deployments_status_updated"):
        op.create_index("idx_strategy_deployments_status_updated", "strategy_deployments", ["status", "updated_at"])
    if not _has_index(inspector, "strategy_deployments", "idx_strategy_deployments_strategy_status"):
        op.create_index("idx_strategy_deployments_strategy_status", "strategy_deployments", ["strategy_id", "status"])
    if not _has_index(inspector, "strategy_deployment_events", "idx_strategy_deployment_events_deployment_created"):
        op.create_index(
            "idx_strategy_deployment_events_deployment_created",
            "strategy_deployment_events",
            ["deployment_id", "created_at"],
        )
    if not _has_index(inspector, "strategy_deployment_events", "idx_strategy_deployment_events_user_created"):
        op.create_index("idx_strategy_deployment_events_user_created", "strategy_deployment_events", ["user_slug", "created_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("strategy_deployment_events"):
        if _has_index(inspector, "strategy_deployment_events", "idx_strategy_deployment_events_user_created"):
            op.drop_index("idx_strategy_deployment_events_user_created", table_name="strategy_deployment_events")
        if _has_index(inspector, "strategy_deployment_events", "idx_strategy_deployment_events_deployment_created"):
            op.drop_index("idx_strategy_deployment_events_deployment_created", table_name="strategy_deployment_events")
        op.drop_table("strategy_deployment_events")

    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("strategy_deployments"):
        if _has_index(inspector, "strategy_deployments", "idx_strategy_deployments_strategy_status"):
            op.drop_index("idx_strategy_deployments_strategy_status", table_name="strategy_deployments")
        if _has_index(inspector, "strategy_deployments", "idx_strategy_deployments_status_updated"):
            op.drop_index("idx_strategy_deployments_status_updated", table_name="strategy_deployments")
        if _has_index(inspector, "strategy_deployments", "idx_strategy_deployments_user_updated"):
            op.drop_index("idx_strategy_deployments_user_updated", table_name="strategy_deployments")
        op.drop_table("strategy_deployments")
