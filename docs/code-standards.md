# FBKit Code Standards

Last updated: 2026-05-07

## Repository Structure

| Path | Purpose |
|---|---|
| `agent/` | Python FastAPI agent, APIs, services, SQLite access, worker |
| `agent/api/` | FastAPI routers mounted under `/api` |
| `agent/db/` | SQLite schema, connection, CRUD helpers, default strategy seed data |
| `agent/services/` | Safety Gate, extension client, scheduler, auth, notifier, seeding, spy ads |
| `agent/worker/` | Background task processor |
| `extension/` | Chrome Manifest V3 extension and Facebook content script |
| `dashboard/` | React/Vite dashboard |
| `scripts/` | Runtime and smoke-test helper scripts |
| `tests/` | Pytest unit tests |
| `docs/` | Project documentation source of truth |

## Python Standards

- Keep API request models close to their router files (`agent/api/*.py`).
- Route all external mutating task payloads through `agent/services/safety_gate.py`.
- Do not trust client-supplied `_serverApproved`, `approved`, `_quotaReserved`, or `_liveArmId` fields.
- Use `agent/db/crud.py` for database mutations; avoid ad hoc SQL in routers unless the CRUD layer already exposes no fit.
- Preserve async boundaries: API routes, worker, scheduler, and database calls are async.
- Keep `CHECK_LOGIN` and scrape tasks read-only unless the code changes Safety Gate classification.
- Keep account queue/quota summaries in CRUD-derived data so API responses reflect persisted task/account state.
- Treat extension session health as freshness-based. Do not claim or route queued work through stale-only WebSocket sessions.

## Safety Gate Rules

1. Add new mutating task types to `MUTATING_TASK_TYPES` in `agent/services/safety_gate.py`.
2. Enforce payloads before task creation and before worker dispatch.
3. Keep live dispatch blocked unless server config, API auth, WebSocket auth, active scoped live arm, server-owned approval, exact `fb_uid`, quota readiness, and extension guard readiness allow it.
4. Require exact `fb_uid` routing for live mutating tasks; do not allow fallback sessions for live mutation.
5. Prefer fresh duplicate sessions for exact `fb_uid`; stale exact matches must fail closed instead of dispatching to old browser state.
6. Keep live arm scope narrow: one account, mutating task types only, positive TTL, and TTL `<= 900` seconds.
7. Store `_liveArmId` only from the approval path; strip it from external task creation payloads.
8. Keep live quota reservation after auth, active arm, exact account `fb_uid`, and extension guard checks.
9. Keep `_quotaReserved` server-owned, date-scoped, and idempotent only for the same counter/date/units coverage.
10. Keep the DB-backed live account lease/lock path for live mutating non-dry-run tasks before relying on multiple worker processes sharing one SQLite DB; dry-run/read-only tasks must remain lease-exempt.
11. Keep `FBKIT_NODE_ID` unique per worker process in shared-DB runs. Treat worker `node_id`, `active_live_account_ids`, and `live_account_leases` in `/api/status` as operational metadata; keep API local or enable API auth before non-local exposure.
12. Add or update tests in `tests/unit/test_safety_gate.py`, `tests/unit/test_live_arming.py`, `tests/unit/test_account_queue_quota.py`, or multi-profile session tests for any safety behavior change.

## API Standards

- Routers should use clear prefixes matching domain nouns: `/accounts`, `/tasks`, `/posts`, `/messages`, `/groups`, `/seeding`, `/spy`.
- Keep response formats aligned with existing CRUD dictionaries returned by `agent/db/crud.py`.
- Use `HTTPException` with explicit status codes for missing resources, invalid requests, and unsafe approval attempts.
- API auth is centralized through `agent/services/auth.py` and added in `agent/main.py` router registration.
- Live arm endpoints are safety-critical API paths. They must stay protected by API auth when auth is enabled and must reject arming unless both API and WebSocket auth are configured on.
- Account queue/quota visibility belongs under account routes; current verified endpoint is `GET /api/accounts/{account_id}/queue-summary`.
- `/api/status` may expose worker node IDs, live account lease rows, and extension session metadata. Do not add mutating lease-management endpoints without a new safety review.

## Frontend Standards

- Dashboard code lives under `dashboard/src/`.
- Shared API helpers live in `dashboard/src/api/`.
- Shared TypeScript types live in `dashboard/src/types/`.
- Pages are route-level components in `dashboard/src/pages/` and are wired from `dashboard/src/App.tsx`.
- Dev proxy configuration belongs in `dashboard/vite.config.ts`.

## Extension Standards

- Keep extension-side live-action safety independent from server-side Safety Gate.
- Report extension live guard state in `extension_ready` as `extensionLiveActionsEnabled`; server status exposes this per session as `extension_live_actions_enabled`.
- Report stable profile identity as `profileId` and `profileName`; server status exposes these as `profile_id` and `profile_name`.
- Keep heartbeat updates identity-bound. A keepalive for a UID-bound session must include current `fb_uid`/login state; identity-less heartbeats must not make an old UID binding fresh.
- Exact account commands should carry `expectedFbUid`, and the extension must refuse dispatch if the current Facebook `c_user` cookie does not match it.
- Mutating content-script methods must check dry-run or extension live-action guard before navigation, clicks, typing, uploads, or keyboard submission.
- Manifest permissions should stay limited to local agent URLs and Facebook host permissions needed by the extension.

## Verification Commands

Use the repository virtualenv on Windows:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py -q
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_crud.py -q
& ".\.venv\Scripts\python.exe" -m pytest
```

Dashboard checks:

```powershell
npm run build
npm run lint
```

Run dashboard commands from `dashboard/`.

## Documentation Standards

- Keep durable project docs in `docs/`.
- Update [Codebase Summary](./codebase-summary.md) after architecture, runtime, config, API, or Safety Gate changes.
- Update [Common Issues](./common-issues.md) after confirmed bug fixes or recurring runtime failures.
- Do not document endpoints, flags, or functions unless verified in code.
