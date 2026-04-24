"""Add append-only audit logs.

Revision ID: 20260424_01
Revises: 20260409_03
Create Date: 2026-04-24 14:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_01"
down_revision = "20260409_03"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("actor_user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="SET NULL")),
            sa.Column("action", sa.String(length=120), nullable=False),
            sa.Column("resource_type", sa.String(length=120), nullable=False),
            sa.Column("resource_id", sa.String(length=255)),
            sa.Column("ip_address", sa.String(length=64)),
            sa.Column("user_agent", sa.Text()),
            sa.Column("before_state_json", sa.Text()),
            sa.Column("after_state_json", sa.Text()),
            sa.Column("created_at", sa.String(length=64), nullable=False),
        )
    inspector = sa.inspect(op.get_bind())
    if not _has_index(inspector, "audit_logs", "idx_audit_logs_actor_created"):
        op.create_index("idx_audit_logs_actor_created", "audit_logs", ["actor_user_slug", "created_at"])
    if not _has_index(inspector, "audit_logs", "idx_audit_logs_resource_created"):
        op.create_index("idx_audit_logs_resource_created", "audit_logs", ["resource_type", "resource_id", "created_at"])
    if not _has_index(inspector, "audit_logs", "idx_audit_logs_action_created"):
        op.create_index("idx_audit_logs_action_created", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("audit_logs"):
        if _has_index(inspector, "audit_logs", "idx_audit_logs_action_created"):
            op.drop_index("idx_audit_logs_action_created", table_name="audit_logs")
        if _has_index(inspector, "audit_logs", "idx_audit_logs_resource_created"):
            op.drop_index("idx_audit_logs_resource_created", table_name="audit_logs")
        if _has_index(inspector, "audit_logs", "idx_audit_logs_actor_created"):
            op.drop_index("idx_audit_logs_actor_created", table_name="audit_logs")
        op.drop_table("audit_logs")
