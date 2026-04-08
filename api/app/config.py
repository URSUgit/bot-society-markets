from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    project_name: str = "Bot Society Markets"
    version: str = "0.2.0"
    database_path: Path = Path("api/data/bot_society_markets.db")
    seed_demo_data: bool = True
    scoring_version: str = "v1"



def get_settings() -> Settings:
    database_path = Path(os.getenv("BSM_DATABASE_PATH", "api/data/bot_society_markets.db"))
    seed_demo_data = os.getenv("BSM_SEED_DEMO_DATA", "true").lower() not in {"0", "false", "no"}
    return Settings(database_path=database_path, seed_demo_data=seed_demo_data)
