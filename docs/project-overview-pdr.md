# FBKit Project Overview and PDR

Last updated: 2026-05-08

## Overview

FBKit is a local-first Facebook automation assistant. The current implementation uses a Python FastAPI agent, SQLite task queue, Chrome extension WebSocket bridge, and React/Vite dashboard.

Primary product constraint: FBKit is dry-run first. Real Facebook mutations must remain disabled unless explicitly approved for a controlled live test with a safe target.

## Current Product Scope

| Area | In scope now | Verified implementation |
|---|---|---|
| Account management | Store local Facebook account metadata and `fb_uid` mapping | `agent/api/accounts.py`, `agent/db/schema.py` |
| Task queue | Queue and process Facebook automation tasks | `agent/api/tasks.py`, `agent/worker/processor.py` |
| Posting | Text, link, image, video, story, reel, reup-video task paths | `agent/api/posts.py`, `agent/worker/processor.py` |
| Messaging | Single and bulk message tasks | `agent/api/messages.py`, `agent/worker/processor.py` |
| Engagement | Like, comment, share, friend, group, page actions | `agent/services/safety_gate.py`, `agent/worker/processor.py` |
| Scheduling | Scheduled posts/messages become queued tasks | `agent/services/scheduler.py` |
| Browser bridge | Route commands to connected Chrome extension sessions by `fb_uid` | `agent/services/fb_client.py`, `extension/` |
| Dashboard | Local UI for status, accounts, tasks, seeding, spy ads, logs | `dashboard/src/App.tsx` |

## Marketing Context

| Item | Current direction |
|---|---|
| Product name | FBKit |
| Tagline | local-first Facebook automation assistant |
| Category | Facebook automation software |
| Main offer | Local automation platform with safety-gated execution |
| Objective | Lead generation |
| Primary audience | Agencies and marketers |
| Buyer profile | Small agencies and SMB teams |
| Decision-maker | Founder or agency owner |
| Geographic focus | Global, remote-first |
| Positioning | Safer local-first alternative to cloud social automation tools |
| Public website | Not published yet |
| Pricing | TBD / not public yet |
| Brand assets | Basic assets only; style follows existing app UI |

## Functional Requirements

1. The agent must expose local REST APIs on `API_HOST`/`API_PORT`, default `127.0.0.1:8100`.
2. The extension bridge must listen on `WS_HOST`/`WS_PORT`, default `127.0.0.1:9222`.
3. Mutating task payloads must pass Safety Gate enforcement at task creation and again before dispatch.
4. External task creation must strip client-supplied server-owned approval and quota fields.
5. Live mutating tasks must require exact account routing through resolved `account.fb_uid`.
6. Dry-run tasks must not reserve live-action quota.
7. Scheduled posts/messages must be claimed before task creation to avoid duplicate enqueue.
8. The dashboard must read current API status and subscribe to live event updates through `/ws/dashboard`.

## Non-Functional Requirements

| Requirement | Current expectation |
|---|---|
| Safety | Defaults: `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true` |
| Local-first | SQLite database and local browser extension bridge; no hosted service required |
| Auditability | Activity logs, task traces, task results, strategy outcome counters |
| Recoverability | Worker retry logic with retryable/non-retryable classification |
| Minimal auth | API-key auth is optional and disabled by default for safe local mode |
| Windows support | README and scripts use quoted PowerShell paths for `.venv` |

## Acceptance Criteria

- `GET /health` returns `{"status":"ok"}` when the agent is running.
- `GET /api/status` reports Safety Gate settings, task stats, runtime components, and extension session details.
- Dry-run smoke tasks complete with `dryRun=true` and do not call approval endpoints.
- Mutating tasks remain dry-run when live actions are disabled or approval is missing.
- Extension mutating handlers do not perform DOM actions when dry-run or extension live actions are disabled.

## Out of Scope / Removed

- The old video-generation pipeline is removed from the active product.
- Live Facebook automation on a main/personal account is not a safe validation target.

## Related Docs

- [Codebase Summary](./codebase-summary.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
- [Common Issues](./common-issues.md)
