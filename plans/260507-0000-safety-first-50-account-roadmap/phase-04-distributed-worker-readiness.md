# Phase 04: Distributed Worker Readiness

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` before implementing. This phase is safety-critical. Do not enable live Facebook actions, do not approve live tasks, and do not build distributed orchestration/control-plane features.

**Goal:** make FBKit safe for multiple worker processes/nodes by replacing process-only same-account live exclusion with a minimal SQLite-backed live account lease, plus read-only node/lease status.

**Status:** Complete as minimal readiness. This phase did not add distributed orchestration/control plane, node assignment, queue federation, remote control, live deployment, or live action tests.

**Architecture:** keep current local-first queue. A worker claims normal dry-run/read-only tasks as today. For live mutating tasks only, worker must acquire an account-scoped DB lease before marking a task `PROCESSING`; other workers skip live tasks for leased accounts until release or expiry. `/api/status` exposes node identity and active leases read-only.

**Tech stack:** Python async worker, FastAPI, SQLite/aiosqlite, pytest.

---

## Context Links

- [Plan overview](./plan.md)
- [Phase 03](./phase-03-multi-profile-local-pilot.md)
- `README.md` safety defaults: dry-run first; live disabled by default
- `docs/codebase-summary.md` lines 126-129: known process-local `_active_live_account_ids` blocker
- `docs/code-standards.md` line 42: DB lease/lock required before multi-process workers
- `agent/worker/processor.py`: `WorkerController._active_live_account_ids`, claim/preflight/dispatch/finally flow
- `agent/db/crud.py`: `claim_next_pending_task`, live arm CRUD, quota reservation, activity logs
- `agent/db/schema.py`: SQLite schema and `_MIGRATIONS`
- `agent/main.py`: `/api/status`

## Scope Lock

### In scope

- DB table for live account leases.
- CRUD helpers for acquire/release/list active leases.
- Worker lease acquisition/release for **live mutating non-dry-run** tasks only.
- Claim-time lease conflict avoidance across worker processes sharing one SQLite DB.
- Expired lease reclaim.
- Read-only `/api/status` exposure: node id + active live leases.
- Tests and docs updates.

### Out of scope / explicit non-goals

- Do **not** enable live actions or change safety defaults.
- Do **not** add SaaS control plane, remote command execution, queue federation, node assignment UI, distributed scheduler, or cross-machine networking.
- Do **not** lease dry-run tasks, read-only tasks, scrape tasks, or tasks that Safety Gate forces dry-run.
- Do **not** replace SQLite.
- Do **not** hold long DB transactions while dispatching browser actions.

## Minimal Schema Shape

Add table in `agent/db/schema.py` `SCHEMA` and `_MIGRATIONS`:

```sql
CREATE TABLE IF NOT EXISTS live_account_lease (
    account_id   TEXT PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    task_id      TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    node_id      TEXT NOT NULL,
    acquired_at  DATETIME NOT NULL,
    heartbeat_at DATETIME NOT NULL,
    expires_at   DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_account_lease_expires ON live_account_lease(expires_at);
CREATE INDEX IF NOT EXISTS idx_live_account_lease_node ON live_account_lease(node_id);
```

Rationale:

- `account_id` primary key enforces one live lease per account.
- `task_id` ties release to the task that acquired the lease.
- `node_id` is observability + ownership check on release; not auth.
- `expires_at` enables crash recovery and stale reclaim.
- No payload changes; backwards-compatible for existing tasks/accounts.

## Minimal API/Status Shape

No new mutating endpoints.

Extend `/api/status` response only:

```json
{
  "worker": {
    "active_tasks": 1,
    "node_id": "host-123:pid-456",
    "active_live_account_ids": ["account-id"],
    "live_account_leases": [
      {
        "account_id": "account-id",
        "task_id": "task-id",
        "node_id": "host-123:pid-456",
        "acquired_at": "2026-05-07T02:00:00",
        "heartbeat_at": "2026-05-07T02:00:00",
        "expires_at": "2026-05-07T02:15:00"
      }
    ]
  }
}
```

Node identity source:

- Add `FBKIT_NODE_ID` optional env var in `agent/config.py`.
- Default: deterministic enough for local process status, e.g. `f"{socket.gethostname()}:{os.getpid()}"`.
- Do not use node id as authorization or account ownership.

Lease TTL:

- Add `LIVE_ACCOUNT_LEASE_TTL_SECONDS` in `agent/config.py`, default `900`.
- Clamp minimum to `60` and maximum to `3600` in config or CRUD helper.
- Risk note: if browser dispatch can exceed TTL, add heartbeat refresh in a later phase. For this minimal phase, release in `finally` + conservative TTL is acceptable; tests cover expired reclaim.

## Data Flows

### Live mutating task claim

1. Worker sees fresh extension session (`FBClient.has_fresh_session`) as Phase 3 already requires.
2. Worker calls `crud.claim_next_pending_task(node_id=worker.node_id, live_lease_ttl_seconds=config.LIVE_ACCOUNT_LEASE_TTL_SECONDS)`.
3. CRUD selects ready `PENDING` tasks ordered by priority/created, bounded to 500.
4. For each candidate:
   - Parse payload safely.
   - Run existing live/dry-run classification using `is_mutating_task`, `enforce_payload`, `dry_run_from_payload`.
   - If dry-run/read-only: claim via existing atomic `UPDATE task SET status='PROCESSING' WHERE id=? AND status='PENDING'`; no lease.
   - If live mutating: attempt SQLite lease upsert for `account_id` only if missing or expired.
   - If lease acquired: claim task. If claim fails due race, release the just-acquired lease by `(account_id, task_id, node_id)` and continue/return none.
   - If lease blocked: skip same-account live candidate, continue scanning.
5. Worker runs existing preflight: auth, live arm, exact `fb_uid`, extension guard, quota.
6. Worker dispatches existing handlers.
7. Worker `finally`: release DB lease and clear process-local set.

### Dry-run claim

1. Worker/CRUD evaluates payload as dry-run.
2. No lease read/write occurs.
3. Existing claim behavior remains: same-account dry-run can run even when live lease exists.

### Expired lease reclaim

1. Stale row remains after crashed worker.
2. New worker attempts live lease upsert.
3. SQLite `ON CONFLICT(account_id) DO UPDATE ... WHERE live_account_lease.expires_at <= ?` replaces expired lease.
4. New worker claims next live task for that account.

### Status exposure

1. `/api/status` reads worker controller `node_id`, `active_live_account_ids`, and `crud.list_active_live_account_leases()`.
2. Response is read-only; no endpoint to create/revoke leases manually.

## Dependency Graph

| Step | Depends on | Blocks |
|---|---|---|
| 1. Tests for schema/CRUD leases | existing `db_ready`, CRUD patterns | Complete |
| 2. Schema migration | none | Complete |
| 3. CRUD lease helpers | schema | Complete |
| 4. Claim integration | CRUD lease helpers, existing `claim_next_pending_task` tests | Complete |
| 5. Worker node/release wiring | claim integration, config node id | Complete |
| 6. `/api/status` exposure | CRUD list helper, worker node property | Complete |
| 7. Docs updates | tests green, final API shape | Complete |

No parallel coding recommended because `agent/db/crud.py` and `agent/worker/processor.py` are shared safety-critical files.

## Files to Modify/Create

### Modify

- `agent/config.py`
  - Add `FBKIT_NODE_ID` and `LIVE_ACCOUNT_LEASE_TTL_SECONDS`.
  - Keep default dry-run/live settings unchanged.
- `agent/db/schema.py`
  - Add `live_account_lease` table and indexes to `SCHEMA`.
  - Add idempotent `_MIGRATIONS` entries.
- `agent/db/crud.py`
  - Add lease helpers:
    - `acquire_live_account_lease(account_id, task_id, node_id, ttl_seconds) -> dict | None`
    - `release_live_account_lease(account_id, task_id, node_id) -> bool`
    - `list_active_live_account_leases() -> list[dict]`
    - optional private `_task_requires_live_account_lease(row) -> bool`
  - Update `claim_next_pending_task(...)` signature to accept `node_id: str | None = None`, `live_lease_ttl_seconds: int | None = None` while preserving existing `excluded_live_account_ids` compatibility.
- `agent/worker/processor.py`
  - Add `node_id` property.
  - Pass node id + TTL into claim.
  - Store live lease identity with the task and release in `finally`.
  - Keep `_active_live_account_ids` as in-process telemetry/defense-in-depth, not the only guard.
- `agent/main.py`
  - Add read-only node id and active lease list to `/api/status` worker block.
- `docs/codebase-summary.md`
  - Replace residual blocker with completed lease behavior after implementation.
- `docs/code-standards.md`
  - Update safety rule 10 from “add DB lease/lock” to “keep DB lease/lock for multi-process live exclusion”.
- `docs/system-architecture.md` and `docs/project-roadmap.md`
  - Update only if implementation changes runtime architecture/status contract.

### Create

- Prefer adding tests to existing files to avoid test sprawl:
  - `tests/unit/test_account_queue_quota.py` for lease claim behavior.
  - `tests/unit/test_live_arming.py` for `/api/status` exposure.
- Create `tests/unit/test_live_account_leases.py` only if existing files become too large/hard to navigate.

## TDD Test List

Write tests first. Verify RED before implementation.

### 1. Lease acquisition conflict

File: `tests/unit/test_account_queue_quota.py`

- Setup: two live `POST_TEXT` tasks for same account, `dryRun=false`, safety monkeypatched live-ready enough to prevent Safety Gate forcing dry-run at insert or use `enforce_safety=False`.
- Act: `lease_1 = await crud.acquire_live_account_lease(account_id, task_1_id, "node-a", 900)` then `lease_2 = await crud.acquire_live_account_lease(account_id, task_2_id, "node-b", 900)`.
- Assert: first returns row; second returns `None`; active lease belongs to `node-a/task_1`.

### 2. Claim skips leased same-account live task and claims other account

- Setup: active lease for account A; pending live task for account A priority 10; pending live task for account B priority 5.
- Act: `claimed = await crud.claim_next_pending_task(node_id="node-b", live_lease_ttl_seconds=900)`.
- Assert: claimed account B; account A task remains `PENDING`; no lease overwritten for account A.

### 3. Dry-run not leased / dry-run exempt

- Setup: active live lease for account A; pending dry-run mutating task for account A priority 10.
- Act: claim next pending with node id.
- Assert: account A dry-run task is claimed; `list_active_live_account_leases()` still only has original live lease; no new lease for dry-run task.

### 4. Lease release

- CRUD-level: acquire lease then `release_live_account_lease(account_id, task_id, "node-a")` returns `True` and active list excludes it.
- Worker-level if practical: monkeypatch `_dispatch` to return success quickly, process a live task with a pre-acquired/claim-acquired lease, assert release happens after `_process_task` finally.

### 5. Release cannot delete another node/task lease

- Setup: lease belongs to `node-a/task-1`.
- Act: release with `node-b` or `task-2`.
- Assert: returns `False`; lease remains.

### 6. Expired lease reclaim

- Setup: insert/acquire lease with expired `expires_at` or monkeypatch time helper if easier.
- Act: acquire same account from `node-b/task-2`.
- Assert: new lease replaces old; `node_id == "node-b"`, `task_id == task_2_id`.

### 7. Claim releases lease when task claim race loses

- Setup: candidate pending live task; monkeypatch/arrange second update changes status before claim update after lease acquisition (can direct-call helper if claim internals are hard).
- Assert: acquired lease is cleaned up when `UPDATE task ... WHERE status='PENDING'` affects zero rows.
- If too brittle, test via a small private helper with focused unit coverage.

### 8. Status exposure

File: `tests/unit/test_live_arming.py`

- Setup: acquire active lease; monkeypatch/config `FBKIT_NODE_ID` or instantiate worker with known node id if constructor accepts override.
- Act: `status = await main.get_status(None)`.
- Assert:
  - `status["worker"]["node_id"]` exists.
  - `status["worker"]["live_account_leases"]` contains account/task/node/expires fields.
  - `status["safety_gate"]["live_actions_enabled"]` remains whatever config says; no enabling occurs.

## Implementation Steps

### Step 1 — RED tests for CRUD leases

- Add tests 1, 5, 6 to `tests/unit/test_account_queue_quota.py` or new `test_live_account_leases.py`.
- Run:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_account_queue_quota.py -q
```

Expected: fail because table/helpers do not exist.

### Step 2 — Schema + CRUD lease helpers

- Add schema/migrations.
- Implement acquire with one short SQLite statement using `INSERT ... ON CONFLICT(account_id) DO UPDATE ... WHERE live_account_lease.expires_at <= ?`.
- Commit only after tests pass.

### Step 3 — RED tests for claim integration

- Add tests 2, 3, 7.
- Run targeted test file. Expected fail before claim integration.

### Step 4 — Integrate leases into `claim_next_pending_task`

- Preserve current signature compatibility: existing callers/tests using `excluded_live_account_ids` still work.
- New behavior only activates when candidate is live mutating non-dry-run and `node_id` is supplied.
- Do not lease dry-run/read-only tasks.

### Step 5 — RED tests for worker release wiring

- Add test 4 worker-level if practical.
- Verify failing due missing worker lease release.

### Step 6 — Worker node id + release

- `WorkerController.__init__` sets `self.node_id` from config.
- Claim call passes `self.node_id` and TTL.
- Track lease tuple separately from process-local active account id:
  - `live_account_id` for telemetry/process-local set.
  - `live_lease = {account_id, task_id, node_id}` for DB release.
- `finally`: release DB lease first or second; either way do both; catch/log release errors without suppressing task result.

### Step 7 — Status exposure

- Add test 8.
- Update `/api/status` worker block with node id, active live account ids, and active leases.
- Keep response read-only.

### Step 8 — Docs

- Update docs listed above after tests green.
- State explicitly: Phase 4 is readiness only, not distributed orchestration.

## Backwards Compatibility Strategy

- Existing DBs migrate via idempotent `CREATE TABLE IF NOT EXISTS` and indexes; no existing table/column changes.
- Existing tasks continue unchanged; no task payload migration.
- Existing `claim_next_pending_task(excluded_live_account_ids=...)` tests/callers remain valid.
- `/api/status` only adds fields; existing clients ignore unknown keys.
- Process-local `_active_live_account_ids` remains for status/defense-in-depth during transition.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| Lease expires while live task still running, another worker reclaims account | Medium | High | Default TTL conservative; release in finally; document future heartbeat if task runtime exceeds TTL; do not use this as permission to enable live actions. |
| Lease acquired then task claim fails, stale lease blocks account | Low | Medium | Claim code must release on `rowcount != 1`; targeted test. |
| SQLite write contention with multiple workers | Medium | Medium | Short single-statement acquire/release; no long transactions; WAL already enabled. |
| Dry-run accidentally blocked by lease | Medium | Medium | Explicit dry-run exemption tests. |
| Wrong lease release deletes another worker's lease | Low | High | Release `WHERE account_id=? AND task_id=? AND node_id=?`; targeted test. |
| Status exposure leaks sensitive data | Low | Medium | Expose IDs/timestamps only; no cookies/session data/payload contents. |
| Implementers build orchestration beyond scope | Medium | High | Scope lock: no mutating lease APIs, no node assignment, no live enablement. |

## Rollback Plan

- Code rollback: revert `agent/config.py`, `agent/db/crud.py`, `agent/worker/processor.py`, `agent/main.py`, and tests/docs changes.
- DB rollback is optional: leave `live_account_lease` table unused; it has no effect if code no longer reads it.
- Emergency runtime rollback without code deploy: stop extra worker processes; run a single worker process so existing process-local guard is sufficient for MVP.
- If leases block work unexpectedly: safe manual DB cleanup may delete rows from `live_account_lease`; this only affects live-mutating lease readiness, not existing tasks. Do not approve/live-dispatch as part of cleanup.

## Test Matrix

| Layer | Tests | Command |
|---|---|---|
| Unit: lease CRUD | acquire conflict, release, release ownership, expired reclaim | `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_account_queue_quota.py -q` |
| Unit: claim behavior | leased same-account skip, dry-run exempt, lost-claim cleanup | `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_account_queue_quota.py -q` |
| Unit: status | `/api/status` exposes node id/leases | `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_live_arming.py -q` |
| Regression: safety | Safety Gate/live arm behavior unchanged | `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py tests\unit\test_live_arming.py tests\unit\test_account_queue_quota.py -q` |
| Full unit | All current unit tests | `& ".\.venv\Scripts\python.exe" -m pytest tests\unit -q` |
| Compile | Python syntax | `& ".\.venv\Scripts\python.exe" -m compileall agent` |
| Optional dashboard | if dashboard types touched | `npm run build` from `dashboard/` |

## Verification Commands

Run from `D:\vm extention  facebook\flowkit`:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_account_queue_quota.py -q
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_live_arming.py -q
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py tests\unit\test_live_arming.py tests\unit\test_account_queue_quota.py -q
& ".\.venv\Scripts\python.exe" -m pytest tests\unit -q
& ".\.venv\Scripts\python.exe" -m compileall agent
```

Safe runtime status smoke, dry-run only:

```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
& ".\.venv\Scripts\python.exe" -m agent.main
curl.exe http://127.0.0.1:8100/api/status
```

Expected runtime smoke: status includes `worker.node_id`; live actions remain disabled; no live task approval or live dispatch occurs.

## Success Criteria

- [x] Two worker processes sharing SQLite cannot claim/execute two live mutating non-dry-run tasks for the same account while lease is active.
- [x] Dry-run same-account tasks remain claimable even when a live lease exists.
- [x] Leases release after task processing success/failure/retry path via `finally`.
- [x] Expired leases can be reclaimed without manual intervention.
- [x] `/api/status` exposes node id and active live account leases read-only.
- [x] Existing Safety Gate/live arm/exact `fb_uid`/extension guard/quota checks remain unchanged.
- [x] Verification commands pass per evidence below.

## Completion Evidence

- Implemented DB-backed live account lease for live mutating non-dry-run tasks across workers sharing one SQLite DB.
- Dry-run/read-only tasks remain exempt from leases.
- Worker keeps process-local `_active_live_account_ids` as telemetry/defense-in-depth; DB lease is now cross-worker guard.
- `/api/status` worker block exposes read-only `node_id`, `active_live_account_ids`, and `live_account_leases`.
- Config added: `FBKIT_NODE_ID` optional, default `hostname:pid`; unique value required per worker process in shared-DB runs. `LIVE_ACCOUNT_LEASE_TTL_SECONDS` default `900`, clamped `60`-`3600`.
- Safety defaults unchanged: no live actions enabled by default; Safety Gate/live arm/API auth/WS auth/exact `fb_uid`/extension guard/quota checks remain intact.
- Verification:
  - `pytest tests\unit\test_account_queue_quota.py -q`: `22 passed in 4.80s`
  - `pytest tests\unit\test_safety_gate.py tests\unit\test_live_arming.py tests\unit\test_account_queue_quota.py -q`: `95 passed in 15.93s`
  - final `pytest tests\unit -q`: `260 passed in 21.20s`
  - `python -m compileall agent`: passed
  - `node --check extension\background.js`: passed
  - dashboard `npm run build`: passed
- Final code review: approved docs sync, no blockers.

## Residual Risks

- Lease heartbeat refresh is not implemented. Keep live tasks within TTL or prioritize heartbeat refresh before long live workflows.
- `/api/status` exposes operational IDs/session metadata. Keep API local or enable API auth before non-local exposure.
- Future hardening: multi-process SQLite contention integration test.

## Unresolved Questions

- What maximum live task duration should trigger heartbeat refresh work?
- Should future diagnostics include recently expired leases, or keep `/api/status` active leases only?
