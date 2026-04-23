#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/upload-artifacts.sh CHAPTER_ID [--cleanup-stale] [--help]

Replay the worker upload stage for one completed chapter using the local lane
root. This is intended for zero-credit artifact replay after CONCAT_CHAPTER has
already produced a final file.

Optional environment overrides:
  LANE_ROOT
  ENV_FILE
  PYTHON_BIN
  DRY_RUN=1
  FORCE_NO_LOCAL_FALLBACK=1
  CLEANUP_STALE=0

Behavior notes:
  - default behavior forces ALLOW_LOCAL_ARTIFACT_FALLBACK=0 for this replay
  - --cleanup-stale deletes older artifact rows for the same chapter, keeping
    only the newest rows created by the current replay
EOF
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LANE_ROOT="${LANE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ENV_FILE="${ENV_FILE:-$LANE_ROOT/env/lane.env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DRY_RUN="${DRY_RUN:-0}"
FORCE_NO_LOCAL_FALLBACK="${FORCE_NO_LOCAL_FALLBACK:-1}"
CLEANUP_STALE="${CLEANUP_STALE:-0}"

CHAPTER_ID="${1:-}"
if [[ "$CHAPTER_ID" == "--help" || "$CHAPTER_ID" == "-h" ]]; then
  usage
  exit 0
fi
if [[ -z "$CHAPTER_ID" ]]; then
  usage
  exit 1
fi
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cleanup-stale)
      CLEANUP_STALE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

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

if [[ "$FORCE_NO_LOCAL_FALLBACK" == "1" ]]; then
  export ALLOW_LOCAL_ARTIFACT_FALLBACK=0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  "$PYTHON_BIN" - "$CHAPTER_ID" "$LANE_ROOT" "$ENV_FILE" "$CLEANUP_STALE" <<'PY'
import json
import os
import sys

print(
    json.dumps(
        {
            "status": "dry_run",
            "chapter_id": sys.argv[1],
            "lane_root": sys.argv[2],
            "env_file": sys.argv[3],
            "cleanup_stale": sys.argv[4] == "1",
            "lane_id": os.environ.get("LANE_ID", ""),
            "r2_bucket": os.environ.get("R2_BUCKET", ""),
            "r2_public_base": os.environ.get("R2_PUBLIC_BASE", ""),
            "allow_local_artifact_fallback": os.environ.get("ALLOW_LOCAL_ARTIFACT_FALLBACK", "0") == "1",
        }
    )
)
PY
  exit 0
fi

"$PYTHON_BIN" - "$CHAPTER_ID" "$LANE_ROOT" "$CLEANUP_STALE" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import psycopg

chapter_id = sys.argv[1]
lane_root = Path(sys.argv[2])
cleanup_stale = sys.argv[3] == "1"

sys.path.insert(0, str(lane_root))

from fk_worker.config import settings
from fk_worker.stages import handle_upload_artifacts
from fk_worker.storage import get_chapter
from fk_worker.upload import s3_client


def verify_uploaded_uri(uri: str) -> dict:
    if uri.startswith("https://"):
        request = Request(uri, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            response.read(64)
            return {
                "uri": uri,
                "mode": "http",
                "status": response.status,
                "content_type": response.headers.get_content_type(),
                "content_length": response.headers.get("content-length"),
            }

    prefix = f"s3://{settings.r2_bucket}/"
    if uri.startswith(prefix):
        key = uri.split(prefix, 1)[1]
        head = s3_client().head_object(Bucket=settings.r2_bucket, Key=key)
        return {
            "uri": uri,
            "mode": "s3",
            "content_type": head.get("ContentType"),
            "content_length": head.get("ContentLength"),
            "etag": head.get("ETag"),
        }

    if uri.startswith("file://"):
        raise RuntimeError(f"Unexpected local fallback URI during replay: {uri}")

    raise RuntimeError(f"Unsupported storage URI: {uri}")


chapter = get_chapter(chapter_id)
if not chapter:
    raise SystemExit(json.dumps({"status": "chapter_not_found", "chapter_id": chapter_id}))

with psycopg.connect(settings.postgres_dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            select id::text, artifact_type, storage_uri, created_at
            from artifacts
            where chapter_id = %s
            order by created_at desc, id desc
            """,
            (chapter_id,),
        )
        before_rows = cur.fetchall()

result = handle_upload_artifacts(chapter, {})
uploaded = result.get("uploaded", [])
verifications = [verify_uploaded_uri(uri) for uri in uploaded]

deleted_rows = []
after_rows = []
chapter_meta = None

with psycopg.connect(settings.postgres_dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            select id::text, artifact_type, storage_uri, created_at
            from artifacts
            where chapter_id = %s
            order by created_at desc, id desc
            """,
            (chapter_id,),
        )
        current_rows = cur.fetchall()

        keep_ids = set()
        for uri in uploaded:
            for row_id, artifact_type, storage_uri, created_at in current_rows:
                if storage_uri == uri:
                    keep_ids.add(row_id)
                    break

        if cleanup_stale and keep_ids:
            cur.execute(
                """
                delete from artifacts
                where chapter_id = %s
                  and id::text <> all(%s)
                returning id::text, artifact_type, storage_uri
                """,
                (chapter_id, list(keep_ids)),
            )
            deleted_rows = cur.fetchall()

        cur.execute(
            """
            select artifact_type, storage_uri
            from artifacts
            where chapter_id = %s
            order by created_at desc, id desc
            """,
            (chapter_id,),
        )
        after_rows = cur.fetchall()

        cur.execute(
            """
            select chapter_metadata->>'upload_mode', chapter_metadata->>'uploaded_uris'
            from chapters
            where id = %s
            """,
            (chapter_id,),
        )
        chapter_meta = cur.fetchone()

print(
    json.dumps(
        {
            "status": "completed",
            "chapter_id": chapter_id,
            "lane_id": settings.lane_id,
            "cleanup_stale": cleanup_stale,
            "before_count": len(before_rows),
            "after_count": len(after_rows),
            "upload_result": result,
            "verifications": verifications,
            "deleted_rows": deleted_rows,
            "artifacts": after_rows,
            "chapter_metadata_summary": chapter_meta,
        },
        default=str,
    )
)
PY
