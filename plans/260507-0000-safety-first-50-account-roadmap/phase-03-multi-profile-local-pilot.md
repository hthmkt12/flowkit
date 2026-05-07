# Phase 03: Multi-Profile Local Pilot

## Context Links

- [Plan overview](./plan.md)
- [Phase 01](./phase-01-safety-control-plane.md)
- [Phase 02](./phase-02-account-scoped-queue-and-quota.md)
- `agent/services/fb_client.py`
- `extension/`
- `dashboard/`

## Overview

Priority: P2  
Status: Complete

Implementation validation is complete for stale-aware multi-profile local operation. Manual 5-10 isolated Chrome profile pilot remains an operator activity if real local resource/load evidence is needed before 50-account ambition.

## Key Insights

- 50 profiles on one machine is not a safe first target.
- Browser-profile isolation reduces wrong-account and session bleed risks.
- The first pilot should be dry-run-only unless the user separately approves a controlled live test.
- Stale-only sockets must not make the worker claim queued tasks or make dashboard status look connected.
- Duplicate sessions for the same `fb_uid` must prefer the freshest session and reject stale-only exact matches.

## Requirements

Functional:

- Register multiple extension sessions with stable profile/account identity. Done.
- Show connected/disconnected/stale status per `fb_uid`. Done in status metadata, account extension status, and dashboard types.
- Support dry-run dispatch across multiple profiles through exact fresh `fb_uid` routing. Implementation validated by unit/regression tests.
- Add profile health and reconnect signals through heartbeat freshness. Done.
- Provide a manual runbook for loading profiles safely. Still useful if operator runs a real 5-10 profile pilot.

Non-functional:

- Do not automate Chrome profile creation until manual pilot proves value.
- Avoid headless/browser farm complexity in this phase.
- Do not claim actual 5-10 manual profile pilot results unless the operator runs it.

## Architecture

Pilot topology:

```text
one local agent
  -> multiple Chrome profiles
  -> one extension instance per profile
  -> each session reports fb_uid + profile identity + guard state + heartbeat
  -> FBClient routes by exact fresh fb_uid and ignores stale-only matches
  -> worker waits for at least one fresh extension session before task claim
```

## Related Code Files

Modified/validated:

- `agent/services/fb_client.py`
- `agent/main.py`
- `extension/background.js`
- `extension/content-fb.js`
- `dashboard/src/pages/DashboardPage.tsx`
- `dashboard/src/pages/AccountsPage.tsx`
- tests covering FBClient session routing and stale session state

## Implementation Steps

1. Added tests for multiple connected sessions and exact routing.
2. Added heartbeat/stale detection behavior for extension sessions.
3. Surfaced per-session extension guard state and profile/account identity.
4. Added dashboard type/status awareness for stale session health.
5. Added worker fresh-session gate before task claim.
6. Manual dry-run pilot with 2, then 5, then 10 profiles was not claimed/run in this implementation task.
7. Resource usage and manual failure modes remain operator pilot outputs if needed.

## Todo List

- [x] Define implementation acceptance criteria.
- [x] Add multi-session routing tests.
- [x] Add stale session/heartbeat status.
- [x] Expose session safety state in dashboard types/status.
- [x] Keep extension live actions disabled by default.
- [ ] Write manual multi-profile runbook if operator pilot is scheduled.
- [ ] Record manual pilot results before scaling to distributed/50-account operation.

## Success Criteria

- Implementation supports fresh exact `fb_uid` routing and stale duplicate rejection. Validated by tests.
- Dashboard types/status are stale-aware and do not count stale sessions as connected/logged in. Validated by tests/build.
- Worker does not claim tasks when only stale extension sockets exist. Validated by tests.
- No live action is needed or enabled by default to validate routing and queue behavior.
- Manual 5-10 profile dry-run pilot results are not yet recorded here.

## Risk Assessment

- Risk: local machine resource exhaustion. Mitigate with staged profile count.
- Risk: stale session used for dispatch. Mitigate with heartbeat expiry and exact routing failure.
- Risk: Facebook detects abnormal behavior. Mitigate with dry-run-first and low frequency.
- Residual low risk: `_active_live_account_ids` remains process-local. Mitigate with DB lease/lock before multi-process/distributed workers.

## Security Considerations

- Never fallback to any connected session for live mutation.
- Treat disconnected/unknown guard state as unsafe.
- Treat stale sessions as offline for dispatch/readiness even if metadata remains visible.

## Completion Evidence

- `pytest tests\unit -q`: `246 passed in 17.91s`.
- `compileall agent`: passed.
- `node --check extension\background.js`: passed.
- Dashboard `npm run build`: passed.
- Follow-up targeted regression: `pytest tests\unit\test_multi_profile_sessions.py tests\unit\test_dashboard_session_types.py -q`: `13 passed in 0.85s`.
- Code review: requested Phase 3 risk areas satisfied; stale-readiness follow-up fixed.

## Next Steps

If an operator-run 5-10 profile dry-run pilot is stable, decide whether 50 accounts need distributed workers or only scheduled low-concurrency operation. Before multi-process/distributed workers, design DB-backed lease/lock for account live exclusion.
