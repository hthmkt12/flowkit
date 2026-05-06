---
title: "FBKit Dry-Run Runtime Validation Report"
date: "2026-05-06"
type: "runtime-validation"
scope: "FBKit safe-mode dry-run smoke variants"
---

# FBKit Dry-Run Runtime Validation Report

## Summary

Runtime dry-run validation was recorded for the FBKit smoke variants under safe local flags. The validation confirmed completed dry-run task flow for `POST_TEXT`, `LIKE_POST`, `COMMENT_POST`, and `SEND_MESSAGE` without enabling live actions or calling approval endpoints.

## Safe Flags Used

| Flag | Value |
|---|---:|
| `LIVE_ACTIONS_ENABLED` | `false` |
| `DRY_RUN_DEFAULT` | `true` |
| `APPROVAL_REQUIRED` | `true` |
| `API_AUTH_ENABLED` | `false` |
| `WS_AUTH_ENABLED` | `false` |

## Runtime Results

| Check | Result |
|---|---|
| `POST_TEXT` smoke variant | Passed in dry-run mode |
| `LIKE_POST` smoke variant | Passed in dry-run mode |
| `COMMENT_POST` smoke variant | Passed in dry-run mode |
| `SEND_MESSAGE` smoke variant | Passed in dry-run mode |
| `/api/status` | Worked during runtime validation |
| `/health` | Returned `{ "detail": "Not Found" }` during this validation; later commit `94e9bce` added basic `GET /health` returning `{ "status": "ok" }` |

## Safety Notes

- No live Facebook actions were enabled.
- `LIVE_ACTIONS_ENABLED=true` was not set.
- No tasks were approved.
- Approval endpoints were not called.
- Smoke variants completed only when the result preserved `dryRun=true`.

## Commands Validated

```powershell
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant POST_TEXT
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant LIKE_POST --content "https://www.facebook.com/example/posts/example"
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant COMMENT_POST --content "https://www.facebook.com/example/posts/example"
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant SEND_MESSAGE --content "100000000000000"
```

## Recommendations

- Keep the documented safe flags for local smoke validation.
- Treat `/api/status` as the current runtime readiness check for extension/session visibility.
- Use `/health` only as a basic process check in versions that include commit `94e9bce` or later.

## Unresolved Questions

None.
