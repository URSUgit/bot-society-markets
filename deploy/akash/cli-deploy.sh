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

provider_hostport_from_url() {
  local url="$1"
  url="${url#http://}"
  url="${url#https://}"
  url="${url%%/*}"
  printf "%s" "$url"
}

provider_host_from_hostport() {
  local hostport="$1"
  hostport="${hostport#[}"
  hostport="${hostport%%]*}"
  if [[ "$hostport" == *:* && "$hostport" != *"]"* ]]; then
    hostport="${hostport%%:*}"
  fi
  printf "%s" "$hostport"
}

configure_provider_tls_trust() {
  local provider_url="${AKASH_PROVIDER_URL:-}"
  local trust_bootstrap
  trust_bootstrap="$(bool_env "${AKASH_PROVIDER_TLS_BOOTSTRAP:-false}")"

  if [ -z "${AKASH_PROVIDER_CA_PEM:-}" ] && [ "$trust_bootstrap" != "true" ]; then
    return
  fi

  local bundle="${AKASH_PROVIDER_CA_BUNDLE:-${RUNNER_TEMP:-/tmp}/akash-provider-ca-bundle.pem}"
  local base_bundle=""
  for candidate in /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt; do
    if [ -r "$candidate" ]; then
      base_bundle="$candidate"
      break
    fi
  done

  if [ -n "$base_bundle" ]; then
    cp "$base_bundle" "$bundle"
  else
    : > "$bundle"
  fi

  if [ -n "${AKASH_PROVIDER_CA_PEM:-}" ]; then
    log "Adding pinned Akash provider CA PEM to temporary trust bundle"
    {
      printf "\n"
      printf "%s\n" "$AKASH_PROVIDER_CA_PEM"
      printf "\n"
    } >> "$bundle"
  fi

  if [ "$trust_bootstrap" = "true" ]; then
    if [ -z "$provider_url" ]; then
      fail "AKASH_PROVIDER_TLS_BOOTSTRAP=true requires AKASH_PROVIDER_URL so the trust scope is explicit."
    fi
    require_command openssl
    local hostport host
    hostport="$(provider_hostport_from_url "$provider_url")"
    host="$(provider_host_from_hostport "$hostport")"
    log "Bootstrapping Akash provider TLS trust for $hostport"
    if ! timeout 20 openssl s_client -showcerts -connect "$hostport" -servername "$host" </dev/null 2>/dev/null \
      | awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/' >> "$bundle"; then
      fail "Could not fetch provider certificate chain from $hostport."
    fi
  fi

  export SSL_CERT_FILE="$bundle"
  log "Using temporary Akash provider TLS bundle at $SSL_CERT_FILE"
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

ensure_client_certificate() {
  local cert_dir="${AKASH_CERT_HOME:-$HOME/.akash}"
  local cert_path="$cert_dir/$AKASH_OWNER_ADDRESS.pem"
  if [ -s "$cert_path" ]; then
    log "Akash client certificate already exists at $cert_path"
    return
  fi

  mkdir -p "$cert_dir"
  log "Generating Akash client certificate for deployment transactions"
  provider-services tx cert generate client \
    --from "$AKASH_KEY_NAME" \
    --keyring-backend "$AKASH_KEYRING_BACKEND"
  publish_client_certificate
}

publish_client_certificate() {
  log "Publishing Akash client certificate"
  local stderr_file
  stderr_file="$(mktemp)"
  if provider-services tx cert publish client "${AKASH_TX_FLAGS[@]}" >/dev/null 2>"$stderr_file"; then
    rm -f "$stderr_file"
    return
  fi

  if grep -qiE "overwrite|already|exists" "$stderr_file"; then
    if provider-services tx cert publish client --override "${AKASH_TX_FLAGS[@]}" >/dev/null 2>"$stderr_file"; then
      rm -f "$stderr_file"
      return
    fi
    if provider-services tx cert publish client --overwrite "${AKASH_TX_FLAGS[@]}" >/dev/null 2>"$stderr_file"; then
      rm -f "$stderr_file"
      return
    fi
  fi

  cat "$stderr_file" >&2
  rm -f "$stderr_file"
  fail "Could not publish Akash client certificate."
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
  jq -r --arg key "$key" '
    [
      .. | objects |
      if has("key") and .key == $key then
        .value
      elif has("value") then
        (.value | fromjson? | if type == "object" and has($key) then .[$key] else empty end)
      else
        empty
      end
    ] | first // empty
  '
}

bid_provider_jq='
  def bid_provider:
    .bid.bid_id.provider // .bid.id.provider // .bid.provider // .bid_id.provider // empty;
  def bid_gseq:
    .bid.bid_id.gseq // .bid.id.gseq // .bid.gseq // .bid_id.gseq // "1";
  def bid_oseq:
    .bid.bid_id.oseq // .bid.id.oseq // .bid.oseq // .bid_id.oseq // "1";
'

select_bid_field() {
  local bids_json="$1"
  local provider="$2"
  local field="$3"
  jq -r --arg provider "$provider" --arg field "$field" "$bid_provider_jq"'
    (.bids // [])
    | map(select(bid_provider == $provider))
    | .[0]
    | if $field == "gseq" then bid_gseq
      elif $field == "oseq" then bid_oseq
      else bid_provider
      end
  ' <<<"$bids_json"
}

select_open_bid_provider() {
  local bids_json="$1"
  local excludes_csv="${2:-}"
  jq -r --arg excludes "$excludes_csv" "$bid_provider_jq"'
    def trim: gsub("^\\s+|\\s+$"; "");
    def excluded($provider):
      ($excludes | split(",") | map(trim) | map(select(length > 0)) | index($provider)) != null;
    (.bids // [])
    | map(select((bid_provider | length) > 0))
    | map(select(excluded(bid_provider) | not))
    | .[0]
    | bid_provider // empty
  ' <<<"$bids_json"
}

render_sdl() {
  if [ -z "${IMAGE_REF:-}" ]; then
    fail "IMAGE_REF is required for manifest/create/update CLI deploys."
  fi
  case "${AKASH_DATABASE_MODE:-postgres}" in
    postgres|sqlite) ;;
    *) fail "Unsupported AKASH_DATABASE_MODE '${AKASH_DATABASE_MODE:-}'. Use postgres or sqlite." ;;
  esac
  if [ "${AKASH_DATABASE_MODE:-postgres}" = "postgres" ] && [ -z "${BSM_DATABASE_URL:-}" ]; then
    fail "BSM_DATABASE_URL is required for Postgres manifest/create/update CLI deploys. Use AKASH_DATABASE_MODE=sqlite for emergency no-Postgres deploys."
  fi

  require_command pwsh

  local args=(
    -NoProfile
    -ExecutionPolicy
    Bypass
    -File
    ./deploy/akash/prepare-bitprivat-neon.ps1
    -DatabaseMode
    "${AKASH_DATABASE_MODE:-postgres}"
    -ImageRef
    "$IMAGE_REF"
    -OutputPath
    "$AKASH_SDL_PATH"
    -PricingDenom
    "$AKASH_PRICING_DENOM"
    -SocialDiscoveryProvider
    "$BSM_SOCIAL_DISCOVERY_PROVIDER"
  )

  if [ "${AKASH_DATABASE_MODE:-postgres}" = "postgres" ]; then
    args+=(
      -DatabaseUrl
      "$BSM_DATABASE_URL"
    )
  fi

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
    create|update|close)
      if [ "$(bool_env "${AKASH_CLI_CONFIRM_SPEND:-false}")" != "true" ]; then
        fail "Set AKASH_CLI_CONFIRM_SPEND=true for '$AKASH_CLI_MODE'. This path signs blockchain transactions and can spend AKT."
      fi
      ;;
  esac
}

get_active_lease_json() {
  local dseq="$1"
  local leases_json
  leases_json="$(provider-services query market lease list \
    --owner "$AKASH_OWNER_ADDRESS" \
    --dseq "$dseq" \
    --state active \
    "${AKASH_QUERY_FLAGS[@]}")"

  if [ "$(jq -r '(.leases // []) | length' <<<"$leases_json")" != "0" ]; then
    printf '%s\n' "$leases_json"
    return
  fi

  # provider-services can lag the chain's current market query version. Use
  # the public v1beta5 REST gateway as a read-only fallback before failing.
  local rest_api="${AKASH_REST_API:-https://api.akashnet.net}"
  local rest_json
  rest_json="$(curl -fsS --get \
    "${rest_api%/}/akash/market/v1beta5/leases/list" \
    --data-urlencode "filters.owner=$AKASH_OWNER_ADDRESS" \
    --data-urlencode "filters.dseq=$dseq" \
    --data-urlencode "filters.state=active" \
    --data-urlencode "pagination.limit=20")"
  log "Resolved active lease through the Akash v1beta5 REST fallback" >&2
  printf '%s\n' "$rest_json"
}

resolve_lease_from_active() {
  local dseq="$1"
  local leases_json
  leases_json="$(get_active_lease_json "$dseq")"

  local lease_count
  lease_count="$(jq -r '(.leases // []) | length' <<<"$leases_json")"
  if [ "$lease_count" = "0" ]; then
    echo "$leases_json" | jq '.'
    fail "No active lease was found for DSEQ $dseq. Create a new deployment or update AKASH_CLI_DSEQ before running update/manifest mode."
  fi

  local active_provider
  active_provider="$(jq -r '(.leases // [])[0] | .lease.lease_id.provider // .lease.id.provider // .lease_id.provider // .bid_id.provider // empty' <<<"$leases_json")"
  RESOLVED_PROVIDER="$active_provider"
  RESOLVED_GSEQ="$(jq -r '(.leases // [])[0] | .lease.lease_id.gseq // .lease.id.gseq // .lease_id.gseq // .bid_id.gseq // "1"' <<<"$leases_json")"
  RESOLVED_OSEQ="$(jq -r '(.leases // [])[0] | .lease.lease_id.oseq // .lease.id.oseq // .lease_id.oseq // .bid_id.oseq // "1"' <<<"$leases_json")"

  if [ -n "${AKASH_PROVIDER:-}" ]; then
    if [ "$AKASH_PROVIDER" = "$active_provider" ]; then
      RESOLVED_PROVIDER="$AKASH_PROVIDER"
    elif [ "$(bool_env "${AKASH_ALLOW_PROVIDER_OVERRIDE:-false}")" = "true" ]; then
      log "Overriding active lease provider $active_provider with AKASH_PROVIDER=$AKASH_PROVIDER"
      RESOLVED_PROVIDER="$AKASH_PROVIDER"
    else
      log "Ignoring AKASH_PROVIDER override because active lease provider is $active_provider. Set AKASH_ALLOW_PROVIDER_OVERRIDE=true to force it."
    fi
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
  local saved_provider_url="${AKASH_PROVIDER_URL:-}"
  local saved_tls_bootstrap="${AKASH_PROVIDER_TLS_BOOTSTRAP:-}"
  local command_provider_url="$saved_provider_url"
  local command_tls_bootstrap="$saved_tls_bootstrap"

  if [ -n "$saved_provider_url" ] && [ -n "${AKASH_PROVIDER:-}" ] && [ "$provider" != "$AKASH_PROVIDER" ] && [ "$(bool_env "${AKASH_FORCE_PROVIDER_URL:-false}")" != "true" ]; then
    log "Skipping pinned provider URL/TLS bootstrap because selected provider differs from AKASH_PROVIDER."
    command_provider_url=""
    command_tls_bootstrap="false"
  fi

  AKASH_PROVIDER_URL="$command_provider_url"
  AKASH_PROVIDER_TLS_BOOTSTRAP="$command_tls_bootstrap"
  configure_provider_tls_trust

  # provider-services v0.12 accepts wallet/provider flags here, but not chain query flags.
  local args=(
    send-manifest
    "$AKASH_SDL_PATH"
    --dseq "$dseq"
    --provider "$provider"
    --from "$AKASH_KEY_NAME"
    --keyring-backend "$AKASH_KEYRING_BACKEND"
  )
  if [ -n "$command_provider_url" ] && [ "$(bool_env "${AKASH_FORCE_PROVIDER_URL:-false}")" = "true" ]; then
    args+=(--provider-url "$command_provider_url")
  fi

  local result=0
  if provider-services "${args[@]}"; then
    result=0
  else
    result=$?
  fi

  AKASH_PROVIDER_URL="$saved_provider_url"
  AKASH_PROVIDER_TLS_BOOTSTRAP="$saved_tls_bootstrap"
  return "$result"
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

    local saved_provider_url="${AKASH_PROVIDER_URL:-}"
    local saved_tls_bootstrap="${AKASH_PROVIDER_TLS_BOOTSTRAP:-}"
    if [ -n "$saved_provider_url" ] && [ -n "${AKASH_PROVIDER:-}" ] && [ "$RESOLVED_PROVIDER" != "$AKASH_PROVIDER" ] && [ "$(bool_env "${AKASH_FORCE_PROVIDER_URL:-false}")" != "true" ]; then
      log "Skipping pinned provider URL/TLS bootstrap for status because the active lease uses another provider."
      AKASH_PROVIDER_URL=""
      AKASH_PROVIDER_TLS_BOOTSTRAP="false"
    fi
    configure_provider_tls_trust

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

    AKASH_PROVIDER_URL="$saved_provider_url"
    AKASH_PROVIDER_TLS_BOOTSTRAP="$saved_tls_bootstrap"

    write_result_env "$AKASH_DSEQ" "$RESOLVED_PROVIDER"
  fi
}

create_deployment() {
  render_sdl
  ensure_client_certificate

  local dseq=""
  local create_args=(tx deployment create "$AKASH_SDL_PATH" --deposit "$AKASH_DEPOSIT")
  # Create mode must be able to recover from a closed/invalid prior lease. Do
  # not inherit AKASH_DSEQ unless a caller explicitly asks for deterministic
  # DSEQ creation with AKASH_CLI_CREATE_DSEQ.
  if [ -n "${AKASH_CLI_CREATE_DSEQ:-}" ]; then
    if provider-services query deployment get \
      --owner "$AKASH_OWNER_ADDRESS" \
      --dseq "$AKASH_CLI_CREATE_DSEQ" \
      "${AKASH_QUERY_FLAGS[@]}" >/dev/null 2>&1; then
      dseq="$AKASH_CLI_CREATE_DSEQ"
      log "Using existing Akash deployment DSEQ $dseq"
    else
      create_args+=(--dseq "$AKASH_CLI_CREATE_DSEQ")
    fi
  else
    unset AKASH_DSEQ
  fi

  if [ -z "$dseq" ]; then
    log "Creating Akash deployment"
    local create_json
    create_json="$(provider-services "${create_args[@]}" "${AKASH_TX_FLAGS[@]}")"
    dseq="$(extract_first_attr dseq <<<"$create_json")"
    if [ -z "$dseq" ]; then
      echo "$create_json" | jq '.'
      fail "Deployment create succeeded but DSEQ could not be parsed."
    fi
    log "Deployment created with DSEQ $dseq"
  fi

  log "Waiting ${AKASH_BID_WAIT_SECONDS}s for marketplace bids"
  sleep "$AKASH_BID_WAIT_SECONDS"

  local bids_json
  bids_json="$(provider-services query market bid list --owner "$AKASH_OWNER_ADDRESS" --dseq "$dseq" --state open "${AKASH_QUERY_FLAGS[@]}")"

  local provider
  provider="${AKASH_CLI_CREATE_PROVIDER:-}"
  if [ -z "$provider" ]; then
    local exclude_providers="${AKASH_CLI_EXCLUDE_PROVIDERS:-}"
    if [ -z "$exclude_providers" ] && [ -n "${AKASH_PROVIDER:-}" ]; then
      exclude_providers="$AKASH_PROVIDER"
    fi

    local bid_count
    bid_count="$(jq -r '(.bids // []) | length' <<<"$bids_json")"
    if [ -n "$exclude_providers" ]; then
      log "Selecting provider from $bid_count open bid(s), excluding configured provider(s)."
    else
      log "Selecting provider from $bid_count open bid(s)."
    fi
    provider="$(select_open_bid_provider "$bids_json" "$exclude_providers")"
  else
    log "Using explicitly requested create provider $provider"
  fi

  if [ -z "$provider" ]; then
    echo "$bids_json" | jq '.'
    fail "No eligible open bid was found for DSEQ $dseq. Increase AKASH_BID_WAIT_SECONDS, adjust AKASH_CLI_EXCLUDE_PROVIDERS, or pass a provider explicitly."
  fi

  local gseq
  local oseq
  gseq="${AKASH_GSEQ:-$(select_bid_field "$bids_json" "$provider" gseq)}"
  oseq="${AKASH_OSEQ:-$(select_bid_field "$bids_json" "$provider" oseq)}"

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

close_deployment() {
  if [ -z "${AKASH_DSEQ:-}" ]; then
    fail "AKASH_DSEQ is required for close mode."
  fi

  log "Closing Akash deployment DSEQ $AKASH_DSEQ"
  provider-services tx deployment close \
    --dseq "$AKASH_DSEQ" \
    "${AKASH_TX_FLAGS[@]}" >/dev/null

  write_result_env "$AKASH_DSEQ" "${AKASH_PROVIDER:-}"
  log "Akash CLI close completed"
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
  AKASH_BID_WAIT_SECONDS="${AKASH_BID_WAIT_SECONDS:-120}"
  AKASH_MANIFEST_WAIT_SECONDS="${AKASH_MANIFEST_WAIT_SECONDS:-10}"
  AKASH_SDL_PATH="${AKASH_SDL_PATH:-deploy/akash/akash-cli.generated.yaml}"
  AKASH_DATABASE_MODE="${AKASH_DATABASE_MODE:-postgres}"
  AKASH_PRICING_DENOM="${AKASH_PRICING_DENOM:-uact}"
  AKASH_DEPOSIT="${AKASH_DEPOSIT:-500000${AKASH_PRICING_DENOM}}"
BSM_REAL_DATA_ONLY="${BSM_REAL_DATA_ONLY:-true}"
BSM_SEED_DEMO_DATA="${BSM_SEED_DEMO_DATA:-false}"
BSM_SOCIAL_DISCOVERY_PROVIDER="${BSM_SOCIAL_DISCOVERY_PROVIDER:-youtube}"

export AKASH_KEY_NAME AKASH_KEYRING_BACKEND AKASH_CHAIN_ID AKASH_NODE
export AKASH_GAS AKASH_GAS_ADJUSTMENT AKASH_GAS_PRICES AKASH_DEPOSIT
export AKASH_SDL_PATH AKASH_DATABASE_MODE AKASH_PRICING_DENOM BSM_REAL_DATA_ONLY BSM_SEED_DEMO_DATA BSM_SOCIAL_DISCOVERY_PROVIDER

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
    close)
      close_deployment
      ;;
    *)
      fail "Unsupported AKASH_CLI_MODE '$AKASH_CLI_MODE'. Use status, manifest, create, update, or close."
      ;;
  esac
}

main "$@"
