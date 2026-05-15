# FBKit Project Roadmap

Last updated: 2026-05-08

## Current Status

FBKit has a working local-first architecture: FastAPI agent, SQLite task queue, Safety Gate, worker/scheduler, Chrome extension bridge, and React dashboard. Phases 1-4 are implemented in code as minimal readiness: live actions require scoped live arming plus API/WS auth, server approval, exact account routing, quota readiness, extension guard readiness, stale-aware multi-profile session handling, and a DB-backed live account lease for same-account live exclusion across workers sharing one SQLite DB.

## Milestones

| Milestone | Status | Evidence |
|---|---|---|
| Local agent runtime | Complete | `agent/main.py`, `/health`, `/api/status` |
| Safety Gate v1 | Complete | `agent/services/safety_gate.py`, `tests/unit/test_safety_gate.py` |
| Safety Control Plane Phase 1 | Complete | `live_arm` table/model, `/api/tasks/live-arm`, `/api/status` safety state, `tests/unit/test_live_arming.py` |
| Account-Scoped Queue And Quota Phase 2 | Complete | `claim_next_pending_task(excluded_live_account_ids=...)`, worker `_active_live_account_ids`, `/api/accounts/{account_id}/queue-summary`, `tests/unit/test_account_queue_quota.py` |
| Multi-Profile Local Pilot Phase 3 | Complete | profile identity/guard metadata, stale heartbeat health, fresh duplicate `fb_uid` routing, stale-only worker gate, stale-aware dashboard types; `246 passed` unit suite and targeted `13 passed` regression |
| Distributed Worker Readiness Phase 4 | Complete | SQLite `live_account_lease`, worker `node_id`, live lease claim/release/reclaim, `/api/status` worker lease metadata; `260 passed` unit suite, compile/build checks passed |
| Docs, Validation, And Rollout Gates Phase 5 | Complete/active | `docs/rollout-gates.md`, README/roadmap links, static rollout-doc regression tests |
| Chrome extension bridge | Complete | `agent/services/fb_client.py`, `extension/` |
| Task worker and scheduler | Complete | `agent/worker/processor.py`, `agent/services/scheduler.py` |
| Dashboard UI | In progress | `dashboard/src/App.tsx`, dashboard pages for status/accounts/tasks/seeding/spy/logs |
| Docker local runtime | Available | `Dockerfile`, `docker-compose.yaml` |
| Controlled live-action readiness | Guarded, not ready by default | Live requires `LIVE_ACTIONS_ENABLED`, API/WS auth, active live arm, approval, exact `fb_uid`, quota readiness, extension live guard enabled, and DB-backed same-account live lease |

## Near-Term Priorities

1. Keep dry-run smoke validation reliable for `POST_TEXT`, `LIKE_POST`, `COMMENT_POST`, and `SEND_MESSAGE`.
2. Maintain tests around Safety Gate, live arming, exact `fb_uid` routing, quota reservation, approvals, and extension dry-run guard.
3. Keep Phase 5 active for rollout gates, docs sync, and validation discipline.
4. Follow [rollout-gates.md](./rollout-gates.md) before any multi-profile, distributed-readiness, or controlled-live claim.
5. Run optional operator manual 5-10 profile pilot using Phase 3/4 implementation if local resource/load evidence is still needed.
6. Improve dashboard coverage only where it reflects verified API behavior, especially `/api/status` safety/lease state and `/api/accounts/{account_id}/queue-summary`.
7. Keep docs synced with code after changes to endpoints, config, runtime behavior, or safety rules.

## Near-Term Marketing Milestones (Lean Product-Led)

| Milestone | Target window | Status | Notes |
|---|---|---|---|
| Publish core messaging baseline | Immediate | In progress | Use tagline + local-first safety positioning across docs and product surfaces |
| Ship compact marketing overview doc | Immediate | Complete | `docs/marketing-overview.md` |
| Prepare product-led demo flow | Near-term | In progress | Reuse dry-run safe flow as primary demo path |
| Build lead capture entry point | Near-term | Planned | Public website is not live yet; use interim direct-contact/demo-request path |
| Define first outbound competitor narrative | Near-term | Planned | Keep comparison tight vs Phantombuster/TexAu/Jarvee-like tools |
| Publish initial pricing stance | Later near-term | Planned | Keep as TBD until packaging is validated through early demos |

## Safety Guardrails

- Do not enable live Facebook mutations as a default workflow.
- Do not approve tasks during dry-run smoke checks.
- Do not test live actions on a main account.
- Document every confirmed change to Safety Gate behavior in [Codebase Summary](./codebase-summary.md).
- Maintain the Phase 4 SQLite live account lease before relying on multiple workers sharing one DB; process-local `_active_live_account_ids` is only telemetry/defense-in-depth.
- Treat stale extension sessions as offline for routing/readiness; do not count stale sockets as live-ready in status UI.
- Keep `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` shorter than `LIVE_ACCOUNT_LEASE_TTL_SECONDS` for long live workflows; the worker clamps the effective interval to at most half of TTL.
- Keep `/api/status` local or enable API auth before non-local exposure because it includes operational IDs/session metadata.

## Phase 4 Completion Evidence

- DB-backed live account leases are implemented for live mutating non-dry-run tasks; dry-run/read-only tasks remain lease-exempt.
- Worker exposes read-only `node_id`, `active_live_account_ids`, and `live_account_leases` under `/api/status`.
- New config: `FBKIT_NODE_ID` optional, default `hostname:pid`; `LIVE_ACCOUNT_LEASE_TTL_SECONDS` default `900`, clamped `60`-`3600`; `LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS` default `60`, clamped `5`-`300`.
- Safety defaults unchanged: no live actions enabled by default; Safety Gate, live arm, API/WS auth, exact `fb_uid`, extension guard, and quota checks remain intact.
- Verification: `pytest tests\unit\test_account_queue_quota.py -q` passed with `22 passed in 4.80s`; targeted safety/live/quota suite passed with `95 passed in 15.93s`; final full unit suite passed with `260 passed in 21.20s`; `python -m compileall agent`, `node --check extension\background.js`, and dashboard `npm run build` passed.
- Final code review approved docs sync with no blockers.

## Documentation Backlog

| Item | Priority | Notes |
|---|---|---|
| Deployment guide | Medium | Current Docker support is verified, but no dedicated `docs/deployment-guide.md` exists. |
| API reference | Medium | Route inventory is summarized in `codebase-summary.md`; detailed request/response docs would need generated or verified examples. |
| Dashboard guide | Low | Add only after UI workflows stabilize. |

## Rollout Gates

Use [rollout-gates.md](./rollout-gates.md) as the source of truth for progression claims. The current verified gates cover local dry-run, one dedicated test account, 2/5/10 profile dry-run pilots, distributed readiness review, and an explicitly approved controlled-live test gate. No 50-account support, distributed deployment, or broad live Facebook automation safety is validated.
