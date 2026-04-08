"""Create initial Bot Society Markets schema.

Revision ID: 20260409_01
Revises:
Create Date: 2026-04-09 15:00:00
"""
from __future__ import annotations

from alembic import op

from api.app.database import metadata

# revision identifiers, used by Alembic.
revision = "20260409_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
