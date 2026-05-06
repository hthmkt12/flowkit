# FBKit Codebase Summary

Last updated: 2026-05-06

## Current Runtime Shape

FBKit is now the only active product in this repository. The old video-generation pipeline has been removed.

| Area | Verified files | Purpose |
|---|---|---|
| Facebook automation worker | `agent/api/posts.py`, `agent/api/tasks.py`, `agent/worker/processor.py` | Queue tasks for post, message, engagement, group/page/friend actions |
| Safety Gate | `agent/services/safety_gate.py`, `tests/unit/test_safety_gate.py` | Enforce dry-run, approval, and live-action boundaries |
| Extension guard | `extension/content-fb.js`, `tests/unit/test_extension_dry_run.py` | Prevent dangerous DOM actions when dry-run or extension live actions are disabled |

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
| `POST /tasks/{task_id}/approve` | `agent/api/tasks.py`, `agent/db/crud.py` | Atomically approves only `PENDING` tasks, adds server-owned approval marker, clears dry-run for live dispatch, logs approval activity |
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
| Worker quota reservation | `agent/db/crud.py`, `agent/worker/processor.py` | Reserves live daily quota after Safety Gate enforcement and before dispatch |
| Worker dispatch | `agent/worker/processor.py` | Re-enforces payload immediately before client dispatch |

Worker dispatch remains the final server-side safety boundary before calling `FBClient` methods.

Live mutating tasks require an account with a resolved `fb_uid` before dispatch. This prevents legacy or incomplete account records from falling back to an arbitrary connected Chrome extension session. Dry-run and read-only tasks can still use fallback routing when no `fb_uid` is requested.

`FBClient` routing is exact-match when a `fb_uid` is provided. It only falls back to any connected session when the caller omits `fb_uid`.

Scheduler enqueue claims scheduled posts/messages before creating tasks, so repeated enqueue attempts for the same item do not create duplicate tasks.

Live quota reservation is skipped for dry-run tasks. For `SEND_BULK_MESSAGE`, quota units equal recipient count. Reserved quota is marked in task payload as server-owned `_quotaReserved` so retries of the same task do not reserve twice. Client-supplied `_quotaReserved` is stripped from external `/tasks` creation.

Live approval is server-owned. External `/tasks` creation strips `approved` and `_serverApproved`; only `POST /tasks/{task_id}/approve` can set `_serverApproved=true` and clear `dryRun` when live actions are enabled. Approval is atomically limited to `PENDING` tasks.

Approval rejects malformed task payload JSON with `400` and writes an `APPROVE_TASK` activity log entry after successful approval.

## Extension DOM-Action Guard

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
| `LIVE_ACTIONS_ENABLED` | `false` | Global switch for real mutating Facebook actions |
| `DRY_RUN_DEFAULT` | `true` | Default dry-run value when live actions are allowed and no explicit flag is provided |
| `APPROVAL_REQUIRED` | `true` | Requires payload approval before live mutation |

## Runtime Dry-Run Validation

Validated dry-run variants:

- `POST_TEXT`
- `LIKE_POST`
- `COMMENT_POST`
- `SEND_MESSAGE`

The validation used `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`, `API_AUTH_ENABLED=false`, and `WS_AUTH_ENABLED=false`. No tasks were approved, no approval endpoints were called, and no live Facebook actions were enabled.

## Current FBKit Readiness Endpoints

| Endpoint | Current use |
|---|---|
| `GET /health` | Basic process check. Current response is `{"status":"ok"}`. |
| `GET /api/status` | FBKit runtime, extension session, worker, scheduler, and task status details. |

Do not use `POST /tasks/{task_id}/approve` as part of safe cleanup or dry-run validation.

## Test Coverage

`tests/unit/test_safety_gate.py` verifies Safety Gate behavior for dry-run enforcement, task creation, approvals, scheduled enqueue, quota reservation, `POST_LINK`, `REUP_VIDEO`, and exact `fb_uid` routing.

`tests/unit/test_extension_dry_run.py` verifies extension-side dry-run enforcement and DOM-action guard behavior.
