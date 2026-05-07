# Phase 01: Safety Control Plane

## Context Links

- [Plan overview](./plan.md)
- `docs/codebase-summary.md`
- `docs/system-architecture.md`
- `agent/services/safety_gate.py`
- `agent/worker/processor.py`
- `agent/services/fb_client.py`
- `extension/content-fb.js`

## Overview

Priority: P1  
Status: Complete

Add an explicit live-action arming model. Live execution should be impossible unless the operator arms a scoped, expiring live window for a specific account and task type. This is the required foundation before any 50-account work.

## Key Insights

- Env flags are not enough as a product safety model.
- Extension guard must remain independent from server policy.
- The operator needs one place to see whether the system is dry-run, blocked, or armed.

## Requirements

Functional:

- Add live arm state with account scope, task-type scope, expiry, and audit metadata. Implemented in `live_arm`.
- Require live arm before approval/live dispatch for mutating tasks. Implemented through approval and worker checks.
- Require exact `fb_uid` for every live mutating task. Implemented before dispatch.
- Require API and WebSocket auth when live mode is armed or approved. Implemented for arm creation, approval, quota readiness, and dispatch.
- Report server safety state and extension guard state in `/api/status`. Implemented under `safety_gate` and `extension.sessions[]`.
- Fail closed for unknown task types that can reach mutating dispatch.

Non-functional:

- Preserve dry-run defaults.
- Keep implementation small and testable.
- Avoid broad auth/RBAC work unless required by live safety.

## Architecture

Server policy flow:

```text
task creation -> Safety Gate -> persisted task
approval request -> auth -> live config check -> live arm check -> server approval marker
worker claim -> Safety Gate re-check -> live arm still valid -> quota -> exact fb_uid -> FBClient
extension command -> extension live guard -> DOM action or dry-run result
```

The live arm can initially be stored in SQLite. A single local operator is assumed. Multi-user RBAC is out of scope.

## Related Code Files

Likely modify:

- `agent/services/safety_gate.py`
- `agent/config.py`
- `agent/api/tasks.py`
- `agent/main.py`
- `agent/services/fb_client.py`
- `agent/worker/processor.py`
- `agent/db/schema.py`
- `agent/db/crud.py`
- `extension/content-fb.js`
- `tests/unit/test_safety_gate.py`
- `tests/unit/test_extension_dry_run.py`

Likely create only if needed:

- `tests/unit/test_live_arming.py`

## Implementation Steps

1. Add tests that live approval fails without an active matching arm.
2. Add tests that live mode refuses to start or arm when API/WS auth is disabled.
3. Add a minimal live arm persistence model.
4. Add explicit arming and disarming endpoints, protected by API auth.
5. Gate approval/live dispatch on active arm scope and expiry.
6. Extend extension status handshake to report extension live guard state.
7. Extend `/api/status` with safety state summary.
8. Add fail-closed tests for unknown mutating task paths.

## Todo List

- [x] Define live arm contract.
- [x] Add failing tests for live approval without arm.
- [x] Implement minimal arm storage and policy checks.
- [x] Report extension guard state.
- [x] Update status endpoint.
- [x] Update docs after verified behavior.

## Success Criteria

- A live mutating task cannot be approved or dispatched unless live config, auth, arm scope, approval, exact `fb_uid`, and extension guard checks align.
- Dry-run smoke behavior remains unchanged.
- Focused Safety Gate and extension dry-run tests pass.

## Completion Evidence

- `agent/db/schema.py` defines `live_arm` with account, task type JSON, expiry, created metadata, and revocation state.
- `agent/db/crud.py` enforces API/WS auth, mutating task types only, and TTL `<= 900` seconds for live arms.
- `agent/api/tasks.py` strips client `_liveArmId`, requires active matching live arm for approval, and stores server-owned `_liveArmId`.
- `agent/worker/processor.py` rechecks API/WS auth, active `_liveArmId`, account scope, exact `fb_uid`, extension guard, and quota readiness before live dispatch.
- `extension/background.js` sends `extensionLiveActionsEnabled`; `agent/services/fb_client.py` exposes session guard state.
- Reported validation: `223 passed` unit suite, Python `compileall` passed, and `node --check extension\background.js` passed.

## Risk Assessment

- Risk: added state creates confusing UX. Mitigate with explicit `/api/status` messages.
- Risk: arming endpoint becomes a bypass. Mitigate with auth requirement and audit log.

## Security Considerations

- Live arming is a safety-critical control path.
- Never accept client-supplied `_serverApproved` or arm markers inside task payloads.
- Expired arms must fail closed at worker dispatch, not only approval time.

## Next Steps

Proceed to Phase 2 account-scoped queue/quota work without weakening Phase 1 live-arm invariants.
