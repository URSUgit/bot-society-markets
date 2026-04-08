from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from .database import Database, metadata


@dataclass(slots=True)
class DatabaseCopySummary:
    source_url: str
    target_url: str
    copied_rows: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.copied_rows.values())


def build_alembic_config(database_url: str | None = None) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str((repo_root / "alembic.ini").resolve()))
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(revision: str = "head", *, database_url: str | None = None) -> None:
    command.upgrade(build_alembic_config(database_url), revision)


def copy_database(source_database: Database, target_database: Database, *, truncate_target: bool = True) -> DatabaseCopySummary:
    target_database.initialize()
    copied_rows: dict[str, int] = {}

    with source_database.connect() as source_connection, target_database.connect() as target_connection:
        if truncate_target:
            for table in reversed(metadata.sorted_tables):
                target_connection.execute(table.delete())

        for table in metadata.sorted_tables:
            rows = [dict(row) for row in source_connection.execute(select(table)).mappings().all()]
            if rows:
                target_connection.execute(table.insert(), rows)
            copied_rows[table.name] = len(rows)

    return DatabaseCopySummary(
        source_url=source_database.url,
        target_url=target_database.url,
        copied_rows=copied_rows,
    )
