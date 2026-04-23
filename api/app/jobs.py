from __future__ import annotations

import argparse
from pathlib import Path

from .config import get_settings
from .database import Database
from .db_ops import backup_sqlite_database, copy_database, upgrade_database
from .services import BotSocietyService
from .worker import PipelineWorker



def build_service() -> BotSocietyService:
    settings = get_settings()
    database = Database(path=settings.database_path, url=settings.database_url)
    service = BotSocietyService(database, settings)
    service.bootstrap()
    return service



def _database_locator(url: str | None, path: str | None) -> Database:
    if url:
        return Database(url=url)
    if path:
        return Database(path=Path(path))
    raise ValueError("A database URL or path is required")



def main() -> None:
    parser = argparse.ArgumentParser(description="Bot Society Markets operational jobs")
    parser.add_argument(
        "command",
        choices=[
            "bootstrap",
            "run-cycle",
            "provider-status",
            "worker",
            "retry-notifications",
            "notification-health",
            "db-upgrade",
            "db-copy",
            "db-backup",
            "cutover-report",
        ],
    )
    parser.add_argument("--interval-seconds", type=int, default=None)
    parser.add_argument("--cycles", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--revision", type=str, default="head")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--source-url", type=str, default=None)
    parser.add_argument("--target-url", type=str, default=None)
    parser.add_argument("--source-path", type=str, default=None)
    parser.add_argument("--target-path", type=str, default=None)
    parser.add_argument("--backup-dir", type=str, default=None)
    parser.add_argument("--no-truncate-target", action="store_true")
    parser.add_argument("--probe-live", action="store_true")
    args = parser.parse_args()

    if args.command == "db-upgrade":
        target_url = args.database_url or get_settings().database_url
        upgrade_database(args.revision, database_url=target_url)
        print(f"Database upgraded to {args.revision}.")
        return

    if args.command == "db-copy":
        source_database = _database_locator(args.source_url, args.source_path)
        target_database = _database_locator(args.target_url, args.target_path)
        try:
            summary = copy_database(
                source_database,
                target_database,
                truncate_target=not args.no_truncate_target,
            )
        finally:
            source_database.dispose()
            target_database.dispose()
        print(
            f"Copied {summary.total_rows} row(s) from {summary.source_url} to {summary.target_url}."
        )
        for table_name, count in summary.copied_rows.items():
            print(f"  {table_name}: {count}")
        return

    if args.command == "db-backup":
        settings = get_settings()
        source_path = Path(args.source_path) if args.source_path else settings.database_path
        summary = backup_sqlite_database(
            source_path,
            backup_dir=Path(args.backup_dir) if args.backup_dir else None,
        )
        print(
            f"Backed up SQLite database from {summary.source_path} to {summary.backup_path} "
            f"({summary.size_bytes} bytes)."
        )
        return

    service = build_service()
    settings = service.settings

    if args.command == "bootstrap":
        print("Bootstrap completed.")
        return

    if args.command == "run-cycle":
        result = service.run_pipeline_cycle()
        print(
            f"Cycle {result.operation.id if result.operation else 'n/a'} completed. "
            f"Generated {result.operation.generated_predictions if result.operation else 0} predictions; "
            f"scored {result.operation.scored_predictions if result.operation else 0}; "
            f"unread alerts {result.alert_inbox.unread_count}."
        )
        return

    if args.command == "provider-status":
        status = service.get_provider_status()
        print(
            f"environment_name={status.environment_name} "
            f"deployment_target={status.deployment_target} "
            f"database_backend={status.database_backend} "
            f"database_target={status.database_target} "
            f"market_provider_mode={status.market_provider_mode} "
            f"market_provider_source={status.market_provider_source} "
            f"market_provider_configured={status.market_provider_configured} "
            f"market_provider_live_capable={status.market_provider_live_capable} "
            f"signal_provider_mode={status.signal_provider_mode} "
            f"signal_provider_source={status.signal_provider_source} "
            f"signal_provider_configured={status.signal_provider_configured} "
            f"signal_provider_live_capable={status.signal_provider_live_capable} "
            f"market_fallback_active={status.market_fallback_active} "
            f"signal_fallback_active={status.signal_fallback_active}"
        )
        if status.venue_signal_providers:
            for provider in status.venue_signal_providers:
                print(
                    f"  venue_provider mode={provider.mode} source={provider.source} configured={provider.configured} "
                    f"live_capable={provider.live_capable} ready={provider.ready}"
                )
        if args.probe_live:
            diagnostics = service.probe_provider_connectivity()
            for name, result in diagnostics.items():
                print(f"{name}_probe={result}")
        return

    if args.command == "retry-notifications":
        result = service.retry_failed_notifications(limit=args.limit)
        print(
            f"Notification retry scan complete. scanned={result.scanned_events} delivered={result.delivered} "
            f"rescheduled={result.rescheduled} exhausted={result.exhausted}"
        )
        return

    if args.command == "notification-health":
        health = service.get_notification_health(settings.default_user_slug)
        print(
            f"active_channels={health.active_channels} delivered_last_24h={health.delivered_last_24h} "
            f"retry_queue_depth={health.retry_queue_depth} exhausted_deliveries={health.exhausted_deliveries}"
        )
        for channel in health.channels:
            print(
                f"  channel={channel.channel_type}:{channel.target} delivered={channel.delivered_count} "
                f"retry_scheduled={channel.retry_scheduled_count} exhausted={channel.exhausted_count}"
            )
        return

    if args.command == "cutover-report":
        report = service.get_production_cutover()
        print(
            f"posture={report.posture} current_backend={report.current_backend} "
            f"current_target={report.current_target} target_backend={report.target_backend}"
        )
        print(report.summary)
        print(report.source_data_note)
        for step in report.steps:
            print(f"[{step.state}] {step.label}: {step.detail}")
            if step.command:
                print(f"  command: {step.command}")
        if report.verification_urls:
            print("verify:")
            for url in report.verification_urls:
                print(f"  {url}")
        return

    if args.command == "worker":
        interval_seconds = max(30, args.interval_seconds or settings.worker_interval_seconds)
        max_cycles = max(0, args.cycles if args.cycles is not None else settings.worker_max_cycles)
        worker = PipelineWorker(service, interval_seconds=interval_seconds)
        summary = worker.run(max_cycles=max_cycles)
        print(
            f"Worker completed {summary.completed_cycles} cycle(s) at {summary.interval_seconds}-second intervals."
        )


if __name__ == "__main__":
    main()
