"""Exercise the deployment shell with a fake CLI; no wallet or network calls."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "deploy/akash/cli-deploy.sh"
pytestmark = pytest.mark.skipif(not shutil.which("bash") or not shutil.which("jq"), reason="bash and jq required")

HARNESS = r'''
source "$1"
AKASH_DSEQ=123
AKASH_OWNER_ADDRESS=test-owner
AKASH_SDL_PATH=test.yaml
AKASH_MANIFEST_WAIT_SECONDS=0
AKASH_QUERY_FLAGS=(--output json)
AKASH_TX_FLAGS=(--from test --output json --gas auto)
render_sdl() { :; }
resolve_existing_or_latest_lease() { RESOLVED_DSEQ=123; RESOLVED_PROVIDER=test-provider; }
provider-services() {
  if [[ "$1 $2 $3" == "tx deployment update" ]]; then
    if [[ " $* " == *" --generate-only "* ]]; then
      echo generate >> "$CALLS"
      # Akash simulates gas=auto even for unsigned generation. A repeated
      # hash must be inspectable without running that rejecting simulation.
      local previous="" effective_gas="" argument
      for argument in "$@"; do
        if [[ "$previous" == --gas ]]; then effective_gas="$argument"; fi
        previous="$argument"
      done
      if [[ "$effective_gas" == auto ]]; then return 1; fi
      printf '%s\n' "$GENERATED"
    else
      echo transaction >> "$CALLS"
      if [[ "$TX_ERROR" == true ]]; then return 1; fi
      printf '%s\n' "$TX_RESPONSE"
      printf '%s\n' "$AFTER" > "$CHAIN"
    fi
  elif [[ "$1 $2 $3" == "query deployment get" ]]; then
    echo query >> "$CALLS"
    cat "$CHAIN"
  else
    echo "Unexpected CLI operation" >&2
    return 99
  fi
}
send_manifest_to_provider() {
  echo manifest >> "$CALLS"
  [[ "$MANIFEST_ERROR" != true ]]
}
write_result_env() { echo result >> "$CALLS"; }
update_deployment
'''


def run_deploy(tmp_path, *, current="old", desired="new", after="new", field="hash", **overrides):
    calls = tmp_path / "calls"
    calls.write_text("")
    chain = tmp_path / "chain.json"
    chain.write_text(json.dumps({"deployment": {field: current}}))
    generated = {"body": {"messages": [{"@type": "/akash.deployment.v1beta4.MsgUpdateDeployment", field: desired}]}}
    env = {
        **os.environ,
        "CALLS": str(calls), "CHAIN": str(chain), "GENERATED": json.dumps(generated),
        "AFTER": json.dumps({"deployment": {field: after}}),
        "TX_ERROR": "false", "TX_RESPONSE": '{"code":0}', "MANIFEST_ERROR": "false",
        **overrides,
    }
    result = subprocess.run(["bash", "-c", HARNESS, "test", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=15)
    return result, calls.read_text().splitlines()


@pytest.mark.parametrize("field", ["hash", "version"])
def test_unchanged_manifest_is_resent_without_a_transaction(tmp_path, field):
    result, calls = run_deploy(tmp_path, current="new", field=field)
    assert result.returncode == 0, result.stderr
    assert calls == ["generate", "query", "manifest", "result"]


def test_changed_manifest_waits_for_matching_chain_hash(tmp_path):
    result, calls = run_deploy(tmp_path)
    assert result.returncode == 0, result.stderr
    assert calls == ["generate", "query", "transaction", "query", "manifest", "result"]


@pytest.mark.parametrize("options", [
    {"TX_ERROR": "true"},
    {"TX_RESPONSE": '{"code":7}'},
    {"TX_RESPONSE": '{}'},
    {"after": "still-old"},
    {"GENERATED": '{}'},
    {"current": None},
])
def test_failed_or_unconfirmed_updates_do_not_send_manifest(tmp_path, options):
    result, calls = run_deploy(tmp_path, **options)
    assert result.returncode != 0
    assert "manifest" not in calls
    assert "result" not in calls


def test_manifest_failure_remains_a_failure_and_can_be_retried(tmp_path):
    failed, calls = run_deploy(tmp_path, current="new", MANIFEST_ERROR="true")
    assert failed.returncode != 0
    assert "transaction" not in calls
    assert "result" not in calls
    retried, calls = run_deploy(tmp_path, current="new")
    assert retried.returncode == 0, retried.stderr
    assert calls == ["generate", "query", "manifest", "result"]
