#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/verify-object-storage.sh [--help]

Load lane env and report whether object storage config is ready for real uploads.

Optional environment overrides:
  LANE_ROOT=/abs/path/to/lane-root
  ENV_FILE=/abs/path/to/lane.env
  PYTHON_BIN=python3
  CHECK_NETWORK=0

Relevant env keys:
  R2_BUCKET
  R2_ENDPOINT
  R2_PUBLIC_BASE
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LANE_ROOT="${LANE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ENV_FILE="${ENV_FILE:-$LANE_ROOT/env/lane.env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CHECK_NETWORK="${CHECK_NETWORK:-0}"

load_env_file() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    local key="${line%%=*}"
    local value="${line#*=}"
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done < "$env_file"
}

load_env_file "$ENV_FILE"

"$PYTHON_BIN" - "$CHECK_NETWORK" <<'PY'
import json
import os
import sys

check_network = sys.argv[1] == "1"

fields = {
    "R2_BUCKET": os.environ.get("R2_BUCKET", ""),
    "R2_ENDPOINT": os.environ.get("R2_ENDPOINT", ""),
    "R2_PUBLIC_BASE": os.environ.get("R2_PUBLIC_BASE", ""),
    "R2_ACCESS_KEY_ID": os.environ.get("R2_ACCESS_KEY_ID", ""),
    "R2_SECRET_ACCESS_KEY": os.environ.get("R2_SECRET_ACCESS_KEY", ""),
}

missing = [key for key in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY") if not fields[key]]
if missing:
    print(json.dumps({"status": "missing_config", "missing": missing, "fields": fields}))
    sys.exit(1)

payload = {
    "status": "config_ready",
    "fields": fields,
    "network_checked": check_network,
}

if check_network:
    payload["status"] = "config_ready_no_network_check"

print(json.dumps(payload))
PY
