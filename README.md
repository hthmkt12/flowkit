# FBKit

FBKit is a local-first Facebook automation assistant. It uses a Python FastAPI agent, a SQLite task queue, and a Chrome extension WebSocket bridge to run Facebook tasks through a logged-in browser session.

**Positioning snapshot:** FBKit is a safer local-first alternative to cloud social automation tools for agencies and marketers that need control, account-level safety gating, and operational visibility.

> **Safety default:** FBKit is dry-run first. Real mutating Facebook actions are disabled by default at both the server Safety Gate and the Chrome extension DOM-action layer.
> Live mutating dispatch now also requires API auth, WebSocket auth, a scoped live arm, server approval, exact `fb_uid` routing, quota readiness, and an extension live guard that reports enabled.
> Phase 3 multi-profile support is stale-aware: extension sessions report profile identity, guard state, current `fb_uid`, and heartbeat health; workers wait for a fresh extension session before claiming queued work, and exact `fb_uid` routing ignores stale duplicate sockets.
> Phase 4 worker readiness adds a SQLite-backed live account lease for live mutating non-dry-run tasks across worker processes sharing one DB. Dry-run/read-only tasks remain lease-exempt; this is readiness only, not a distributed orchestration/control plane.

For verified Safety Gate entry points and current runtime behavior, see `docs/codebase-summary.md`.

For the broader project overview, architecture, standards, and roadmap, see the `docs/` directory.

## Quick Start

### 1. Start the agent in safe local mode

PowerShell:

```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
.\.venv\Scripts\python.exe -m agent.main
```

Or use the safe Windows helper at `scripts/start-fbkit-safe.ps1`:

```powershell
.\scripts\start-fbkit-safe.ps1
```

Preview the safe environment and command without starting the agent:

```powershell
.\scripts\start-fbkit-safe.ps1 -PrintOnly
```

Bash/Git Bash/WSL:

```bash
LIVE_ACTIONS_ENABLED=false \
DRY_RUN_DEFAULT=true \
APPROVAL_REQUIRED=true \
API_AUTH_ENABLED=false \
WS_AUTH_ENABLED=false \
python -m agent.main
```

The agent listens on:

- REST API: `http://127.0.0.1:8100`
- Extension WebSocket: `ws://127.0.0.1:9222`

### 2. Load and connect the Chrome extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select `extension/`.
4. Open `https://www.facebook.com/` and sign in.
5. Verify the extension session:

```powershell
curl.exe http://127.0.0.1:8100/api/status
```

Look for a logged-in session with a non-empty `fb_uid`:

```json
{
  "extension": {
    "connected": true,
    "sessions": [{"fb_uid": "...", "logged_in": true}]
  }
}
```

### 3. Run the safe dry-run smoke test

```powershell
.\.venv\Scripts\python.exe scripts\fbkit-dry-run-smoke.py
```

The smoke script:

- checks `/api/status`
- finds the logged-in extension `fb_uid`
- finds or creates a matching local account
- submits exactly one task with `dryRun=true`
- defaults to `POST_TEXT`, with optional safe variants: `LIKE_POST`, `COMMENT_POST`, `SEND_MESSAGE`
- passes only if the task completes with `dryRun=true`
- does **not** approve tasks and does **not** request live dispatch

Run a specific dry-run variant:

```powershell
.\.venv\Scripts\python.exe scripts\fbkit-dry-run-smoke.py --variant LIKE_POST --content "https://www.facebook.com/example/posts/123"
```

Validated dry-run variants:

- `POST_TEXT`
- `LIKE_POST`
- `COMMENT_POST`
- `SEND_MESSAGE`

Clean up smoke helper processes when you are done:

```powershell
.\scripts\stop-fbkit-smoke.ps1
```

The cleanup helper stops identifiable FBKit agent listeners on ports `8100` and `9222`, removes stale agent smoke PID files, and keeps Chrome open by default. Pass `-IncludeChrome` only if you started a dedicated smoke Chrome profile and want to close it too.

## Safety Gate Defaults

FBKit centralizes mutation safety in `agent/services/safety_gate.py`.

| Env var | Safe default | Purpose |
|---|---:|---|
| `LIVE_ACTIONS_ENABLED` | `false` | Global switch for live Facebook mutations |
| `DRY_RUN_DEFAULT` | `true` | Default to dry-run when no explicit payload flag is provided |
| `APPROVAL_REQUIRED` | `true` | Require server-owned `_serverApproved=true` before live mutation |
| `API_AUTH_ENABLED` | `false` | Must be `true` before creating live arms or approving live tasks |
| `WS_AUTH_ENABLED` | follows `API_AUTH_ENABLED` | Must be `true` before creating live arms or approving live tasks |
| `FBKIT_NODE_ID` | `hostname:pid` | Optional worker identity for lease/status visibility; must be unique per worker process sharing one DB |
| `LIVE_ACCOUNT_LEASE_TTL_SECONDS` | `900` | Live account lease TTL for live mutating tasks; clamped to `60`-`3600` seconds |
| `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` | `60` | Live account lease refresh interval while a live mutating task is processing; clamped to `5`-`300` seconds |

Mutating task types include posting, messaging, liking, commenting, sharing, friend actions, group actions, page follow/unfollow, and video reup tasks.

Additional protections:

- external `/api/tasks` creation strips client-supplied approval/quota markers
- external `/api/tasks` creation also strips client-supplied `_liveArmId`; live arm IDs are server-owned
- live arms are stored in SQLite, scoped to one account, mutating task types, and a TTL of at most 900 seconds
- `POST /api/tasks/{task_id}/approve` requires `LIVE_ACTIONS_ENABLED=true`, API/WS auth enabled, and an active matching live arm before storing `_serverApproved=true`, `_liveArmId`, and `dryRun=false`
- worker re-enforces Safety Gate immediately before extension dispatch
- worker live dispatch rechecks API/WS auth, the specific active `_liveArmId`, exact task account, and the extension live guard before sending mutating commands
- worker waits for at least one fresh extension session before claiming tasks, so stale-only sockets do not fail queued work
- live quota is reserved before live dispatch, skipped for dry-run tasks, and not reserved until live auth, arm, and extension guard readiness all pass
- live quota reservation is date-scoped and idempotent for the same task retry; dry-run tasks remain exempt from live quota reservation
- the worker uses a SQLite-backed live account lease to block same-account live mutating non-dry-run claims across workers sharing one DB; same-account dry-run/read-only work remains exempt
- the worker refreshes the matching SQLite live account lease during processing so long live mutating tasks do not expire while still running
- the worker still reports process-local `active_live_account_ids` as telemetry/defense-in-depth, but the DB lease is the cross-worker guard
- `FBClient` requires exact `fb_uid` routing when a task targets a specific Facebook account
- `FBClient` marks sessions stale by heartbeat age and prefers the freshest duplicate session for exact `fb_uid` routing
- identity-bound extension heartbeat requires current `fb_uid`/login state; identity-less keepalives do not refresh old UID bindings, and extension dispatch refuses commands when the browser profile's current `c_user` differs from the server-selected `expectedFbUid`
- live mutating worker tasks fail closed if the account has no resolved `fb_uid`
- `/api/status` reports API/WS auth readiness, active live arms, worker `node_id`, process-local `active_live_account_ids`, active `live_account_leases`, and extension live guard state under extension sessions
- `/api/status` and dashboard session types include stale session health metadata; dashboard connectivity counts only fresh sessions
- `GET /api/accounts/{account_id}/queue-summary` reports queue counts, quota usage, stale-counter-aware used values, and blocked reasons for one account
- extension mutating handlers return before navigation/click/type/file-upload when `dryRun=true` or when `EXTENSION_LIVE_ACTIONS_ENABLED=false`
- extension-local live-action guard forces dry-run with `safetyReason: "extension_live_actions_disabled"`, independent of server payload approval

## Live Action Warning

Do **not** enable live Facebook actions on your main account as a first test.

Before any live test:

1. Create a dedicated test Facebook account/page/group.
2. Keep `LIVE_ACTIONS_ENABLED=false` until dry-run smoke tests pass.
3. Start with one low-risk post task.
4. Enable both `API_AUTH_ENABLED=true` and `WS_AUTH_ENABLED=true`; live arming and approval fail closed without both.
5. Create a short-lived live arm for the exact account and task type. TTL must be `<= 900` seconds.
6. Approve the pending task through the server approval endpoint only after reviewing the payload.
7. Confirm the extension-side `EXTENSION_LIVE_ACTIONS_ENABLED` guard has been intentionally changed for a controlled test; otherwise the extension still forces dry-run.
8. Do not live-test inbox/comment/engagement automation until the posting flow is proven safe.

## Current Docs

- `docs/marketing-overview.md` — compact go-to-market strategy, channel priorities, messaging, and near-term actions.
- `ARCHITECTURE.md` — current FBKit architecture.
- `docs/project-overview-pdr.md` — verified product scope, requirements, and acceptance criteria.
- `docs/codebase-summary.md` — verified Safety Gate behavior and runtime entry points.
- `docs/code-standards.md` — repository structure, safety rules, and verification commands.
- `docs/system-architecture.md` — component map, data flow, persistence model, and runtime interfaces.
- `docs/project-roadmap.md` — milestone status and documentation backlog.
- `docs/rollout-gates.md` — dry-run, multi-profile, distributed-readiness, and controlled-live progression gates.
- `docs/common-issues.md` — FBKit troubleshooting notes.
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` — agent safety/development rules.

## Legacy Removal Note

The old video-generation pipeline has been removed. It is no longer part of this repository and should not be used for current work.
