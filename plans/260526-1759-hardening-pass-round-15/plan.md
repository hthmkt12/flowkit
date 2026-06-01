# Hardening Pass Round 15

Status: Complete
Date: 2026-05-26

## Goal

Fix the Flowkit unauthenticated root endpoint identity leak with regression tests, docs, and fresh verification.

## Scope

- Flowkit FastAPI root/status surface.
- No live Facebook mutation.
- Preserve existing dirty worktree changes from earlier hardening rounds.

## Finding

`GET /` returned `client.ws_stats`, which can include extension session identity fields such as `fb_uid`, `profile_id`, and `profile_name`. Because `/` is public even when `API_AUTH_ENABLED=true`, it could leak local Facebook account routing metadata.

## Fix

- Keep `/` as public app metadata and worker activity only.
- Leave extension/session detail under `/api/status`, which uses `require_api_key` when API auth is enabled.

## Tests

- Added a regression that injects sensitive extension session identity into `get_fb_client().ws_stats`.
- The test failed before the fix because `/` returned the raw identity values.
- It now verifies `/` omits `fb_uid`, `profile_id`, and `profile_name`.

## Verification

- `python -m pytest tests\unit\test_health.py::test_root_does_not_expose_extension_session_identity -q`

## Unresolved Questions

None.
