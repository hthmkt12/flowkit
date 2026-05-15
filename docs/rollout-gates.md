# FBKit Rollout Gates

Last updated: 2026-05-07

## Overview

FBKit is dry-run first. This rollout path describes verified progression gates only. It does not validate 50-account support, distributed orchestration, or live Facebook action safety.

No 50-account support is validated. Do not use a main Facebook account for live tests or pilot work.

## Gate 0: Local dry-run

Purpose: prove the local agent, extension bridge, task queue, and dashboard work without live Facebook mutations.

Required settings:

Inline check values: `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`.

```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
```

Pass criteria:

- `curl.exe http://127.0.0.1:8100/health` returns `{"status":"ok"}`.
- `/api/status` reports Safety Gate state and at least one fresh extension session when Chrome is connected.
- `scripts/fbkit-dry-run-smoke.py` completes with `dryRun=true`.
- No task approval endpoint is called.

Stop if:

- Extension session is stale or missing `fb_uid`.
- Any dry-run smoke task attempts live navigation/click/type/file upload.

## Gate 1: One dedicated test account

Purpose: prove exact account routing and operator visibility for one non-main account.

Required guardrails:

- Do not use a main Facebook account.
- Live-readiness auth values for any controlled live test are `API_AUTH_ENABLED=true` and `WS_AUTH_ENABLED=true`; do not set these for normal dry-run smoke validation unless testing auth behavior.
- Keep `LIVE_ACTIONS_ENABLED=false` for dry-run validation.
- Confirm local account `fb_uid` matches `/api/status` extension session `fb_uid`.
- Confirm dashboard shows one fresh logged-in session.

Pass criteria:

- `POST_TEXT`, `LIKE_POST`, `COMMENT_POST`, and `SEND_MESSAGE` dry-run variants remain dry-run.
- `GET /api/accounts/{account_id}/queue-summary` reports queue/quota state.
- No live arm or approval is needed for validation.

## Gate 2: Two-profile dry-run pilot

Purpose: prove duplicate profile isolation and exact `fb_uid` routing.

Required guardrails:

- Two Chrome profiles, one extension instance per profile.
- Each profile reports distinct `profileId`/`profileName` and `fb_uid`.
- `EXTENSION_LIVE_ACTIONS_ENABLED=false` remains in the extension.

Pass criteria:

- Commands with a target `fb_uid` route only to the fresh matching session.
- Stale duplicate sessions do not shadow fresh sessions.
- Dashboard does not count stale sessions as connected/logged-in.

## Gate 3: Five-profile dry-run pilot

Purpose: gather local resource and stale-session behavior evidence before larger pilots.

Required guardrails:

- Keep dry-run settings from Gate 0.
- Record CPU, memory, reconnect behavior, stale sessions, and failed dry-runs.
- Do not approve tasks.

Pass criteria:

- Worker does not claim tasks when only stale sockets exist.
- No wrong-account dry-run dispatch observed.
- Operator can map every session to account/profile in `/api/status`.

## Gate 4: Ten-profile dry-run pilot

Purpose: decide whether local scheduled low-concurrency operation is enough.

Required guardrails:

- Keep live actions disabled.
- Keep pilot traffic low frequency.
- Record browser/profile resource usage and queue latency.

Pass criteria:

- Queue and quota summaries stay understandable per account.
- Stale profile recovery remains operator-visible.
- No 50-account rollout decision is made without documented evidence.

## Gate 5: Distributed readiness review

Purpose: review Phase 4 readiness controls before any multi-worker process sharing one SQLite DB.

Required guardrails:

- `FBKIT_NODE_ID` must be unique per worker process when multiple workers share one DB.
- `LIVE_ACCOUNT_LEASE_TTL_SECONDS` must exceed expected live task duration.
- `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` should be shorter than the lease TTL; the worker clamps the effective heartbeat interval to at most half of `LIVE_ACCOUNT_LEASE_TTL_SECONDS`.
- `/api/status` exposes operational metadata: node IDs, account IDs, session metadata, live arms, and live account leases.
- Keep the API bound to localhost or enable `API_AUTH_ENABLED=true` before non-local exposure.

Pass criteria:

- DB-backed `live_account_lease` prevents same-account live mutating non-dry-run claims across workers sharing one DB.
- Dry-run and read-only tasks remain lease-exempt.
- Final validation commands pass before any rollout claim.

## Controlled Live Test Gate

This gate is optional and requires explicit human approval.

Before any controlled live test:

- Use a dedicated test/business asset only.
- Set `LIVE_ACTIONS_ENABLED=true` only for the controlled test window.
- Set `API_AUTH_ENABLED=true` and `WS_AUTH_ENABLED=true` before live arming or approval.
- Create a short-lived live arm for the exact account and task type.
- Approve one reviewed pending task only.
- Confirm the extension live-action guard was intentionally changed for the dedicated test profile.
- Stop after one low-risk action and record the result.

Do not test live actions on a main account. Do not test inbox/comment/engagement automation before low-risk posting is proven safe.

## Verification Commands

Run from the project root:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit -q
& ".\.venv\Scripts\python.exe" -m compileall agent
node --check "extension\background.js"
```

Run dashboard build from `dashboard/`:

```powershell
npm run build
```

## Rollout Claims

Allowed claims:

- Local dry-run support is verified by tests and smoke scripts.
- Multi-profile session routing/readiness is implemented and unit-tested.
- DB-backed live account lease readiness is implemented and unit-tested for workers sharing one SQLite DB.

Disallowed claims:

- 50-account support is validated.
- Distributed deployment is validated.
- Live Facebook automation is generally safe.
- Main-account live automation is safe.

## Unresolved Questions

- What maximum live task duration should drive lease heartbeat refresh design?
- Should `/api/status` gain a sanitized mode for non-local dashboards?
- Should future validation include a real multi-process SQLite contention test?
