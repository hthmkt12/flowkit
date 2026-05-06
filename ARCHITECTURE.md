# FBKit Architecture

FBKit is the active system in this repository. It is a local-first Facebook automation assistant using a Python FastAPI agent, a SQLite task queue, and a Chrome extension WebSocket bridge connected to a logged-in browser session.

The old video-generation pipeline has been removed.

## Safety-First Architecture

- server Safety Gate enforces dry-run defaults before task creation
- worker re-enforces Safety Gate immediately before dispatch
- live mutating tasks require server-owned approval
- `FBClient` routes exact account targets by `fb_uid`
- the Chrome extension keeps an independent DOM-action guard
- live Facebook actions stay disabled unless the user explicitly requests a controlled live test with a safe target and verified Safety Gate behavior

## Data Flow

```text
Local/API caller
  -> FastAPI endpoint
  -> Safety Gate enforcement
  -> SQLite task queue
  -> worker final Safety Gate enforcement
  -> exact fb_uid routing through FBClient
  -> WebSocket bridge
  -> Chrome extension DOM-action guard
  -> logged-in Facebook browser session
```

## Runtime Components

| Component | Path | Responsibility |
|---|---|---|
| FastAPI app | `agent/main.py` | REST API, WebSocket server, worker/scheduler lifecycle |
| API routers | `agent/api/` | Accounts, tasks, posts, messages, groups, seeding, spy ads, strategies |
| SQLite schema/CRUD | `agent/db/` | Local account/task/post/message/group state |
| Safety Gate | `agent/services/safety_gate.py` | Dry-run enforcement and approval boundaries |
| Facebook client | `agent/services/fb_client.py` | Routes worker commands to exact extension sessions |
| Worker | `agent/worker/processor.py` | Claims queued tasks, re-checks safety, dispatches actions |
| Scheduler | `agent/services/scheduler.py` | Enqueues scheduled posts/messages |
| Chrome extension | `extension/` | Connects to agent and performs guarded Facebook DOM actions |

## Current Endpoints

- `GET /health` — basic process check, expected `{"status":"ok"}`.
- `GET /api/status` — active FBKit readiness check for runtime, worker, scheduler, task, notifier, session, and extension details.
- `POST /api/tasks` and related APIs — create queued work that must pass Safety Gate enforcement.

For verified Safety Gate behavior, see `docs/codebase-summary.md`.
