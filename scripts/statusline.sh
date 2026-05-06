#!/usr/bin/env bash
# FBKit statusline for Claude Code.

G="\033[32m"
V="\033[35m"
R="\033[0m"

CLAUDE=""
if [ ! -t 0 ]; then
  read -r STDIN_JSON
  if [ -n "$STDIN_JSON" ]; then
    IFS='|' read -r model ctx_pct rl5h rl7d <<< "$(echo "$STDIN_JSON" | jq -r '[
      (.model.display_name // ""),
      ((.context_window.used_percentage // 0) | floor | tostring),
      ((.rate_limits.five_hour.used_percentage // 0) | floor | tostring),
      ((.rate_limits.seven_day.used_percentage // 0) | floor | tostring)
    ] | join("|")' 2>/dev/null)"
    if [ -n "$model" ]; then
      CLAUDE="${model} ctx:${G}${ctx_pct}%${R} rl:${G}${rl5h}%${R}/5h ${G}${rl7d}%${R}/7d"
    fi
  fi
fi

BASE="http://127.0.0.1:8100"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

curl -s --max-time 1 "$BASE/health" >"$TMP/health" 2>/dev/null &
curl -s --max-time 1 "$BASE/api/status" >"$TMP/status" 2>/dev/null &
wait

health=$(cat "$TMP/health")
if [ -z "$health" ]; then
  echo -e "${CLAUDE:+$CLAUDE | }FBKit: ${V}DOWN${R}"
  exit 0
fi

status=$(cat "$TMP/status")
if [ -z "$status" ]; then
  echo -e "${CLAUDE:+$CLAUDE | }FBKit: ${G}health ok${R} status:${V}unavailable${R}"
  exit 0
fi

IFS='|' read -r connected sessions pending processing completed failed scheduler_running active_tasks <<< "$(echo "$status" | jq -r '[
  (.extension.connected // false | tostring),
  ((.extension.sessions // []) | length | tostring),
  (.tasks.PENDING // 0 | tostring),
  (.tasks.PROCESSING // 0 | tostring),
  (.tasks.COMPLETED // 0 | tostring),
  (.tasks.FAILED // 0 | tostring),
  (.scheduler.running // false | tostring),
  (.worker.active_tasks // 0 | tostring)
] | join("|")' 2>/dev/null)"

if [ "$connected" = "true" ]; then
  ext="ext:${G}ok${R}/${sessions}"
else
  ext="ext:${V}off${R}/${sessions}"
fi

if [ "$scheduler_running" = "true" ]; then
  sched="sched:${G}on${R}"
else
  sched="sched:${V}off${R}"
fi

tasks="Q:${V}${pending}${R}/${processing} done:${G}${completed}${R} fail:${V}${failed}${R} active:${active_tasks}"

echo -e "${CLAUDE:+$CLAUDE | }FBKit: ${ext} ${sched} ${tasks}"
