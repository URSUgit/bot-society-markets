#!/bin/sh
set -eu

python -m http.server 9000 --bind 0.0.0.0 >/tmp/bsm-worker-health.log 2>&1 &
HEALTH_PID="$!"

cleanup() {
  kill "$HEALTH_PID" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

python -m api.app.jobs db-upgrade
exec python -m api.app.jobs worker
