---
title: "Safety-first 50-account roadmap"
description: "Plan to evolve FBKit from local dry-run MVP toward controlled multi-account operation without weakening safety defaults."
status: completed
priority: P1
effort: multi-phase
branch: unknown
tags: [fbkit, safety, architecture, multi-account, planning]
created: 2026-05-07
---

# Safety-First 50-Account Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development before implementing. This plan is architecture-first. Do not enable live Facebook actions without explicit user approval and a dedicated safe target.

## Overview

FBKit can evolve toward managing 50 Facebook accounts, but not by jumping straight from the current local MVP to 50 simultaneous live browser sessions. The safe path is staged: first make live execution explicitly armed and observable, then add account-scoped queues and quotas, then pilot multi-profile operation, and only then consider distributed workers.

Core product stance: FBKit remains dry-run first. Live action is a controlled, scoped, expiring exception.

## Phase Status

| Phase | File | Status | Purpose |
|---|---|---|---|
| 1 | [Safety control plane](./phase-01-safety-control-plane.md) | Complete | Added explicit live arming and fail-closed policy invariants. |
| 2 | [Account-scoped queue and quota](./phase-02-account-scoped-queue-and-quota.md) | Complete | Added account-scoped live claim exclusion, date-scoped quota idempotency, exact `fb_uid` quota preflight, and account queue summary API. |
| 3 | [Multi-profile local pilot](./phase-03-multi-profile-local-pilot.md) | Complete | Implemented stale-aware multi-profile session routing/readiness. Manual 5-10 profile operator pilot remains optional activity. |
| 4 | [Distributed worker readiness](./phase-04-distributed-worker-readiness.md) | Complete | Added minimal DB-backed live account lease/status readiness. No orchestration/control plane. |
| 5 | [Docs, validation, and rollout gates](./phase-05-docs-validation-and-rollout-gates.md) | Complete/active | Added rollout gates and keeps safety docs/tests/operator workflows aligned. |

## Key Dependencies

| Dependency | Why it matters |
|---|---|
| Current Safety Gate | Remains the central server-side mutating task policy. |
| Extension DOM guard | Must stay independent from server policy for defense-in-depth. |
| Exact `fb_uid` routing | Required for all live mutating tasks. No live fallback session. |
| SQLite task queue | Acceptable for local staged rollout; revisit only after concurrency evidence. |
| Dashboard status UX | Required for operators to see dry-run, armed, disconnected, and unsafe states. |

## Non-Goals

- Do not implement a SaaS platform in this plan.
- Do not support live automation on the user's main Facebook account as a first target.
- Do not run 50 live browser sessions on one machine as the initial scale target.
- Do not weaken dry-run defaults.
- Do not approve, dispatch, or test live Facebook actions as part of planning.

## Success Criteria

- Live mode cannot run unless explicitly armed for account, task type, and time window.
- API and WebSocket auth become mandatory when live actions are enabled.
- `/api/status` exposes complete safety state, including extension guard state per connected session.
- Unknown or uncategorized mutating paths fail closed.
- Account-level queues and quotas can throttle 50 accounts over time without requiring 50 simultaneous sessions.
- Rollout gates define when 5-10 profile pilots, distributed readiness review, and controlled live tests may be claimed; no 50-account rollout is validated by this plan.

## Recommended Execution Order

1. Complete Phase 1 before any scale work.
2. Phase 2 is complete; use its queue/quota controls before multi-profile/browser orchestration.
3. Phase 3 implementation is complete; run a manual 5-10 account/profile pilot if real resource evidence is needed.
4. Phase 4 minimal readiness is complete; do not treat it as distributed orchestration or live deployment proof.
5. Keep Phase 5 active across rollout, docs, and validation work.

## Risk Summary

| Risk | Severity | Mitigation |
|---|---|---|
| Facebook ToS/account enforcement | High | Dedicated test/business assets, low rates, dry-run default, no main-account live tests. |
| Safety bypass by new task type | High | Fail-closed unknowns, invariant tests, extension guard parity checks. |
| Wrong-account live mutation | High | Exact `fb_uid` required for live, no fallback for live mutating tasks. |
| Local API misuse | High when live enabled | Require API/WS auth when live enabled or armed. |
| 50-session resource overload | High | Pilot 5-10 profiles; distributed workers only after evidence. |

## Implementation Handoff

Use this plan as the source of truth. Implement one phase at a time with TDD for behavior changes. After each phase, update `docs/codebase-summary.md`, `docs/system-architecture.md`, and `docs/project-roadmap.md` when runtime behavior changes.

## Phase 1 Completion Evidence

- `live_arm` SQLite state and `/api/tasks/live-arm` create/revoke endpoints exist.
- Live approval and worker dispatch require API/WS auth, scoped active live arm, server-owned approval marker, exact account routing, quota readiness, and extension live guard readiness.
- `/api/status` reports API/WS auth readiness, active live arms, and extension guard state through extension sessions.
- Reported validation: `223 passed` unit suite, Python `compileall` passed, and `node --check extension\background.js` passed.

## Phase 2 Completion Evidence

- `crud.claim_next_pending_task(excluded_live_account_ids=...)` scans up to 500 ready pending tasks and skips live mutating tasks for accounts already active in the worker process.
- Worker tracks process-local `_active_live_account_ids` around async processing, enforcing one active live mutating task per account in the single-worker process; dry-run tasks are exempt.
- `_check_rate_limit()` records specific preflight/quota errors and validates API/WS auth, active live arm, exact account `fb_uid`, and extension guard before live quota reservation.
- `_quotaReserved` now includes `date`; retry idempotency is scoped to today's counter reservation.
- `crud.get_account_queue_summary(account_id)` and `GET /api/accounts/{account_id}/queue-summary` expose queue counts, quota usage, stale-counter-aware used values, and blocked reasons.
- Reported validation: `232 passed` unit suite, Python `compileall` passed, and `node --check extension\background.js` passed.
- Code review found no blockers. Historical low concern about process-local same-account live guard was resolved by Phase 4 DB-backed live account lease.

## Phase 3 Completion Evidence

- Extension reports stable profile identity metadata (`profileId`, `profileName`), login state, `fb_uid`, heartbeat, and extension live guard state.
- Inbound real extension `ping` refreshes session heartbeat only with current identity; identity-less keepalives do not refresh old UID-bound sessions, and `/api/status` exposes `last_seen_age_s`, `stale`, and `health`.
- `FBClient` exact `fb_uid` routing prefers the freshest duplicate session and rejects stale-only exact matches.
- Worker waits for at least one fresh extension session before claiming queued tasks, so stale-only sockets do not fail queued work.
- Account extension status treats stale sessions as offline/stale and chooses least-stale duplicate metadata for visibility.
- Dashboard session types and `SafetyGateStatus` count/connectivity are stale-aware.
- Extension dispatch rechecks the current Facebook `c_user` against server-sent `expectedFbUid` before content-script dispatch, preventing same-profile account switches from reusing an old exact route.
- Extension live actions remain disabled by default.
- Reported validation: `pytest tests\unit -q` passed with `246 passed in 17.91s`; `compileall agent` passed; `node --check extension\background.js` passed; dashboard `npm run build` passed.
- Follow-up targeted regression: `pytest tests\unit\test_multi_profile_sessions.py tests\unit\test_dashboard_session_types.py -q` passed with `13 passed in 0.85s`.
- Code review risk areas satisfied. Historical low concern about process-local `_active_live_account_ids` was resolved by Phase 4 DB-backed live account lease; the process-local set remains telemetry/defense-in-depth.

## Phase 4 Completion Evidence

- Implemented SQLite-backed `live_account_lease` guard for live mutating non-dry-run tasks across worker processes sharing one DB.
- Dry-run/read-only tasks remain lease-exempt.
- Worker keeps process-local `_active_live_account_ids` as telemetry/defense-in-depth; DB lease is now the cross-worker guard.
- `/api/status` worker block exposes read-only `node_id`, `active_live_account_ids`, and `live_account_leases`.
- New config: `FBKIT_NODE_ID` optional, default `hostname:pid`; must be unique per worker process when multiple workers share one DB. `LIVE_ACCOUNT_LEASE_TTL_SECONDS` default `900`, clamped `60`-`3600`; `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` default `60`, clamped `5`-`300`.
- No live actions enabled by default. Safety Gate, live arm, API auth, WS auth, exact `fb_uid`, extension guard, and quota checks remain intact.
- Verification: `pytest tests\unit\test_account_queue_quota.py -q` -> `22 passed in 4.80s`; `pytest tests\unit\test_safety_gate.py tests\unit\test_live_arming.py tests\unit\test_account_queue_quota.py -q` -> `95 passed in 15.93s`; final `pytest tests\unit -q` -> `260 passed in 21.20s`; `python -m compileall agent` passed; `node --check extension\background.js` passed; dashboard `npm run build` passed.
- Final code review approved docs sync, no blockers.
- Live account leases are refreshed during task processing by matching account/task/node before expiry; the worker clamps the effective heartbeat interval to at most half of TTL. Residual risks: `/api/status` exposes operational IDs/session metadata; keep API local or enable API auth before non-local exposure. Future hardening: multi-process SQLite contention integration test.

## Phase 5 Completion Evidence

- Added `docs/rollout-gates.md` as the source of truth for local dry-run, one-account, 2/5/10 profile dry-run pilots, distributed readiness review, and optional controlled-live progression gates.
- README and `docs/project-roadmap.md` link rollout gates.
- Rollout gate docs explicitly disallow claims that 50-account support, distributed deployment, broad live Facebook automation, or main-account live automation are validated.
- Static regression tests verify rollout gate content and links.

## Unresolved Questions

- Is the 50-account target for scheduled/rate-limited operation, or true simultaneous live action?
- Should live mode be permanently restricted to dedicated test/business assets?
- What is the maximum acceptable local machine resource budget for the multi-profile pilot?
- What live task duration and heartbeat interval should be used for controlled live pilots?
