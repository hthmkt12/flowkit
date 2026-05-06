# FBKit

FBKit is a local-first Facebook automation assistant. It uses a Python FastAPI agent, a SQLite task queue, and a Chrome extension WebSocket bridge to run Facebook tasks through a logged-in browser session.

> **Safety default:** FBKit is dry-run first. Real mutating Facebook actions are disabled by default at both the server Safety Gate and the Chrome extension DOM-action layer.

For verified Safety Gate entry points and current runtime behavior, see `docs/codebase-summary.md`.

## Quick Start

### 1. Start the agent in safe local mode

PowerShell:

```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
.\.venv\Scripts\python.exe -m agent.main
```

Or use the safe Windows helper at `scripts/start-fbkit-safe.ps1`:

```powershell
.\scripts\start-fbkit-safe.ps1
```

Preview the safe environment and command without starting the agent:

```powershell
.\scripts\start-fbkit-safe.ps1 -PrintOnly
```

Bash/Git Bash/WSL:

```bash
LIVE_ACTIONS_ENABLED=false \
DRY_RUN_DEFAULT=true \
APPROVAL_REQUIRED=true \
API_AUTH_ENABLED=false \
WS_AUTH_ENABLED=false \
python -m agent.main
```

The agent listens on:

- REST API: `http://127.0.0.1:8100`
- Extension WebSocket: `ws://127.0.0.1:9222`

### 2. Load and connect the Chrome extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select `extension/`.
4. Open `https://www.facebook.com/` and sign in.
5. Verify the extension session:

```powershell
curl.exe http://127.0.0.1:8100/api/status
```

Look for a logged-in session with a non-empty `fb_uid`:

```json
{
  "extension": {
    "connected": true,
    "sessions": [{"fb_uid": "...", "logged_in": true}]
  }
}
```

### 3. Run the safe dry-run smoke test

```powershell
.\.venv\Scripts\python.exe scripts\fbkit-dry-run-smoke.py
```

The smoke script:

- checks `/api/status`
- finds the logged-in extension `fb_uid`
- finds or creates a matching local account
- submits exactly one task with `dryRun=true`
- defaults to `POST_TEXT`, with optional safe variants: `LIKE_POST`, `COMMENT_POST`, `SEND_MESSAGE`
- passes only if the task completes with `dryRun=true`
- does **not** approve tasks and does **not** request live dispatch

Run a specific dry-run variant:

```powershell
.\.venv\Scripts\python.exe scripts\fbkit-dry-run-smoke.py --variant LIKE_POST --content "https://www.facebook.com/example/posts/123"
```

Validated dry-run variants:

- `POST_TEXT`
- `LIKE_POST`
- `COMMENT_POST`
- `SEND_MESSAGE`

Clean up smoke helper processes when you are done:

```powershell
.\scripts\stop-fbkit-smoke.ps1
```

The cleanup helper stops identifiable FBKit agent listeners on ports `8100` and `9222`, removes stale agent smoke PID files, and keeps Chrome open by default. Pass `-IncludeChrome` only if you started a dedicated smoke Chrome profile and want to close it too.

## Safety Gate Defaults

FBKit centralizes mutation safety in `agent/services/safety_gate.py`.

| Env var | Safe default | Purpose |
|---|---:|---|
| `LIVE_ACTIONS_ENABLED` | `false` | Global switch for live Facebook mutations |
| `DRY_RUN_DEFAULT` | `true` | Default to dry-run when no explicit payload flag is provided |
| `APPROVAL_REQUIRED` | `true` | Require server-owned `_serverApproved=true` before live mutation |

Mutating task types include posting, messaging, liking, commenting, sharing, friend actions, group actions, page follow/unfollow, and video reup tasks.

Additional protections:

- external `/api/tasks` creation strips client-supplied approval/quota markers
- worker re-enforces Safety Gate immediately before extension dispatch
- live quota is reserved before live dispatch and skipped for dry-run tasks
- `FBClient` requires exact `fb_uid` routing when a task targets a specific Facebook account
- live mutating worker tasks fail closed if the account has no resolved `fb_uid`
- extension mutating handlers return before navigation/click/type/file-upload when `dryRun=true` or when `EXTENSION_LIVE_ACTIONS_ENABLED=false`
- extension-local live-action guard forces dry-run with `safetyReason: "extension_live_actions_disabled"`, independent of server payload approval

## Live Action Warning

Do **not** enable live Facebook actions on your main account as a first test.

Before any live test:

1. Create a dedicated test Facebook account/page/group.
2. Keep `LIVE_ACTIONS_ENABLED=false` until dry-run smoke tests pass.
3. Start with one low-risk post task.
4. Approve it through the server approval endpoint only after reviewing the payload.
5. Confirm the extension-side `EXTENSION_LIVE_ACTIONS_ENABLED` guard has been intentionally changed for a controlled test; otherwise the extension still forces dry-run.
6. Do not live-test inbox/comment/engagement automation until the posting flow is proven safe.

## Current Docs

- `ARCHITECTURE.md` — current FBKit architecture.
- `docs/codebase-summary.md` — verified Safety Gate behavior and runtime entry points.
- `docs/common-issues.md` — FBKit troubleshooting notes.
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` — agent safety/development rules.

## Legacy Removal Note

The old video-generation pipeline has been removed. It is no longer part of this repository and should not be used for current work.
