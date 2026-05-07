# Phase 02: Account-Scoped Queue And Quota

## Context Links

- [Plan overview](./plan.md)
- [Phase 01](./phase-01-safety-control-plane.md)
- `agent/worker/processor.py`
- `agent/services/scheduler.py`
- `agent/db/crud.py`
- `agent/db/schema.py`

## Overview

Priority: P1  
Status: Complete

Prepare FBKit to manage many accounts without requiring 50 simultaneous live sessions. The implemented target is controlled single-process live-account exclusion, live-only quota reservation, and per-account queue/quota visibility.

## Key Insights

- 50 managed accounts is different from 50 simultaneous browser actions.
- Account-level fairness prevents one account or campaign from starving others.
- Per-account quota is the minimum safety layer before multi-profile operation.
- Phase 2 keeps the SQLite MVP: live same-account exclusion is process-local, not a distributed lock.

## Requirements

Functional:

- Ensure task selection can respect account-level live concurrency in the single-worker process. **Done:** `claim_next_pending_task(excluded_live_account_ids=...)` skips same-account live mutating tasks.
- Add per-account rate windows for posts, messages, likes, comments, friend/group/page actions. **Done for existing daily counters surfaced by queue summary.**
- Make quota reservation idempotent across retries. **Done:** `_quotaReserved` includes `date`, `counter`, and `units`.
- Add visibility for each account's queue depth, quota usage, and blocked reason. **Done:** `GET /api/accounts/{account_id}/queue-summary`.
- Preserve dry-run behavior where quota reservation is skipped or simulated only. **Done:** dry-run tasks bypass live quota and same-account live exclusion.

Non-functional:

- Keep SQLite unless evidence shows it is the bottleneck.
- Avoid adding Redis/Celery before local queue limits are proven.

## Architecture

Proposed scheduling model:

```text
pending tasks
  -> group by account_id
  -> skip disconnected or unarmed live accounts
  -> enforce per-account concurrency = 1 for live mutation
  -> reserve quota idempotently
  -> dispatch through exact fb_uid session
```

Initial concurrency target should be conservative: dry-run can be broader, live mutation should be one active mutating task per account.

Implemented model:

```text
worker active_live_account_ids
  -> crud.claim_next_pending_task(excluded_live_account_ids)
  -> scan first 500 ready PENDING tasks
  -> skip same-account live mutating tasks
  -> allow dry-run/read-only tasks
  -> preflight auth + live arm + exact fb_uid + extension guard
  -> reserve date-scoped quota
  -> mark account active while async live processing runs
  -> clear active account in finally path
```

Known limit: `_active_live_account_ids` is process-local. Multi-process workers require a DB lease/lock before Phase 4 distributed operation.

## Related Code Files

Modified:

- `agent/worker/processor.py`
- `agent/db/crud.py`
- `agent/api/accounts.py`
- `tests/unit/test_account_queue_quota.py`
- related Safety Gate/live arming tests as needed for regression coverage

## Implementation Steps

1. Add tests for per-account task selection and no duplicate claim. **Done.**
2. Add tests for per-account quota windows and retry idempotency. **Done.**
3. Extend account/task status summaries with queue depth and quota state. **Done via account queue summary.**
4. Enforce one live mutating task per account at a time. **Done within one worker process.**
5. Keep dry-run tasks safe and cheap. **Done; dry-run is exempt from live quota reservation and same-account live exclusion.**
6. Add dashboard/API visibility only after backend state is stable. **API done; dashboard follow-up remains optional.**

## Todo List

- [x] Define account-level quota model.
- [x] Define account-level concurrency policy.
- [x] Add focused worker/CRUD tests.
- [x] Implement minimal queue selection changes.
- [x] Expose account queue/quota summary.
- [x] Update docs.

## Success Criteria

- 50 accounts can have queued work without uncontrolled same-account live dispatch in the single-worker SQLite MVP.
- Worker does not duplicate live quota reservation on same-day retries.
- `GET /api/accounts/{account_id}/queue-summary` reveals queue counts, quota usage, stale-counter-aware values, and blocked reasons.
- Validation reported: `232 passed`, Python `compileall` passed, and `node --check extension\background.js` passed.

## Risk Assessment

- Risk: scheduler complexity grows fast. Mitigate with simple account-level fairness first.
- Risk: SQLite lock contention. Mitigate by measuring before replacing the queue backend.
- Risk: process-local live exclusion does not protect multi-process workers. Mitigate in Phase 4 with a DB lease/lock before distributed worker use.

## Security Considerations

- Quota and queue state are safety controls, not just performance controls.
- Live tasks must keep exact `fb_uid` routing and active arm checks from Phase 01.
- Live quota reservation must keep API/WS auth, active arm, exact account `fb_uid`, and extension guard preflight before counter increment.

## Next Steps

After this phase, pilot multiple isolated profiles with only 5-10 accounts. Do not move to multi-process workers until same-account live exclusion has a database-backed lease/lock.
