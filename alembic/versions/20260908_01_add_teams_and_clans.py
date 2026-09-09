"""Add teams and clans workspace tables.

Revision ID: 20260908_01
Revises: 20260514_01
Create Date: 2026-09-08 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260908_01"
down_revision = "20260514_01"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("teams"):
        op.create_table(
            "teams",
            sa.Column("slug", sa.String(length=120), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False, server_default="team"),
            sa.Column("description", sa.Text()),
            sa.Column("owner_user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("join_code", sa.String(length=32), nullable=False, unique=True),
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.String(length=64), nullable=False),
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("team_memberships"):
        op.create_table(
            "team_memberships",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("team_slug", sa.String(length=120), sa.ForeignKey("teams.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("user_slug", sa.String(length=120), sa.ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False, server_default="member"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("joined_at", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.String(length=64), nullable=False),
            sa.UniqueConstraint("team_slug", "user_slug", name="uq_team_memberships_team_user"),
        )

    inspector = sa.inspect(op.get_bind())
    if not _has_index(inspector, "teams", "idx_teams_owner_updated"):
        op.create_index("idx_teams_owner_updated", "teams", ["owner_user_slug", "updated_at"])
    if not _has_index(inspector, "team_memberships", "idx_team_memberships_user_updated"):
        op.create_index("idx_team_memberships_user_updated", "team_memberships", ["user_slug", "updated_at"])
    if not _has_index(inspector, "team_memberships", "idx_team_memberships_team_active"):
        op.create_index(
            "idx_team_memberships_team_active",
            "team_memberships",
            ["team_slug", "is_active", "updated_at"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("team_memberships"):
        if _has_index(inspector, "team_memberships", "idx_team_memberships_team_active"):
            op.drop_index("idx_team_memberships_team_active", table_name="team_memberships")
        if _has_index(inspector, "team_memberships", "idx_team_memberships_user_updated"):
            op.drop_index("idx_team_memberships_user_updated", table_name="team_memberships")
        op.drop_table("team_memberships")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("teams"):
        if _has_index(inspector, "teams", "idx_teams_owner_updated"):
            op.drop_index("idx_teams_owner_updated", table_name="teams")
        op.drop_table("teams")
