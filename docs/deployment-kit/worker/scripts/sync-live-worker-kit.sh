#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/sync-live-worker-kit.sh [--help]

Sync the canonical deployment-kit worker files from this repo to one or more
live lane roots on a remote VM over SSH/SCP.

Optional environment overrides:
  SOURCE_ROOT
  REMOTE_HOST
  LANE_ROOTS
  SSH_BIN
  SCP_BIN
  DRY_RUN=1

Defaults:
  SOURCE_ROOT=<repo>/docs/deployment-kit/worker
  REMOTE_HOST=hth2-box
  LANE_ROOTS="/home/hth2/flowkit-worker-demo /home/hth2/flowkit-worker-demo-lane-02"
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_ROOT="${SOURCE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REMOTE_HOST="${REMOTE_HOST:-hth2-box}"
LANE_ROOTS="${LANE_ROOTS:-/home/hth2/flowkit-worker-demo /home/hth2/flowkit-worker-demo-lane-02}"
SSH_BIN="${SSH_BIN:-ssh}"
SCP_BIN="${SCP_BIN:-scp}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DRY_RUN="${DRY_RUN:-0}"

copy_items=(
  "fk_worker"
  "scripts"
  "requirements.txt"
  "lane.env.example"
  "docker-compose.worker.yml"
  "Dockerfile.worker"
)

for item in "${copy_items[@]}"; do
  if [[ ! -e "$SOURCE_ROOT/$item" ]]; then
    echo "Missing source item: $SOURCE_ROOT/$item" >&2
    exit 1
  fi
done

to_scp_local_path() {
  local path="$1"
  if [[ "$SCP_BIN" == *.exe ]] && command -v wslpath >/dev/null 2>&1; then
    wslpath -w "$path"
    return
  fi
  printf '%s\n' "$path"
}

read -r -a lane_roots <<< "$LANE_ROOTS"
if [[ "${#lane_roots[@]}" -eq 0 ]]; then
  echo "No lane roots configured" >&2
  exit 1
fi

if [[ "$DRY_RUN" == "1" ]]; then
  copy_items_json="$(printf '%s\n' "${copy_items[@]}" | "$PYTHON_BIN" -c "import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))")"
  lane_roots_json="$(printf '%s\n' "${lane_roots[@]}" | "$PYTHON_BIN" -c "import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))")"
  "$PYTHON_BIN" - "$REMOTE_HOST" "$SOURCE_ROOT" "$lane_roots_json" "$copy_items_json" <<'PY'
import json
import sys

print(
    json.dumps(
        {
            "status": "dry_run",
            "remote_host": sys.argv[1],
            "source_root": sys.argv[2],
            "lane_roots": json.loads(sys.argv[3]),
            "copy_items": json.loads(sys.argv[4]),
        }
    )
)
PY
  exit 0
fi

for lane_root in "${lane_roots[@]}"; do
  "$SSH_BIN" "$REMOTE_HOST" "mkdir -p '$lane_root'"
  for item in "${copy_items[@]}"; do
    local_path="$(to_scp_local_path "$SOURCE_ROOT/$item")"
    "$SCP_BIN" -r "$local_path" "$REMOTE_HOST:$lane_root/"
  done
  "$SSH_BIN" "$REMOTE_HOST" "find '$lane_root/scripts' -maxdepth 1 -type f -name '*.sh' -exec chmod +x {} +"
done

printf '{"status":"completed","remote_host":"%s","lane_root_count":%s}\n' "$REMOTE_HOST" "${#lane_roots[@]}"
