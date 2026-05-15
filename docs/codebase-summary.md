# FBKit Codebase Summary

Last updated: 2026-05-07

Source basis: existing repository summary plus direct verification against selected source files and Phase 4 validation evidence. No generated artifact is required to read this document.

## Current Runtime Shape

FBKit is the active product in this repository. It is a local-first Facebook automation assistant with a Python FastAPI agent, SQLite persistence, a background worker/scheduler stack, a Chrome extension WebSocket bridge, and a React/Vite dashboard.

The old video-generation pipeline is not part of the current runtime.

| Area | Verified files | Purpose |
|---|---|---|
| FastAPI runtime | `agent/main.py`, `agent/config.py`, `agent/services/auth.py` | REST API, dashboard WebSocket, extension WebSocket startup, optional API-key auth |
| Facebook automation worker | `agent/api/posts.py`, `agent/api/tasks.py`, `agent/worker/processor.py` | Queue and dispatch post, message, engagement, group/page/friend actions with DB-backed live account leases and fresh-session preclaim gating |
| Persistence | `agent/db/schema.py`, `agent/db/crud.py` | SQLite tables for accounts, posts, messages, tasks, groups, activity logs, live arms, live account leases, seed campaigns, spy ads, strategies, traces |
| Safety Gate | `agent/services/safety_gate.py`, `tests/unit/test_safety_gate.py` | Enforce dry-run, approval, and live-action boundaries |
| Extension guard | `extension/background.js`, `extension/content-fb.js`, `tests/unit/test_extension_dry_run.py` | Reports profile identity, heartbeat/guard readiness, and prevents dangerous DOM actions when dry-run or extension live actions are disabled |
| Dashboard UI | `dashboard/src/App.tsx`, `dashboard/src/pages/*.tsx`, `dashboard/vite.config.ts` | Local React dashboard for accounts, tasks, seeding, spy ads, logs, live status |

Previous repomix pack metrics: 129 files, about 160.5k tokens, security check passed with no suspicious files detected.

## Startup and Local Services

| Service | Verified file | Current behavior |
|---|---|---|
| Agent API | `agent/main.py` | `uvicorn` serves `agent.main:app` on `API_HOST`/`API_PORT`, default `127.0.0.1:8100` |
| Extension WebSocket | `agent/main.py` | `websockets.serve()` listens on `WS_HOST`/`WS_PORT`, default `127.0.0.1:9222` |
| Dashboard WebSocket | `agent/main.py` | FastAPI WebSocket endpoint at `/ws/dashboard` emits event-bus messages |
| Worker | `agent/worker/processor.py` | Waits for at least one fresh extension session, then claims one task before dispatch and respects concurrency/retry rules |
| Scheduler | `agent/services/scheduler.py` | Claims due scheduled posts/messages and creates corresponding tasks |
| Auto-seeder, spy monitor, notifier | `agent/main.py` | Started during FastAPI lifespan startup |

Docker support exists in `Dockerfile` and `docker-compose.yaml`. The compose service is named `flowkit`, binds API and extension WebSocket ports to localhost, and mounts `flowkit-runtime` at `/app/runtime`.

## API and Auth Surface

All routers under `/api` use `require_api_key` from `agent/services/auth.py`. Auth is disabled by default (`API_AUTH_ENABLED=false`). When enabled, callers must send either `X-API-Key` or `Authorization: Bearer <key>`.

Verified route groups:

| Route group | File | Examples |
|---|---|---|
| `/api/accounts` | `agent/api/accounts.py` | list/create/update/delete accounts, activity, extension status, account queue summary |
| `/api/tasks` | `agent/api/tasks.py` | list/create tasks, stats, pending count, approve/cancel/delete, engagement helper, live arm create/revoke |
| `/api/posts` | `agent/api/posts.py` | post CRUD, scheduled posts, reup-video task creation |
| `/api/messages` | `agent/api/messages.py` | message CRUD, scheduled messages, bulk message task creation |
| `/api/groups` | `agent/api/groups.py` | group CRUD and join/leave/scrape task helpers |
| `/api/seeding` | `agent/api/seeding.py` | seed campaign stats, create, stop, delete |
| `/api/spy` | `agent/api/spy.py` | spy target stats, target CRUD, ad listing |
| `/api/strategies`, `/api/traces` | `agent/api/strategies.py` | learned task strategies and execution traces |

Top-level verified endpoints:

| Endpoint | Current use |
|---|---|
| `GET /` | Basic app metadata plus extension and worker status |
| `GET /health` | Basic process check. Current response is `{"status":"ok"}`. |
| `GET /api/status` | FBKit runtime, extension session including live guard state, worker `node_id`, process-local active live account IDs, active live account leases, scheduler, seeder, spy, notifier, session, Safety Gate auth readiness, active live arms, and task status details. |
| `WS /ws/dashboard` | Dashboard live event feed. Uses WS token check only when `WS_AUTH_ENABLED=true`. |

## Safety Gate Behavior

`agent/services/safety_gate.py` centralizes payload safety defaults for mutating Facebook task types.

### Mutating tasks

Verified mutating task types include:

- `POST_TEXT`, `POST_IMAGE`, `POST_VIDEO`, `POST_LINK`, `POST_STORY`, `POST_REEL`
- `REUP_VIDEO`
- `SEND_MESSAGE`, `SEND_BULK_MESSAGE`
- `LIKE_POST`, `COMMENT_POST`, `SHARE_POST`
- `ADD_FRIEND`, `ACCEPT_FRIEND`
- `JOIN_GROUP`, `LEAVE_GROUP`
- `FOLLOW_PAGE`, `UNFOLLOW_PAGE`

`CHECK_LOGIN` is treated as read-only and does not receive `dryRun` or `safetyReason` defaults.

### Enforcement rules

`enforce_payload(task_type, payload)` returns a copied payload and applies these rules:

| Condition | Result |
|---|---|
| task is read-only | payload unchanged |
| `LIVE_ACTIONS_ENABLED=false` | forces `dryRun=true`, sets `safetyReason=live_actions_disabled` if absent |
| `APPROVAL_REQUIRED=true` and payload is not approved | forces `dryRun=true`, sets `safetyReason=approval_required` if absent |
| neither of the above and `dryRun` missing | sets `dryRun` from `DRY_RUN_DEFAULT`; if true, sets `safetyReason=dry_run_default` |

`dry_run_from_payload(payload)` reads the enforced `dryRun` flag and converts common truthy values safely.

## Safety Gate Entry Points

| Entry point | Verified file | Behavior |
|---|---|---|
| `POST /tasks` | `agent/api/tasks.py` | Enforces payload before `crud.create_task()` |
| `POST /tasks/{task_id}/approve` | `agent/api/tasks.py`, `agent/db/crud.py` | Requires live actions enabled, API/WS auth enabled, and active matching live arm; atomically approves only `PENDING` tasks, stores server-owned `_serverApproved` and `_liveArmId`, clears dry-run, logs approval activity |
| `POST /tasks/live-arm` | `agent/api/tasks.py`, `agent/db/crud.py` | Creates a scoped live arm only when API/WS auth are enabled; scope is account, mutating task types, and TTL <= 900 seconds |
| `POST /tasks/live-arm/{arm_id}/revoke` | `agent/api/tasks.py`, `agent/db/crud.py` | Revokes an active live arm by setting `revoked_at` |
| `POST /tasks/engage` | `agent/api/tasks.py` | Enforces LIKE/COMMENT/SHARE payload before task creation |
| `POST /posts` with `auto_queue=true` and no `scheduled_at` | `agent/api/posts.py` | Builds `POST_{post_type}` payload, enforces it, then creates task |
| `POST /posts/reup` | `agent/api/posts.py` | Enforces `REUP_VIDEO` payload before task creation |
| `POST /groups/join` | `agent/api/groups.py` | Enforces `JOIN_GROUP` payload before task creation |
| `POST /groups/leave` | `agent/api/groups.py` | Enforces `LEAVE_GROUP` payload before task creation |
| `POST /messages` with `auto_queue=true` and no `scheduled_at` | `agent/api/messages.py` | Enforces `SEND_MESSAGE` payload before task creation |
| `POST /messages/bulk` with `auto_queue=true` | `agent/api/messages.py` | Enforces `SEND_BULK_MESSAGE` payload before task creation |
| Auto-seeding campaign action | `agent/services/auto_seed.py` | Enforces LIKE/COMMENT/SHARE payload before task creation |
| Scheduler post enqueue | `agent/services/scheduler.py` | Enforces scheduled post payload before task creation |
| Scheduler message enqueue | `agent/services/scheduler.py` | Enforces scheduled message payload before task creation |
| Worker task claim | `agent/db/crud.py`, `agent/worker/processor.py` | Moves one pending task to `PROCESSING` before async dispatch |
| Worker live account lease | `agent/db/crud.py`, `agent/worker/processor.py`, `agent/db/schema.py` | Bounded scan of ready pending tasks leases live mutating non-dry-run work by account in SQLite; leased same-account live work is skipped across workers sharing one DB; dry-run/read-only work is exempt |
| Worker quota reservation | `agent/db/crud.py`, `agent/worker/processor.py` | Reserves live daily quota after Safety Gate enforcement, auth/arm/extension guard checks, and exact account `fb_uid` validation |
| Worker dispatch | `agent/worker/processor.py` | Re-enforces payload immediately before client dispatch |
| Account queue summary | `agent/api/accounts.py`, `agent/db/crud.py` | `GET /api/accounts/{account_id}/queue-summary` returns queue counts, quota usage, stale-counter-aware counters, and blocked reasons |

Worker dispatch remains the final server-side safety boundary before calling `FBClient` methods.

Live mutating tasks require an account with a resolved `fb_uid` before dispatch. This prevents legacy or incomplete account records from falling back to an arbitrary connected Chrome extension session. Dry-run and read-only tasks can still use fallback routing when no `fb_uid` is requested.

`FBClient` routing is exact-match when a `fb_uid` is provided. It prefers the freshest non-stale duplicate session for that `fb_uid`, returns no session when all exact matches are stale, and only falls back to any fresh connected session when the caller omits `fb_uid`.

Scheduler enqueue claims scheduled posts/messages before creating tasks, so repeated enqueue attempts for the same item do not create duplicate tasks.

Live quota reservation is skipped for dry-run tasks. Before reserving quota for a live mutating task, the worker verifies API/WS auth readiness, the specific active `_liveArmId`, exact account `fb_uid`, and extension live guard readiness for the selected `fb_uid`. For `SEND_BULK_MESSAGE`, quota units equal recipient count. Reserved quota is marked in task payload as server-owned `_quotaReserved` with `counter`, `units`, and `date`; retries of the same task do not reserve twice only when the reservation matches the same counter, has enough units, and is for today's date. Client-supplied `_quotaReserved` is stripped from external `/tasks` creation.

`WorkerController` passes `node_id` and `LIVE_ACCOUNT_LEASE_TTL_SECONDS` into `crud.claim_next_pending_task(...)`. CRUD scans at most 500 ready pending tasks ordered by priority and creation time. Live mutating non-dry-run candidates must acquire or reclaim a row in `live_account_lease` before task claim; candidates blocked by another active lease are skipped. Same-account dry-run tasks and read-only tasks are not leased or blocked by the lease. If a claim race is lost after lease acquisition, the lease is released.

While a live mutating task is processing, `WorkerController` refreshes the matching account/task/node lease every `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` using `crud.refresh_live_account_lease(...)`. The effective heartbeat interval is clamped to at most half of `LIVE_ACCOUNT_LEASE_TTL_SECONDS` so misconfiguration cannot schedule the first heartbeat after lease expiry. Refresh updates `heartbeat_at` and extends `expires_at` only for the active matching lease; mismatched or expired leases are not refreshed and fail closed.

`WorkerController` still maintains process-local `_active_live_account_ids` around async processing for telemetry/defense-in-depth and exposes it through `/api/status`, but the SQLite lease is now the cross-worker same-account live guard for workers sharing one SQLite DB.

The worker now waits for `FBClient.has_fresh_session` before claiming pending tasks. Stale-only sockets do not trigger queued work and therefore do not immediately fail tasks because an old browser session remained registered.

When worker preflight fails, `_check_rate_limit()` records `last_rate_limit_error` for auth readiness, missing active arm, missing exact `fb_uid`, extension guard, malformed quota payload, or exhausted quota. `_fail_task_for_rate_limit()` persists that specific reason instead of always writing `Daily rate limit exceeded`.

Live approval and live arm binding are server-owned. External `/tasks` creation strips `approved`, `_serverApproved`, `_quotaReserved`, and `_liveArmId`; only `POST /tasks/{task_id}/approve` can set `_serverApproved=true`, bind an active `_liveArmId`, and clear `dryRun` when live actions, API auth, WS auth, and a matching live arm are all active. Approval is atomically limited to `PENDING` tasks.

Approval rejects malformed task payload JSON with `400` and writes an `APPROVE_TASK` activity log entry after successful approval.

## Live Arm Model

`agent/db/schema.py` defines `live_arm` as the explicit live-action window table:

| Column | Purpose |
|---|---|
| `id` | Server-generated arm identifier stored in approved task payload as `_liveArmId` |
| `account_id` | Account scope; live dispatch only accepts a matching task account |
| `task_types` | JSON list of allowed mutating task types |
| `expires_at` | Expiry timestamp; TTL must be positive and `<= 900` seconds at creation |
| `created_by`, `created_at` | Operator/audit metadata |
| `revoked_at` | Revocation marker; revoked arms are inactive |

`crud.arm_live_actions()` rejects arms unless both `API_AUTH_ENABLED` and `WS_AUTH_ENABLED` are true. It also rejects empty task type lists, non-mutating task types such as `CHECK_LOGIN`, unknown task types, and excessive TTL values.

`crud.get_active_live_arm()` returns an arm only when the requested ID is active, unexpired, unrevoked, scoped to the task account, and includes the exact task type.

## Live Account Lease Model

`agent/db/schema.py` defines `live_account_lease` as a minimal distributed-worker readiness table:

| Column | Purpose |
|---|---|
| `account_id` | Primary key and account scope for one active live mutating task |
| `task_id` | Task that acquired the lease; release must match this task |
| `node_id` | Worker identity for visibility and release ownership check |
| `acquired_at`, `heartbeat_at` | Acquisition and latest refresh metadata |
| `expires_at` | Crash-recovery expiry; active list returns rows with `expires_at > now` |

`crud.acquire_live_account_lease(account_id, task_id, node_id, ttl_seconds)` inserts or replaces only expired same-account leases. `ttl_seconds` is clamped to `60`-`3600`; default config is `LIVE_ACCOUNT_LEASE_TTL_SECONDS=900`. `crud.refresh_live_account_lease(account_id, task_id, node_id, ttl_seconds)` extends only the matching active lease. `crud.release_live_account_lease(account_id, task_id, node_id)` deletes only the matching account/task/node lease. `crud.list_active_live_account_leases()` powers read-only `/api/status` visibility.

## Extension DOM-Action Guard

`extension/background.js` reports `extensionLiveActionsEnabled`, `profileId`, `profileName`, current `fb_uid`, and login state in the `extension_ready` handshake and ping keepalive. `agent/services/fb_client.py` stores these as `extension_live_actions_enabled`, `profile_id`, and `profile_name` per session, updates or clears session identity when heartbeat identity changes, ignores identity-less heartbeats for UID-bound sessions, exposes `last_seen_age_s`, `stale`, and `health` through `/api/status`, and lets the worker fail closed when the selected session does not report the live guard enabled.

Server-routed extension commands include `expectedFbUid` when a task targets an exact Facebook account. The background worker re-reads the current `c_user` cookie before dispatching to content scripts and refuses the command if the browser profile has switched accounts since the server selected the session.

`extension/content-fb.js` keeps a centralized `MUTATING_METHODS` set at the message router. When `EXTENSION_LIVE_ACTIONS_ENABLED=false`, mutating extension methods are blocked before handler dispatch and return a dry-run result with `safetyReason=extension_live_actions_disabled`.

Handler-level dry-run checks remain as a second extension-side boundary before navigation, click, type, upload, or keyboard-submit DOM actions.

## `POST_LINK` Dispatch Behavior

`agent/worker/processor.py` dispatches `POST_LINK` through the existing text-post client path:

1. Safety Gate enforcement runs first.
2. Worker reads `content` from payload.
3. Worker reads the link from `linkUrl`, `url`, or `link`.
4. If a link exists, it appends the link to content separated by a newline.
5. Worker calls `client.post_text(...)` with the combined content.

## Configuration Keys

Verified in `agent/config.py`:

| Variable | Default | Purpose |
|---|---:|---|
| `API_HOST` | `127.0.0.1` | FastAPI bind host |
| `API_PORT` | `8100` | FastAPI bind port |
| `WS_HOST` | `127.0.0.1` | Extension WebSocket bind host |
| `WS_PORT` | `9222` | Extension WebSocket bind port |
| `API_AUTH_ENABLED` | `false` | Enables REST API-key auth |
| `API_KEY` | empty | API key used when REST auth is enabled |
| `WS_AUTH_ENABLED` | follows `API_AUTH_ENABLED` | Enables extension/dashboard WebSocket token checks |
| `WS_API_KEY` | `API_KEY` | WebSocket auth key |
| `DB_PATH` | `fbkit.db` | SQLite database path |
| `MEDIA_DIR` | `media` | Local media storage directory |
| `POLL_INTERVAL` | `5` | Worker poll interval in seconds |
| `MAX_RETRIES` | `3` | Default task retry cap |
| `MAX_CONCURRENT_TASKS` | `1` | Worker concurrency limit |
| `FBKIT_NODE_ID` | `hostname:pid` | Optional worker identity. Must be unique per worker process when multiple workers share one SQLite DB. |
| `LIVE_ACCOUNT_LEASE_TTL_SECONDS` | `900` | Live account lease TTL for live mutating non-dry-run tasks; clamped to `60`-`3600` seconds |
| `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` | `60` | Refresh interval for matching live account leases while live mutating tasks are processing; clamped to `5`-`300` seconds |
| `LIVE_ACTIONS_ENABLED` | `false` | Global switch for real mutating Facebook actions |
| `DRY_RUN_DEFAULT` | `true` | Default dry-run value when live actions are allowed and no explicit flag is provided |
| `APPROVAL_REQUIRED` | `true` | Requires payload approval before live mutation |
| `SCHEDULER_CHECK_INTERVAL` | `30` | Scheduler polling interval in seconds |
| `ACTION_DELAY_MIN` / `ACTION_DELAY_MAX` | `2.0` / `8.0` | Human-like delay range before worker actions |
| `TYPING_DELAY_MIN` / `TYPING_DELAY_MAX` | `40` / `150` | Typing simulation delay in milliseconds |
| `RATE_LIMIT_POSTS`, `RATE_LIMIT_MESSAGES`, `RATE_LIMIT_LIKES`, `RATE_LIMIT_COMMENTS`, `RATE_LIMIT_FRIENDS` | `20`, `50`, `100`, `50`, `20` | Daily account counters |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | empty | Optional notifier settings |
| `SPY_ADS_CHECK_INTERVAL` | `3600` | Spy ads monitor interval in seconds |

## Dashboard

The dashboard is a Vite React app in `dashboard/`.

| Verified file | Behavior |
|---|---|
| `dashboard/package.json` | Scripts: `dev`, `build`, `lint`, `test`, `preview`; runtime deps include React 19, React Router 7, and lucide-react; dev deps include Vite 8, Tailwind 4, Vitest, jsdom, and Testing Library for dashboard-local hook tests |
| `dashboard/vite.config.ts` | Dev server port `5173`; routes ZooPost Cloud prefixes (`/api/channels`, `/api/content-items`, `/api/media-assets`, `/api/publish-jobs`, `/api/live-arms`, `/api/dashboard`, `/api/agent-installations`) and `/agent-gateway` to `127.0.0.1:8200`; keeps FBKit fallback `/api`, `/health`, and `/ws` on `127.0.0.1:8100`; supports server-side-only `ZOOPOST_CLOUD_DEV_BEARER_TOKEN`; Vitest uses `jsdom` via the local Vite config |
| `dashboard/src/App.tsx` | Routes: `/`, `/accounts`, `/tasks`, `/seeding`, `/spy`, `/logs` |
| `dashboard/src/pages/DashboardPage.tsx` | Polls status/task/account/seeding/spy APIs and renders live event feed from dashboard WebSocket |
| `dashboard/src/api/useWebSocket.test.ts` | Hook-level regression coverage for dashboard WebSocket reconnect, dual-consumer isolation, and unmount cleanup behavior with mocked `WebSocket` and fake timers |

Dashboard session types include `profile_id`, `profile_name`, `last_seen_age_s`, `stale`, and `health`. `SafetyGateStatus` counts only fresh non-stale extension sessions as connected/logged in, so stale sessions no longer make the dashboard look live-ready.

`GET /api/accounts/extension-status` chooses the least-stale duplicate session metadata for an account but reports stale sessions as `extension_online=false` with `extension_health="stale"`.

## Account Queue Summary

`crud.get_account_queue_summary(account_id)` returns:

| Field | Meaning |
|---|---|
| `account_id` | Requested account ID |
| `fb_uid` | Account Facebook UID when present |
| `queue` | Task counts grouped by status for that account |
| `quota` | Daily counter usage and configured limits for posts, messages, likes, comments, and friends |
| `blocked_reasons` | Account status and exhausted quota reasons such as `account_status:SUSPENDED` or `quota_exhausted:daily_posts` |

If `daily_reset_at` is not today's date, queue summary treats stale daily counters as zero for displayed `used` values and blocked-reason calculation. Missing accounts return `blocked_reasons: ["account_not_found"]`.

## Runtime Dry-Run Validation

Validated dry-run variants:

- `POST_TEXT`
- `LIKE_POST`
- `COMMENT_POST`
- `SEND_MESSAGE`

The validation used `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`, `API_AUTH_ENABLED=false`, and `WS_AUTH_ENABLED=false`. No tasks were approved, no approval endpoints were called, and no live Facebook actions were enabled.

Do not use `POST /tasks/{task_id}/approve` as part of safe cleanup or dry-run validation.

## Test Coverage

`tests/unit/test_safety_gate.py` verifies Safety Gate behavior for dry-run enforcement, task creation, approvals, scheduled enqueue, quota reservation, `POST_LINK`, `REUP_VIDEO`, and exact `fb_uid` routing.

`tests/unit/test_account_queue_quota.py` verifies DB-backed live account lease acquisition/release/reclaim behavior, claim-time lease conflict skipping, dry-run lease exemption, queue summary quota reporting, stale daily counters, preflight error reasons, exact `fb_uid` before quota reservation, process-local live account mark/clear behavior, and date-scoped `_quotaReserved` markers.

`tests/unit/test_extension_dry_run.py` verifies extension-side dry-run enforcement and DOM-action guard behavior.

`tests/unit/test_live_arming.py` verifies live arm auth requirements, server-owned `_liveArmId`, approval/live-dispatch checks, quota readiness checks, extension guard readiness, active live arms plus worker node/lease metadata in `/api/status`, and API-key enforcement for live arm endpoints.

`tests/unit/test_multi_profile_sessions.py` and `tests/unit/test_dashboard_session_types.py` verify profile identity metadata, identity-bound heartbeat freshness, logout/account-switch identity updates, stale health metadata, fresh duplicate preference for exact `fb_uid` routing, stale-only worker gating, account extension status behavior, and dashboard stale-aware session typing/connectivity.

Latest reported validation for Phase 4 distributed worker readiness: `pytest tests\unit\test_account_queue_quota.py -q` passed with `22 passed in 4.80s`; `pytest tests\unit\test_safety_gate.py tests\unit\test_live_arming.py tests\unit\test_account_queue_quota.py -q` passed with `95 passed in 15.93s`; `pytest tests\unit -q` passed with `260 passed in 21.20s`; `python -m compileall agent` passed; `node --check extension\background.js` passed; dashboard `npm run build` passed. Final code review approved docs sync with no blockers.

Phase 4 is minimal readiness only. It does not add distributed orchestration, node assignment, queue federation, remote control, or live action enablement. Residual risks: `/api/status` exposes operational IDs/session metadata, so keep API local or enable API auth before non-local exposure; add a future multi-process SQLite contention integration test.

## Rollout Gates

`docs/rollout-gates.md` is the source of truth for progression gates. It covers local dry-run, one dedicated test account, 2/5/10 profile dry-run pilots, distributed readiness review, and an explicitly approved controlled-live test gate.

The rollout gates intentionally do not validate 50-account support, distributed deployment, broad live Facebook automation safety, or main-account live automation safety.
