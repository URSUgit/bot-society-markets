#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "==> $*"
}

fail() {
  echo "::error::$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

install_provider_services() {
  if command -v provider-services >/dev/null 2>&1; then
    provider-services version
    return
  fi

  require_command curl
  require_command unzip

  local install_dir="${AKASH_CLI_BIN_DIR:-${RUNNER_TEMP:-$PWD/.akash-cli-bin}}"
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  mkdir -p "$install_dir"

  log "Installing provider-services CLI"
  (
    cd "$tmp_dir"
    curl -sfL https://raw.githubusercontent.com/akash-network/provider/main/install.sh | bash
    test -x ./bin/provider-services || fail "provider-services installer did not produce ./bin/provider-services"
    cp ./bin/provider-services "$install_dir/provider-services"
    chmod +x "$install_dir/provider-services"
  )
  rm -rf "$tmp_dir"

  export PATH="$install_dir:$PATH"
  provider-services version
}

bool_env() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|y|Y) echo "true" ;;
    *) echo "false" ;;
  esac
}

ensure_wallet() {
  if [ -z "${AKASH_CLI_MNEMONIC:-}" ]; then
    fail "AKASH_CLI_MNEMONIC is required. Use a dedicated funded deploy wallet, not your main wallet."
  fi

  if provider-services keys show "$AKASH_KEY_NAME" --keyring-backend "$AKASH_KEYRING_BACKEND" >/dev/null 2>&1; then
    log "Wallet key already exists in the runner keyring"
  else
    log "Importing Akash deploy wallet into ephemeral keyring"
    printf "%s\n" "$AKASH_CLI_MNEMONIC" | provider-services keys add "$AKASH_KEY_NAME" --recover --keyring-backend "$AKASH_KEYRING_BACKEND" --output json >/dev/null
  fi

  AKASH_OWNER_ADDRESS="$(provider-services keys show "$AKASH_KEY_NAME" -a --keyring-backend "$AKASH_KEYRING_BACKEND")"
  export AKASH_OWNER_ADDRESS
  log "Using deploy wallet: $AKASH_OWNER_ADDRESS"
}

query_flags() {
  printf '%s\0' --node "$AKASH_NODE" --chain-id "$AKASH_CHAIN_ID" --output json
}

tx_flags() {
  printf '%s\0' \
    --from "$AKASH_KEY_NAME" \
    --keyring-backend "$AKASH_KEYRING_BACKEND" \
    --node "$AKASH_NODE" \
    --chain-id "$AKASH_CHAIN_ID" \
    --gas "$AKASH_GAS" \
    --gas-adjustment "$AKASH_GAS_ADJUSTMENT" \
    --gas-prices "$AKASH_GAS_PRICES" \
    -y \
    --output json
}

load_query_flags() {
  mapfile -d '' AKASH_QUERY_FLAGS < <(query_flags)
}

load_tx_flags() {
  mapfile -d '' AKASH_TX_FLAGS < <(tx_flags)
}

extract_first_attr() {
  local key="$1"
  jq -r --arg key "$key" '[.. | objects | select(has("key") and .key == $key) | .value] | first // empty'
}

render_sdl() {
  if [ -z "${BSM_DATABASE_URL:-}" ]; then
    fail "BSM_DATABASE_URL is required for manifest/create/update CLI deploys."
  fi
  if [ -z "${IMAGE_REF:-}" ]; then
    fail "IMAGE_REF is required for manifest/create/update CLI deploys."
  fi

  require_command pwsh

  local args=(
    -NoProfile
    -ExecutionPolicy
    Bypass
    -File
    ./deploy/akash/prepare-bitprivat-neon.ps1
    -DatabaseUrl
    "$BSM_DATABASE_URL"
    -ImageRef
    "$IMAGE_REF"
    -OutputPath
    "$AKASH_SDL_PATH"
    -PricingDenom
    uact
    -SocialDiscoveryProvider
    "$BSM_SOCIAL_DISCOVERY_PROVIDER"
  )

  if [ "$(bool_env "${WITH_WORKER:-false}")" = "true" ]; then
    args+=(-WithWorker)
  fi
  if [ "$(bool_env "${AKASH_ENABLE_APP_CANONICAL_REDIRECTS:-false}")" = "true" ]; then
    args+=(-EnableAppCanonicalRedirects)
  fi

  log "Rendering Akash SDL for CLI deployment"
  pwsh "${args[@]}"
}

require_spend_confirmation() {
  case "$AKASH_CLI_MODE" in
    create|update)
      if [ "$(bool_env "${AKASH_CLI_CONFIRM_SPEND:-false}")" != "true" ]; then
        fail "Set AKASH_CLI_CONFIRM_SPEND=true for '$AKASH_CLI_MODE'. This path signs blockchain transactions and can spend AKT."
      fi
      ;;
  esac
}

get_active_lease_json() {
  local dseq="$1"
  provider-services query market lease list \
    --owner "$AKASH_OWNER_ADDRESS" \
    --dseq "$dseq" \
    --state active \
    "${AKASH_QUERY_FLAGS[@]}"
}

resolve_lease_from_active() {
  local dseq="$1"
  local leases_json
  leases_json="$(get_active_lease_json "$dseq")"

  RESOLVED_PROVIDER="$(jq -r '(.leases // [])[0] | .lease.lease_id.provider // .lease_id.provider // .bid_id.provider // empty' <<<"$leases_json")"
  RESOLVED_GSEQ="$(jq -r '(.leases // [])[0] | .lease.lease_id.gseq // .lease_id.gseq // .bid_id.gseq // "1"' <<<"$leases_json")"
  RESOLVED_OSEQ="$(jq -r '(.leases // [])[0] | .lease.lease_id.oseq // .lease_id.oseq // .bid_id.oseq // "1"' <<<"$leases_json")"

  if [ -n "${AKASH_PROVIDER:-}" ]; then
    RESOLVED_PROVIDER="$AKASH_PROVIDER"
  fi
  if [ -n "${AKASH_GSEQ:-}" ]; then
    RESOLVED_GSEQ="$AKASH_GSEQ"
  fi
  if [ -n "${AKASH_OSEQ:-}" ]; then
    RESOLVED_OSEQ="$AKASH_OSEQ"
  fi

  if [ -z "$RESOLVED_PROVIDER" ]; then
    fail "Could not resolve active provider for DSEQ $dseq. Set AKASH_PROVIDER or create a lease first."
  fi
}

write_result_env() {
  local dseq="$1"
  local provider="${2:-}"
  local result_path="${AKASH_CLI_RESULT_ENV:-deploy/akash/akash-cli-result.env}"
  {
    echo "AKASH_CLI_RESULT_DSEQ=$dseq"
    echo "AKASH_CLI_RESULT_PROVIDER=$provider"
    echo "AKASH_CLI_RESULT_OWNER=$AKASH_OWNER_ADDRESS"
    echo "AKASH_CLI_RESULT_SDL=$AKASH_SDL_PATH"
  } > "$result_path"
  log "Wrote result metadata: $result_path"
}

send_manifest_to_provider() {
  local dseq="$1"
  local provider="$2"

  # provider-services v0.12 accepts wallet/provider flags here, but not chain query flags.
  provider-services send-manifest "$AKASH_SDL_PATH" \
    --dseq "$dseq" \
    --provider "$provider" \
    --from "$AKASH_KEY_NAME" \
    --keyring-backend "$AKASH_KEYRING_BACKEND"
}

status_deployment() {
  log "Akash network status"
  provider-services query block "${AKASH_QUERY_FLAGS[@]}" | jq '{height: .block.header.height, time: .block.header.time}'

  log "Active deployments for wallet"
  provider-services query deployment list --owner "$AKASH_OWNER_ADDRESS" --state active "${AKASH_QUERY_FLAGS[@]}" | jq '.deployments // .'

  if [ -n "${AKASH_DSEQ:-}" ]; then
    log "Active leases for DSEQ $AKASH_DSEQ"
    get_active_lease_json "$AKASH_DSEQ" | jq '.leases // .'
    resolve_lease_from_active "$AKASH_DSEQ"

    log "Provider-services runtime command discovery"
    provider-services --help | sed -n '1,120p' || true
    provider-services query lease --help | sed -n '1,160p' || true
    provider-services lease-status --help | sed -n '1,160p' || true
    provider-services lease-logs --help | sed -n '1,160p' || true
    provider-services provider lease-status --help | sed -n '1,160p' || true
    provider-services provider lease-logs --help | sed -n '1,160p' || true
    provider-services query lease logs --help | sed -n '1,160p' || true

    log "Best-effort lease status"
    provider-services lease-status \
      --dseq "$AKASH_DSEQ" \
      --gseq "$RESOLVED_GSEQ" \
      --oseq "$RESOLVED_OSEQ" \
      --provider "$RESOLVED_PROVIDER" \
      --from "$AKASH_KEY_NAME" \
      --keyring-backend "$AKASH_KEYRING_BACKEND" || true

    log "Best-effort web service logs"
    provider-services lease-logs \
      --dseq "$AKASH_DSEQ" \
      --gseq "$RESOLVED_GSEQ" \
      --oseq "$RESOLVED_OSEQ" \
      --provider "$RESOLVED_PROVIDER" \
      --from "$AKASH_KEY_NAME" \
      --keyring-backend "$AKASH_KEYRING_BACKEND" \
      --service web \
      --tail 120 || true

    write_result_env "$AKASH_DSEQ" "${AKASH_PROVIDER:-}"
  fi
}

create_deployment() {
  render_sdl

  log "Creating Akash deployment"
  local create_args=(tx deployment create "$AKASH_SDL_PATH" --deposit "$AKASH_DEPOSIT")
  if [ -n "${AKASH_DSEQ:-}" ]; then
    create_args+=(--dseq "$AKASH_DSEQ")
  fi

  local create_json
  create_json="$(provider-services "${create_args[@]}" "${AKASH_TX_FLAGS[@]}")"
  local dseq
  dseq="$(extract_first_attr dseq <<<"$create_json")"
  if [ -z "$dseq" ]; then
    echo "$create_json" | jq '.'
    fail "Deployment create succeeded but DSEQ could not be parsed."
  fi

  log "Deployment created with DSEQ $dseq"
  log "Waiting ${AKASH_BID_WAIT_SECONDS}s for marketplace bids"
  sleep "$AKASH_BID_WAIT_SECONDS"

  local bids_json
  bids_json="$(provider-services query market bid list --owner "$AKASH_OWNER_ADDRESS" --dseq "$dseq" --state open "${AKASH_QUERY_FLAGS[@]}")"

  local provider
  provider="${AKASH_PROVIDER:-}"
  if [ -z "$provider" ]; then
    provider="$(jq -r '(.bids // [])[0] | .bid.bid_id.provider // .bid.provider // .bid_id.provider // empty' <<<"$bids_json")"
  fi

  local gseq
  local oseq
  gseq="${AKASH_GSEQ:-$(jq -r '(.bids // [])[0] | .bid.bid_id.gseq // .bid.gseq // .bid_id.gseq // "1"' <<<"$bids_json")}"
  oseq="${AKASH_OSEQ:-$(jq -r '(.bids // [])[0] | .bid.bid_id.oseq // .bid.oseq // .bid_id.oseq // "1"' <<<"$bids_json")}"

  if [ -z "$provider" ]; then
    echo "$bids_json" | jq '.'
    fail "No open bid was found for DSEQ $dseq. Increase AKASH_BID_WAIT_SECONDS or set AKASH_PROVIDER after inspecting bids."
  fi

  log "Creating lease with provider $provider"
  provider-services tx market lease create \
    --dseq "$dseq" \
    --gseq "$gseq" \
    --oseq "$oseq" \
    --provider "$provider" \
    "${AKASH_TX_FLAGS[@]}" >/dev/null

  log "Sending manifest to provider $provider"
  send_manifest_to_provider "$dseq" "$provider"

  write_result_env "$dseq" "$provider"
  log "Akash CLI create completed"
}

manifest_deployment() {
  if [ -z "${AKASH_DSEQ:-}" ]; then
    fail "AKASH_DSEQ is required for manifest mode."
  fi

  render_sdl
  resolve_lease_from_active "$AKASH_DSEQ"

  log "Sending manifest to provider $RESOLVED_PROVIDER for DSEQ $AKASH_DSEQ"
  send_manifest_to_provider "$AKASH_DSEQ" "$RESOLVED_PROVIDER"

  write_result_env "$AKASH_DSEQ" "$RESOLVED_PROVIDER"
  log "Akash CLI manifest upload completed"
}

update_deployment() {
  if [ -z "${AKASH_DSEQ:-}" ]; then
    fail "AKASH_DSEQ is required for update mode."
  fi

  render_sdl
  resolve_lease_from_active "$AKASH_DSEQ"

  log "Updating deployment hash for DSEQ $AKASH_DSEQ"
  provider-services tx deployment update "$AKASH_SDL_PATH" \
    --dseq "$AKASH_DSEQ" \
    "${AKASH_TX_FLAGS[@]}" >/dev/null

  log "Waiting ${AKASH_MANIFEST_WAIT_SECONDS}s before manifest upload"
  sleep "$AKASH_MANIFEST_WAIT_SECONDS"

  log "Sending updated manifest to provider $RESOLVED_PROVIDER"
  send_manifest_to_provider "$AKASH_DSEQ" "$RESOLVED_PROVIDER"

  write_result_env "$AKASH_DSEQ" "$RESOLVED_PROVIDER"
  log "Akash CLI update completed"
}

main() {
  AKASH_CLI_MODE="${AKASH_CLI_MODE:-update}"
  AKASH_KEY_NAME="${AKASH_KEY_NAME:-bitprivat-deployer}"
  AKASH_KEYRING_BACKEND="${AKASH_KEYRING_BACKEND:-test}"
  AKASH_CHAIN_ID="${AKASH_CHAIN_ID:-akashnet-2}"
  AKASH_NODE="${AKASH_NODE:-https://rpc.akashnet.net:443}"
  AKASH_GAS="${AKASH_GAS:-auto}"
  AKASH_GAS_ADJUSTMENT="${AKASH_GAS_ADJUSTMENT:-1.5}"
  AKASH_GAS_PRICES="${AKASH_GAS_PRICES:-0.025uakt}"
  AKASH_DEPOSIT="${AKASH_DEPOSIT:-500000uact}"
  AKASH_BID_WAIT_SECONDS="${AKASH_BID_WAIT_SECONDS:-45}"
  AKASH_MANIFEST_WAIT_SECONDS="${AKASH_MANIFEST_WAIT_SECONDS:-10}"
  AKASH_SDL_PATH="${AKASH_SDL_PATH:-deploy/akash/akash-cli.generated.yaml}"
  BSM_SOCIAL_DISCOVERY_PROVIDER="${BSM_SOCIAL_DISCOVERY_PROVIDER:-demo}"

  export AKASH_KEY_NAME AKASH_KEYRING_BACKEND AKASH_CHAIN_ID AKASH_NODE
  export AKASH_GAS AKASH_GAS_ADJUSTMENT AKASH_GAS_PRICES AKASH_DEPOSIT
  export AKASH_SDL_PATH BSM_SOCIAL_DISCOVERY_PROVIDER

  require_command jq
  install_provider_services
  ensure_wallet
  load_query_flags
  load_tx_flags
  require_spend_confirmation

  case "$AKASH_CLI_MODE" in
    status)
      status_deployment
      ;;
    manifest)
      manifest_deployment
      ;;
    create)
      create_deployment
      ;;
    update)
      update_deployment
      ;;
    *)
      fail "Unsupported AKASH_CLI_MODE '$AKASH_CLI_MODE'. Use status, manifest, create, or update."
      ;;
  esac
}

main "$@"
