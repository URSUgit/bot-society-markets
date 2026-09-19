"""Run the real PowerShell verifier against a local origin/edge fixture."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest


PWSH = os.environ.get("PWSH") or shutil.which("pwsh")
SCRIPT = Path(__file__).resolve().parents[2] / "deploy/verify-production.ps1"
REVISION = "1234567" + "a" * 33


@pytest.mark.skipif(not PWSH, reason="PowerShell required for deployment verifier")
@pytest.mark.parametrize("scenario", ["live", "snapshot", "old_build", "unknown_build", "origin_down"])
def test_verifier_requires_live_origin_and_expected_build(scenario):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            url = urlsplit(self.path)
            requests.append(url)
            path = url.path
            status = 200
            data = "BITprivat System page-root primary-nav platform.css platform.js Expert bots bp-app"
            mode = "live-origin"
            if path == "/api/runtime/public-origin":
                data = json.dumps({"social_read_origin": f"http://127.0.0.1:{self.server.server_port}/origin"})
            elif path.endswith("/health"):
                revision = {"old_build": "b" * 40, "unknown_build": "unknown"}.get(scenario, REVISION)
                data = json.dumps({"status": "ok", "build_revision": revision})
            elif path.endswith("/system/pulse"):
                data = '{"system_pulse":{}}'
                if scenario == "snapshot":
                    mode = "edge-snapshot"
            elif path.endswith("/social-trading"):
                data = '{"top_traders":[],"safety_notes":[]}'
            elif path.endswith("/social-traders") and path.startswith("/api"):
                data = "[]"
            if scenario == "origin_down" and path.startswith("/origin/"):
                status = 503
            self.send_response(status)
            self.send_header("Content-Type", "application/json" if path.startswith("/api") else "text/plain")
            self.send_header("X-BITprivat-Data-Mode", mode)
            self.end_headers()
            self.wfile.write(data.encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{server.server_port}"
    try:
        result = subprocess.run([
            PWSH, "-NoProfile", "-File", str(SCRIPT),
            "-RootUrl", root, "-AppUrl", root, "-ApiUrl", root, "-StatusUrl", root,
            "-Attempts", "1", "-ExpectSocialTrading", "-ExpectOperatorStrip",
            "-RequireLiveOrigin", "-CheckDirectOrigin", "-ExpectedRevision", REVISION[:7],
        ], capture_output=True, text=True, timeout=30)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    if scenario == "live":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Production verification passed" in result.stdout
    else:
        assert result.returncode != 0, result.stdout
        assert "Production verification failed" in result.stderr
    direct = [url for url in requests if url.path.startswith("/origin/")]
    assert {url.path for url in direct} == {"/origin/api/v1/system/pulse", "/origin/api/social-trading", "/origin/health"}
    assert all(parse_qs(url.query).get("edge_require_live") == ["1"] for url in direct)
