from __future__ import annotations

import argparse

from .config import get_settings
from .database import Database
from .services import BotSocietyService
from .worker import PipelineWorker



def build_service() -> BotSocietyService:
    settings = get_settings()
    database = Database(settings.database_path)
    service = BotSocietyService(database, settings)
    service.bootstrap()
    return service



def main() -> None:
    parser = argparse.ArgumentParser(description="Bot Society Markets operational jobs")
    parser.add_argument("command", choices=["bootstrap", "run-cycle", "provider-status", "worker"])
    parser.add_argument("--interval-seconds", type=int, default=None)
    parser.add_argument("--cycles", type=int, default=None)
    args = parser.parse_args()

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
            f"market_provider_mode={status.market_provider_mode} "
            f"market_provider_source={status.market_provider_source} "
            f"signal_provider_mode={status.signal_provider_mode} "
            f"signal_provider_source={status.signal_provider_source} "
            f"market_fallback_active={status.market_fallback_active} "
            f"signal_fallback_active={status.signal_fallback_active}"
        )
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
