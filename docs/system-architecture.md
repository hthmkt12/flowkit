# FBKit System Architecture

Last updated: 2026-05-15

## Architecture Summary

FBKit is a local-first automation system. The FastAPI agent owns persistence, safety enforcement, task scheduling, and worker dispatch. The Chrome extension performs guarded browser-side actions through a WebSocket bridge. The React dashboard observes and manages local state through REST and dashboard WebSocket APIs.

## Component Map

| Component | Path | Responsibility |
|---|---|---|
| FastAPI app | `agent/main.py` | Lifespan startup/shutdown, router registration, health/status endpoints, dashboard WebSocket, ZooPost gateway loop task |
| Config | `agent/config.py` | Environment-backed runtime settings |
| Auth | `agent/services/auth.py`, `agent/main.py` | Optional REST API-key validation and WebSocket token checks; both are mandatory for live arming/approval |
| SQLite schema | `agent/db/schema.py` | Tables, indexes, connection lifecycle, lightweight migrations, live account lease table |
| CRUD layer | `agent/db/crud.py` | Account/task/post/message/group/strategy/trace persistence operations, DB-backed live account lease claim, queue/quota summary |
| Safety Gate | `agent/services/safety_gate.py` | Mutating task classification, dry-run defaults, approval policy |
| Live arm control | `agent/api/tasks.py`, `agent/db/crud.py`, `agent/db/schema.py` | Account/task-type/TTL-scoped live-action windows and revocation |
| Worker | `agent/worker/processor.py` | Fresh extension session gate, task claim, DB live account lease wiring, process-local active-account telemetry, quota reservation, retry handling, FBClient dispatch |
| Scheduler | `agent/services/scheduler.py` | Due scheduled post/message claim and enqueue |
| FBClient | `agent/services/fb_client.py` | Multi-extension session registry, stale health metadata, and command routing by `fb_uid` |
| Chrome extension | `extension/` | Facebook page bridge and DOM-action guard |
| ZooPost Cloud gateway | `agent/services/zoopost_cloud_agent.py` | Optional env-enabled gateway loop for dry-run publish dispatches and terminal result reporting |
| Dashboard | `dashboard/` | Local web UI and live event feed |

## Data Flow

```text
REST caller or dashboard
  -> FastAPI router under /api
  -> optional require_api_key
  -> Safety Gate for mutating payloads
  -> SQLite task/post/message/account tables
  -> worker claims pending task
  -> worker confirms at least one fresh extension session exists
  -> worker/CRUD acquires SQLite live account lease for live mutating non-dry-run work
  -> worker re-enforces Safety Gate, live arm, exact fb_uid, extension guard, and quota policy
  -> FBClient chooses exact extension session when fb_uid is required
  -> WebSocket command to Chrome extension
  -> extension DOM-action guard
  -> logged-in Facebook browser session

ZooPost Cloud, when ZOOPOST_CLOUD_API_URL and ZOOPOST_AGENT_CREDENTIAL are set
  -> FastAPI lifespan starts ZooPost gateway loop
  -> local agent opens /agent-gateway/ws with env-only credential
  -> gateway heartbeat reports connected fb_uid profiles and publish-dry-run capability
  -> gateway poll receives dry-run publish dispatches
  -> adapter strips server-owned fields, rejects local media paths, and creates dryRun=true local tasks
  -> worker processes the local dry-run task through the same Safety Gate and extension path
  -> gateway reports terminal result after local completion and cloud ACK
```

## Safety Boundaries

| Boundary | Verified behavior |
|---|---|
| API task creation | Mutating payloads are enforced; client approval/quota/live-arm markers are stripped |
| Live arming | `live_arm` rows require API/WS auth enabled, one account, mutating task types, and TTL <= 900 seconds |
| Approval endpoint | Only pending tasks can be approved; live actions, API/WS auth, and an active matching live arm are required first |
| Worker quota | Live quota reservation is skipped for dry-run tasks and waits for live auth, active `_liveArmId`, and extension guard readiness |
| Worker account live lease | One active live mutating non-dry-run task per account is guarded by SQLite `live_account_lease` across workers sharing one DB; dry-run/read-only tasks are exempt |
| Worker fresh-session gate | Pending work is not claimed while all extension sockets are stale or absent |
| Worker dispatch | Payload is re-enforced; live mutation rechecks API/WS auth, active `_liveArmId`, task account, and extension guard immediately before command dispatch |
| Account routing | Live mutating tasks fail closed if target account lacks `fb_uid`; exact routing prefers fresh duplicate sessions and rejects stale-only matches |
| Extension guard | Extension sessions report profile identity, heartbeat health, and `extension_live_actions_enabled`; mutating methods are blocked when extension live actions are disabled |

## Persistence Model

Verified tables in `agent/db/schema.py`:

- `account`
- `post`
- `message`
- `task`
- `fb_group`
- `activity_log`
- `live_arm`
- `live_account_lease`
- `spy_ad`
- `scraped_data`
- `seed_campaign`
- `task_strategy`
- `task_trace`
- `spy_target`

SQLite runs with WAL mode and foreign keys enabled in `get_db()`.

## Runtime Interfaces

| Interface | Default location | Notes |
|---|---|---|
| Agent REST API | `http://127.0.0.1:8100` | `/health`, `/api/status`, and routers under `/api` |
| Extension WebSocket | `ws://127.0.0.1:9222` | Used by Chrome extension background/content scripts |
| Dashboard dev server | `http://127.0.0.1:5173` | Vite dev server routes ZooPost Cloud prefixes to `127.0.0.1:8200`, keeps FBKit `/api` fallback plus `/health` and `/ws` on `127.0.0.1:8100`, and can inject `ZOOPOST_CLOUD_DEV_BEARER_TOKEN` server-side for cloud API smoke tests |
| ZooPost gateway | Derived `/agent-gateway/ws` from `ZOOPOST_CLOUD_API_URL` | Inert unless `ZOOPOST_CLOUD_API_URL` and `ZOOPOST_AGENT_CREDENTIAL` are set; rejects remote plaintext `http`/`ws`, allows loopback plaintext for local dev, and uses `wss` for `https`/`wss` |
| Dashboard WebSocket | `/ws/dashboard` on API server | Emits event-bus messages to the dashboard |

## Live Control Plane

Live action is a scoped exception, not a mode switch. The current control plane requires all of these to align before live mutating dispatch:

1. `LIVE_ACTIONS_ENABLED=true` and the task remains mutating after Safety Gate enforcement.
2. `API_AUTH_ENABLED=true` and `WS_AUTH_ENABLED=true`.
3. An active `live_arm` row matches the task account, task type, and unexpired TTL window.
4. `POST /api/tasks/{task_id}/approve` stores server-owned `_serverApproved=true`, `_liveArmId`, and `dryRun=false`.
5. Worker claim acquires a SQLite `live_account_lease` before claiming live mutating non-dry-run tasks; leased same-account live tasks are skipped across workers sharing one DB, while dry-run/read-only work remains exempt.
6. Worker quota reservation rechecks auth, arm, exact account `fb_uid`, and extension guard readiness before reserving quota.
7. Worker dispatch rechecks the same specific `_liveArmId`, exact `fb_uid`, and selected extension live guard before sending a mutating command.

`GET /api/status` exposes `safety_gate.api_auth_enabled`, `safety_gate.ws_auth_enabled`, `safety_gate.live_auth_ready`, `safety_gate.active_live_arms`, worker `node_id`, process-local `active_live_account_ids`, active `live_account_leases`, and per-session `extension.sessions[].extension_live_actions_enabled`.

## Multi-Profile Session Health

Each Chrome profile runs its own extension connection. `extension/background.js` sends `profileId`, `profileName`, current `fb_uid`, login state, extension live guard state, and identity-bearing keepalive pings. `FBClient` stores that metadata per WebSocket session and exposes `last_seen_age_s`, `stale`, and `health` in `/api/status`.

Session routing rules:

1. Commands with `fb_uid` require an exact fresh matching session.
2. Duplicate sessions for the same `fb_uid` prefer the most recently seen fresh session.
3. If every exact match is stale, routing returns no session instead of using stale browser state.
4. Heartbeats without current identity do not refresh UID-bound sessions; heartbeat identity changes update or clear the server-side binding.
5. Fallback to any session is only allowed when the caller omits `fb_uid`, and stale sessions are skipped.

For exact account routing, server commands include `expectedFbUid`. The extension background re-reads the current Facebook `c_user` cookie immediately before content-script dispatch and refuses the command if the active browser profile no longer matches the expected UID.

The worker checks `FBClient.has_fresh_session` before claiming tasks. This keeps stale-only sockets from failing queued work. `GET /api/accounts/extension-status` reports stale account sessions as offline/stale while still exposing least-stale duplicate metadata for operator visibility. Dashboard `SafetyGateStatus` and shared session types are stale-aware, so stale sessions do not count as connected/logged in.

## Account-Scoped Queue, Lease, And Quota

The SQLite MVP keeps queue selection in `agent/db/crud.py`. `claim_next_pending_task(...)` scans up to 500 ready pending tasks ordered by priority and creation time. Live mutating non-dry-run candidates require `acquire_live_account_lease(account_id, task_id, node_id, ttl_seconds)` before claim. If another active lease exists for that account, CRUD skips that live candidate and keeps scanning. Dry-run and read-only tasks are exempt from lease reads/writes.

`live_account_lease.account_id` is the primary key. `task_id` and `node_id` are ownership metadata used on release and heartbeat refresh; `expires_at` allows expired lease reclaim after worker crash. `FBKIT_NODE_ID` defaults to `hostname:pid` and should be unique per worker process when multiple workers share one SQLite DB. `LIVE_ACCOUNT_LEASE_TTL_SECONDS` defaults to `900` and is clamped to `60`-`3600`.

While a live mutating task is processing, the worker refreshes the matching account/task/node lease every `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` seconds. The worker clamps the effective interval to at most half of `LIVE_ACCOUNT_LEASE_TTL_SECONDS`, updates `heartbeat_at`, and extends `expires_at` only if the lease still matches and is active; lost, expired, or mismatched leases are not refreshed.

Worker `finally` releases the matching DB lease and clears process-local `_active_live_account_ids`. The process-local set remains status telemetry/defense-in-depth, not the cross-worker guard.

Quota reservation is live-only. `_check_rate_limit()` requires live auth readiness, active matching live arm, exact account `fb_uid`, and extension live guard before calling `reserve_daily_counter()`. `_quotaReserved` stores `counter`, `units`, and `date`, so retry idempotency is scoped to today's counter reservation.

Account visibility is exposed at `GET /api/accounts/{account_id}/queue-summary`. The response comes from `crud.get_account_queue_summary(account_id)` and includes task counts by status, quota usage/limits, stale-counter-aware `used` values, and blocked reasons. This endpoint is the current source for per-account queue/quota diagnostics.

Limits: Phase 4 is distributed worker readiness only, not distributed orchestration/control plane. `/api/status` exposes operational IDs/session metadata, so keep API local or enable API auth before non-local exposure. A multi-process SQLite contention integration test remains future hardening.

## Deployment Shape

Docker support is local-oriented:

- `Dockerfile` uses `python:3.12-slim`, installs `ffmpeg` and Python requirements, exposes `8100` and `9222`, and starts `python -m agent.main`.
- `docker-compose.yaml` builds service `flowkit`, binds ports to `127.0.0.1`, and mounts a `flowkit-runtime` volume at `/app/runtime`.

The Chrome extension still requires a browser profile and logged-in Facebook session outside the container.
