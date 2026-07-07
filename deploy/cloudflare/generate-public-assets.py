"""Generate Cloudflare Worker static asset module from api/app/static files."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "api" / "app" / "static"
OUTPUT = ROOT / "deploy" / "cloudflare" / "edge-router" / "src" / "public-assets.js"

ASSETS = [
    ("INDEX_HTML", STATIC_DIR / "index.html"),
    ("PLATFORM_HTML", STATIC_DIR / "platform.html"),
    ("SIMULATION_HTML", STATIC_DIR / "simulation.html"),
    ("STATUS_HTML", STATIC_DIR / "status.html"),
    ("TERMS_HTML", STATIC_DIR / "terms.html"),
    ("PRIVACY_HTML", STATIC_DIR / "privacy.html"),
    ("RISK_HTML", STATIC_DIR / "risk.html"),
    ("STYLES_CSS", STATIC_DIR / "styles.css"),
    ("HYPERLIQUID_TOKENS_CSS", STATIC_DIR / "hyperliquid-tokens.css"),
    ("APP_JS", STATIC_DIR / "app.js"),
    ("PLATFORM_CSS", STATIC_DIR / "platform.css"),
    ("PLATFORM_JS", STATIC_DIR / "platform.js"),
    ("LIGHTWEIGHT_CHARTS_JS", STATIC_DIR / "vendor" / "lightweight-charts.standalone.production.js"),
]


def main() -> None:
    lines = [
        "// Generated static public assets for Cloudflare edge serving.",
        "// Regenerate with: python deploy/cloudflare/generate-public-assets.py",
    ]
    for name, path in ASSETS:
        if not path.exists():
            raise FileNotFoundError(path)
        content = path.read_text(encoding="utf-8")
        lines.append(f"export const {name} = {json.dumps(content, ensure_ascii=False)};")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} with {len(ASSETS)} assets.")


if __name__ == "__main__":
    main()
