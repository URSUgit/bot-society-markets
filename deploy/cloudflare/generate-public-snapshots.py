from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "deploy" / "cloudflare" / "edge-router" / "src" / "public-snapshots.js"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app.config import Settings
from api.app.main import create_app


def dump_js(name: str, payload: object) -> str:
    return f"export const {name} = {json.dumps(payload, separators=(',', ':'))};"


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "bsm-edge-public-snapshots.db"
        settings = Settings(
            database_path=db_path,
            environment_name="development",
            deployment_target="akash",
            canonical_host="app.bitprivat.com",
            force_https=True,
        )
        app = create_app(settings)
        with TestClient(app) as client:
            landing = client.get("/api/landing").json()
            dashboard = client.get("/api/dashboard").json()
            pulse = {"system_pulse": client.get("/api/system/pulse").json()}
            connector_diagnostics = client.get("/api/system/connectors/diagnostics").json()

    content = "\n".join(
        [
            "// Generated lightweight public snapshots for Cloudflare edge fallback.",
            "// Regenerate from the FastAPI fast-public path when the public dashboard schema changes.",
            dump_js("LANDING_SNAPSHOT", landing),
            "",
            dump_js("DASHBOARD_SNAPSHOT", dashboard),
            "",
            dump_js("SYSTEM_PULSE", pulse),
            "",
            dump_js("CONNECTOR_DIAGNOSTICS", connector_diagnostics),
            "",
        ]
    )
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
