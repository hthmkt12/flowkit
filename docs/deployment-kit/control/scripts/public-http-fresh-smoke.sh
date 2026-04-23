#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/public-http-fresh-smoke.sh [--help]

Create one tiny control-routed project and poll until the chapter reaches
completed or failed, then print the final artifact URLs.

Required environment:
  POSTGRES_DSN

Optional environment overrides:
  CONTROL_PROFILE_FILE
  CONTROL_API_URL=http://127.0.0.1:18080
  SOURCE_TITLE=Public HTTP Fresh Smoke
  SOURCE_BRIEF=Minimal single-scene proof
  TARGET_DURATION_SECONDS=8
  CHAPTER_COUNT=1
  MATERIAL_ID=realistic
  WAIT_TIMEOUT_SECONDS=1200
  POLL_INTERVAL_SECONDS=15
  PYTHON_BIN=python3
  DRY_RUN=1
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTROL_ROOT="${CONTROL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CONTROL_PROFILE_FILE="${CONTROL_PROFILE_FILE:-}"
DRY_RUN="${DRY_RUN:-0}"

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

if [[ -n "$CONTROL_PROFILE_FILE" ]]; then
  load_env_file "$CONTROL_PROFILE_FILE"
fi

CONTROL_API_URL="${CONTROL_API_URL:-http://127.0.0.1:18080}"
SOURCE_TITLE="${SOURCE_TITLE:-}"
if [[ -z "$SOURCE_TITLE" ]]; then
  SOURCE_TITLE="Public HTTP Fresh Smoke $(date '+%Y-%m-%d %H-%M-%S')"
fi
SOURCE_BRIEF="${SOURCE_BRIEF:-Minimal single-scene proof that a brand-new control-routed chapter stores artifacts directly as public HTTP URLs.}"
TARGET_DURATION_SECONDS="${TARGET_DURATION_SECONDS:-8}"
CHAPTER_COUNT="${CHAPTER_COUNT:-1}"
MATERIAL_ID="${MATERIAL_ID:-realistic}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-1200}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-15}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export CONTROL_API_URL SOURCE_TITLE SOURCE_BRIEF TARGET_DURATION_SECONDS CHAPTER_COUNT MATERIAL_ID
export WAIT_TIMEOUT_SECONDS POLL_INTERVAL_SECONDS POSTGRES_DSN

if [[ "$DRY_RUN" == "1" ]]; then
  "$PYTHON_BIN" - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "status": "dry_run",
            "control_api_url": os.environ.get("CONTROL_API_URL", ""),
            "source_title": os.environ.get("SOURCE_TITLE", ""),
            "source_brief": os.environ.get("SOURCE_BRIEF", ""),
            "target_duration_seconds": int(os.environ.get("TARGET_DURATION_SECONDS", "8")),
            "chapter_count": int(os.environ.get("CHAPTER_COUNT", "1")),
            "material_id": os.environ.get("MATERIAL_ID", "realistic"),
            "wait_timeout_seconds": int(os.environ.get("WAIT_TIMEOUT_SECONDS", "1200")),
            "poll_interval_seconds": int(os.environ.get("POLL_INTERVAL_SECONDS", "15")),
            "postgres_dsn_present": bool(os.environ.get("POSTGRES_DSN")),
        }
    )
)
PY
  exit 0
fi

if [[ -z "${POSTGRES_DSN:-}" ]]; then
  echo "POSTGRES_DSN is required" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
import time
from urllib.request import Request, urlopen

import psycopg

control_api_url = os.environ["CONTROL_API_URL"].rstrip("/")
payload = {
    "source_title": os.environ["SOURCE_TITLE"],
    "source_brief": os.environ["SOURCE_BRIEF"],
    "target_duration_seconds": int(os.environ["TARGET_DURATION_SECONDS"]),
    "material_id": os.environ["MATERIAL_ID"],
    "chapter_count": int(os.environ["CHAPTER_COUNT"]),
}
request = Request(
    f"{control_api_url}/projects",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urlopen(request, timeout=30) as response:
    create_payload = json.load(response)

project = create_payload["project"]
chapters = create_payload["chapters"]
chapter_id = chapters[0]["id"]

deadline = time.time() + int(os.environ["WAIT_TIMEOUT_SECONDS"])
poll_interval = float(os.environ["POLL_INTERVAL_SECONDS"])
last_snapshot = None
final_payload = None

while time.time() < deadline:
    with psycopg.connect(os.environ["POSTGRES_DSN"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select c.id::text, c.status, c.chapter_output_uri, c.chapter_metadata
                from chapters c
                where c.id = %s
                """,
                (chapter_id,),
            )
            chapter_row = cur.fetchone()
            cur.execute(
                """
                select j.job_type, j.status, j.attempt_count, j.error_text
                from jobs j
                where j.chapter_id = %s
                order by j.created_at asc
                """,
                (chapter_id,),
            )
            jobs = cur.fetchall()
            cur.execute(
                """
                select artifact_type, storage_uri
                from artifacts
                where chapter_id = %s
                order by created_at asc
                """,
                (chapter_id,),
            )
            artifacts = cur.fetchall()

    snapshot = {
        "chapter": chapter_row,
        "jobs": jobs,
        "artifacts": artifacts,
    }
    last_snapshot = snapshot
    if chapter_row[1] in {"completed", "failed"}:
        final_payload = snapshot
        break
    time.sleep(poll_interval)
else:
    raise SystemExit(json.dumps({"status": "timeout", "project": project, "chapter_id": chapter_id, "last_snapshot": last_snapshot}, default=str))

artifact_urls = [row[1] for row in final_payload["artifacts"]]
print(
    json.dumps(
        {
            "status": final_payload["chapter"][1],
            "project": project,
            "chapter_id": chapter_id,
            "chapter": final_payload["chapter"],
            "jobs": final_payload["jobs"],
            "artifacts": final_payload["artifacts"],
            "artifact_urls": artifact_urls,
        },
        default=str,
    )
)
PY
