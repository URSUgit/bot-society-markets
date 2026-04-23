from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select

from .database import Database, metadata


@dataclass(slots=True)
class DatabaseCopySummary:
    source_url: str
    target_url: str
    copied_rows: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.copied_rows.values())


@dataclass(slots=True)
class DatabaseBackupSummary:
    source_path: Path
    backup_path: Path
    size_bytes: int


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
        source_tables = set(inspect(source_connection).get_table_names())
        if truncate_target:
            for table in reversed(metadata.sorted_tables):
                target_connection.execute(table.delete())

        for table in metadata.sorted_tables:
            if table.name not in source_tables:
                copied_rows[table.name] = 0
                continue
            rows = [dict(row) for row in source_connection.execute(select(table)).mappings().all()]
            if rows:
                target_connection.execute(table.insert(), rows)
            copied_rows[table.name] = len(rows)

    return DatabaseCopySummary(
        source_url=source_database.url,
        target_url=target_database.url,
        copied_rows=copied_rows,
    )


def backup_sqlite_database(source_path: Path, *, backup_dir: Path | None = None) -> DatabaseBackupSummary:
    resolved_source = Path(source_path).resolve()
    if not resolved_source.exists():
        raise FileNotFoundError(f"SQLite database not found: {resolved_source}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_directory = Path(backup_dir or resolved_source.parent / "backups")
    target_directory.mkdir(parents=True, exist_ok=True)
    backup_path = target_directory / f"{resolved_source.stem}-{timestamp}.backup.sqlite3"

    source_connection = sqlite3.connect(str(resolved_source))
    backup_connection = sqlite3.connect(str(backup_path))
    try:
        source_connection.backup(backup_connection)
    finally:
        backup_connection.close()
        source_connection.close()

    return DatabaseBackupSummary(
        source_path=resolved_source,
        backup_path=backup_path,
        size_bytes=backup_path.stat().st_size,
    )
