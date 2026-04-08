from __future__ import annotations

import argparse

from .config import get_settings
from .database import Database
from .services import BotSocietyService



def build_service() -> BotSocietyService:
    settings = get_settings()
    database = Database(settings.database_path)
    service = BotSocietyService(database, settings)
    service.bootstrap()
    return service



def main() -> None:
    parser = argparse.ArgumentParser(description="Bot Society Markets operational jobs")
    parser.add_argument("command", choices=["bootstrap", "run-cycle", "provider-status"])
    args = parser.parse_args()

    service = build_service()

    if args.command == "bootstrap":
        print("Bootstrap completed.")
        return

    if args.command == "run-cycle":
        result = service.run_pipeline_cycle()
        print(
            f"Cycle {result.operation.id if result.operation else 'n/a'} completed. "
            f"Generated {result.operation.generated_predictions if result.operation else 0} predictions; "
            f"scored {result.operation.scored_predictions if result.operation else 0}."
        )
        return

    if args.command == "provider-status":
        status = service.get_provider_status()
        print(
            f"market_provider_mode={status.market_provider_mode} "
            f"market_provider_source={status.market_provider_source} "
            f"signal_provider_source={status.signal_provider_source} "
            f"fallback_active={status.fallback_active}"
        )


if __name__ == "__main__":
    main()
