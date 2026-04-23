#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/repair-output-ownership.sh <scan|fix> [--help]

Scan or repair ownership drift under a lane runtime output root.

Optional environment overrides:
  OUTPUT_ROOT=/abs/path/to/runtime/output
  EXPECT_OWNER=hth2
  EXPECT_GROUP=hth2
  SUDO_BIN=
  DRY_RUN=0
EOF
}

ACTION="${1:-}"
if [[ -z "$ACTION" || "$ACTION" == "--help" ]]; then
  usage
  exit 0
fi

OUTPUT_ROOT="${OUTPUT_ROOT:-}"
EXPECT_OWNER="${EXPECT_OWNER:-$(id -un)}"
EXPECT_GROUP="${EXPECT_GROUP:-$(id -gn)}"
SUDO_BIN="${SUDO_BIN-sudo}"
DRY_RUN="${DRY_RUN:-0}"

if [[ -z "$OUTPUT_ROOT" ]]; then
  echo '{"status":"missing","detail":"OUTPUT_ROOT is required"}'
  exit 1
fi

collect_candidates() {
  find "$OUTPUT_ROOT" -mindepth 1 \( ! -user "$EXPECT_OWNER" -o ! -group "$EXPECT_GROUP" \) -print | sort
}

print_json() {
  local mode="$1"
  shift
  python3 - "$mode" "$OUTPUT_ROOT" "$EXPECT_OWNER" "$EXPECT_GROUP" "$@" <<'PY'
import json
import sys

mode = sys.argv[1]
output_root = sys.argv[2]
expect_owner = sys.argv[3]
expect_group = sys.argv[4]
items = sys.argv[5:]

payload = {
    "mode": mode,
    "output_root": output_root,
    "expected_owner": expect_owner,
    "expected_group": expect_group,
    "candidate_count": len(items),
}

if mode == "dry_run":
    payload["commands"] = items
else:
    payload["paths"] = items

print(json.dumps(payload))
PY
}

mapfile -t candidates < <(collect_candidates)

case "$ACTION" in
  scan)
    print_json "scan" "${candidates[@]}"
    ;;
  fix)
    if [[ "$DRY_RUN" == "1" ]]; then
      commands=()
      for path in "${candidates[@]}"; do
        if [[ -n "$SUDO_BIN" ]]; then
          commands+=("$SUDO_BIN chown ${EXPECT_OWNER}:${EXPECT_GROUP} $path")
        else
          commands+=("chown ${EXPECT_OWNER}:${EXPECT_GROUP} $path")
        fi
      done
      print_json "dry_run" "${commands[@]}"
      exit 0
    fi

    for path in "${candidates[@]}"; do
      if [[ -n "$SUDO_BIN" ]]; then
        "$SUDO_BIN" chown "${EXPECT_OWNER}:${EXPECT_GROUP}" "$path"
      else
        chown "${EXPECT_OWNER}:${EXPECT_GROUP}" "$path"
      fi
    done
    mapfile -t remaining < <(collect_candidates)
    print_json "fix" "${remaining[@]}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
