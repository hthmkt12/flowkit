# FBKit

FBKit is the active project in this repository. It is a local-first Facebook automation assistant using a Python FastAPI agent, SQLite task queue, and Chrome extension WebSocket bridge.

Base URL: `http://127.0.0.1:8100`

## Marketing Context (Current)

- Product name: **FBKit**
- Tagline: **local-first Facebook automation assistant**
- Positioning: safer local-first alternative to cloud social automation tools
- Primary audience: small agencies, SMB marketers, founder-led teams
- Main objective: near-term lead generation via product-led demos
- Market status: no public website, pricing not published

## Critical Safety Rules

1. Default to safe local mode: `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`.
2. Never trigger, approve, or enable real Facebook/social mutations unless the user explicitly requests it and provides a safe target.
3. Treat posting, messaging, liking, commenting, sharing, friend actions, group actions, page follow/unfollow, and reup tasks as mutating.
4. Safety Gate is server-owned. Client payload fields like `approved`, `_serverApproved`, and `_quotaReserved` must not be trusted from external callers.
5. Do not live-test inbox/comment/engagement automation until the posting flow is proven safe on a dedicated test account/page/group.

## How To Work

1. Read `README.md` first for the current quick start and safety defaults.
2. Use minimal, direct edits. Do not create enhanced duplicate files when an existing file should be updated.
3. Use TDD for feature, fix, and behavior changes. Verify RED before writing production code, then verify GREEN.
4. Run compile/tests after code changes. Do not ignore failures or make fake changes just to pass tests.
5. Do not commit or push unless the user explicitly asks.
6. Do not add secrets, `.env` contents, credentials, cookies, browser profiles, logs, or generated local artifacts to git.

## Test Commands

Use the repo virtualenv on Windows:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py -q
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_crud.py -q
& ".\.venv\Scripts\python.exe" -m pytest
```

`pytest` may not be on PATH. Use `curl.exe` instead of PowerShell's `curl` alias for HTTP checks.

## Dry-Run Runtime Smoke

Only use dry-run mode unless the user explicitly approves a live test:

```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
& ".\.venv\Scripts\python.exe" -m agent.main
```

Then run:

```powershell
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py
```

The expected result is a completed task with `dryRun=true`. The smoke script must not approve tasks or perform live Facebook actions.
