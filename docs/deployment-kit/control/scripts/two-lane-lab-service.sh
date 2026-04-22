#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/two-lane-lab-service.sh <start|park|status> [--help]

Coordinate the same-VM lab control service plus lane-01 and lane-02 host-process runners.

Optional environment overrides:
  CONTROL_SERVICE_SCRIPT=/abs/path/to/control-service.sh
  LANE_01_SERVICE_SCRIPT=/abs/path/to/lane-01/lane-service.sh
  LANE_02_SERVICE_SCRIPT=/abs/path/to/lane-02/lane-service.sh
EOF
}

ACTION="${1:-}"
if [[ -z "$ACTION" || "$ACTION" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTROL_SERVICE_SCRIPT="${CONTROL_SERVICE_SCRIPT:-$SCRIPT_DIR/control-service.sh}"
LANE_01_SERVICE_SCRIPT="${LANE_01_SERVICE_SCRIPT:-/home/hth2/flowkit-worker-demo/scripts/lane-service.sh}"
LANE_02_SERVICE_SCRIPT="${LANE_02_SERVICE_SCRIPT:-/home/hth2/flowkit-worker-demo-lane-02/scripts/lane-service.sh}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

run_json_action() {
  local script_path="$1"
  local action="$2"
  if [[ ! -x "$script_path" ]]; then
    if [[ -f "$script_path" ]]; then
      chmod +x "$script_path"
    else
      echo "{\"status\":\"missing\",\"detail\":\"$script_path\"}"
      return 0
    fi
  fi
  bash "$script_path" "$action"
}

print_status() {
  local control_json lane01_json lane02_json
  control_json="$(run_json_action "$CONTROL_SERVICE_SCRIPT" status)"
  lane01_json="$(run_json_action "$LANE_01_SERVICE_SCRIPT" status)"
  lane02_json="$(run_json_action "$LANE_02_SERVICE_SCRIPT" status)"

  "$PYTHON_BIN" - "$control_json" "$lane01_json" "$lane02_json" <<'PY'
import json
import sys

control = json.loads(sys.argv[1])
lane_01 = json.loads(sys.argv[2])
lane_02 = json.loads(sys.argv[3])

print(json.dumps({"control": control, "lane_01": lane_01, "lane_02": lane_02}))
PY
}

case "$ACTION" in
  start)
    run_json_action "$CONTROL_SERVICE_SCRIPT" start >/dev/null
    run_json_action "$LANE_01_SERVICE_SCRIPT" start >/dev/null
    run_json_action "$LANE_02_SERVICE_SCRIPT" start >/dev/null
    print_status
    ;;
  park)
    run_json_action "$LANE_01_SERVICE_SCRIPT" stop >/dev/null
    run_json_action "$LANE_02_SERVICE_SCRIPT" stop >/dev/null
    run_json_action "$CONTROL_SERVICE_SCRIPT" stop >/dev/null
    print_status
    ;;
  status)
    print_status
    ;;
  *)
    usage
    exit 1
    ;;
esac
