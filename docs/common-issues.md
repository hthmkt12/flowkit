# FBKit Common Issues

Use this file as the first stop before fixing any FBKit bug, runtime failure, or unexpected browser-extension behavior.

## Mandatory Bug-Fix Workflow

1. Read this file before changing code for a bug.
2. Search for matching symptoms first.
3. If a matching issue exists, try the documented checks and solutions before editing code.
4. If no matching issue exists, debug normally and confirm root cause first.
5. After every bug fix, update this file with a new issue entry or an improved existing entry.

## Required Entry Format

```md
## Issue: <short issue name>

### Symptoms
- ...

### Root Cause
- ...

### Common Triggers
- ...

### Solutions
- ...

### Verification
- ...
```

## Quick Checks

Run these first for current FBKit runtime issues:

```powershell
curl.exe http://127.0.0.1:8100/health
curl.exe http://127.0.0.1:8100/api/status
```

Expected health response:

```json
{"status":"ok"}
```

Expected status signal:

- extension connected when a Facebook tab is signed in and the Chrome extension is loaded
- at least one session with a non-empty `fb_uid` before account-targeted live dispatch
- worker/scheduler task stats present

If dashboard requests fail from a non-default dev host, add that origin to `CORS_ALLOWED_ORIGINS` instead of using a wildcard.

## Issue: Root endpoint must not expose extension identity

### Symptoms

- `GET /` returns extension session details.
- Response includes raw `fb_uid`, `profile_id`, or `profile_name`.

### Root Cause

- The root endpoint is a public basic metadata endpoint.
- Extension session identity belongs behind `/api/status`, which is protected when `API_AUTH_ENABLED=true`.

### Common Triggers

- Reusing `/api/status` payloads for top-level health or metadata responses.
- Adding status fields to `/` for convenience during local debugging.

### Solutions

- Keep `/` limited to app metadata and non-sensitive worker activity.
- Use `/health` for process readiness.
- Use `/api/status` for extension/session details.

### Verification

- `python -m pytest tests\unit\test_health.py -q` passes.
- `GET /` response does not contain `fb_uid`, `profile_id`, or `profile_name`.

## Issue: Extension is not connected

### Symptoms

- `GET /api/status` shows `extension.connected=false`.
- Dry-run smoke script cannot find a logged-in extension session.
- Worker tasks remain pending or fail before extension dispatch.

### Root Cause

- Chrome extension is not loaded, cannot reach the local WebSocket server, or no Facebook tab is open/signed in.

### Common Triggers

- Agent is not running on `ws://127.0.0.1:9222`.
- Extension was not loaded from `extension/`.
- Browser tab is not on `facebook.com` or user is signed out.
- `WS_AUTH_ENABLED=true` without matching extension credentials.

### Solutions

- Start the agent in safe mode.
- Reload the unpacked Chrome extension.
- Open `https://www.facebook.com/` and sign in.
- Check `GET /api/status` again.

### Verification

- `GET /api/status` returns `extension.connected=true`.
- At least one session reports `logged_in=true` and non-empty `fb_uid`.

## Issue: Dry-run smoke sees only stale logged-in sessions

### Symptoms

- Dry-run smoke exits before creating a job.
- Error says only stale logged-in extension sessions were found.
- `/api/status` contains a logged-in `fb_uid`, but the session is marked stale.

### Root Cause

- The extension heartbeat is no longer fresh enough for safe routing.
- Stale sessions are treated as offline for smoke selection and worker readiness.

### Common Triggers

- Facebook tab was closed, suspended, or switched profiles.
- Chrome extension reloaded but old session metadata remained visible briefly.
- Agent has not received a fresh heartbeat from the active tab.

### Solutions

- Open or refresh the signed-in Facebook tab.
- Reload the Chrome extension if heartbeat does not resume.
- Re-run the smoke only after `/api/status` shows a non-stale logged-in session.

### Verification

- `GET /api/status` shows `logged_in=true`, non-empty `fb_uid`, and `stale=false`.
- `python scripts/fbkit-dry-run-smoke.py` selects the fresh session.

## Issue: ZooPost setup refuses plaintext remote URL

### Symptoms

- `scripts/zoopost-agent-env-setup.py` exits before token exchange.
- Error says plaintext remote ZooPost Cloud URL is refused.

### Root Cause

- The setup helper sends a one-time registration token and optional bearer token.
- Non-loopback `http://` URLs could expose credentials in transit.

### Common Triggers

- Running setup against `http://staging.example.com`.
- Copying a local command and replacing only the hostname.

### Solutions

- Use `https://` for remote ZooPost Cloud setup.
- Keep `http://127.0.0.1` or `http://localhost` only for local loopback development.

### Verification

- Remote setup uses HTTPS.
- Loopback setup still works for local development.

## Issue: Dashboard realtime disconnects when auth key contains special characters

### Symptoms

- Browser console shows a WebSocket constructor/protocol error before the request reaches the server.
- Dashboard realtime stays offline even though REST API calls authenticate.
- The local API or ZooPost bearer key contains `/`, `=`, or other non-token characters.

### Root Cause

- Browser WebSocket subprotocol values allow a narrower character set than REST bearer headers.
- Dashboard credentials must not be sent in query strings, so the client sends `bearer.b64.<base64url-token>` and the servers decode it.

### Solutions

- Use the current dashboard build so `dashboardWebSocketProtocols()` emits the base64url bearer subprotocol.
- Keep query-string credentials disabled for dashboard realtime, even in local unauthenticated mode.
- Leave existing `bearer.<token>` support only for compatibility with older clients or tests.

### Verification

- `npm run test -- --run src/api/useWebSocket.test.ts` passes from `flowkit/dashboard`.
- `python -m pytest tests\unit\test_auth.py -q` passes from `flowkit`.
- `python -m pytest tests\contract\test_dashboard_api.py -q` passes from `zoopost-cloud`.

## Issue: Live task stays dry-run

### Symptoms

- Task result contains `dryRun=true`.
- Payload includes `safetyReason` such as `live_actions_disabled`, `approval_required`, or `extension_live_actions_disabled`.

### Root Cause

- FBKit is dry-run first. Server and extension guards independently prevent live Facebook mutations until explicitly configured and approved.

### Common Triggers

- `LIVE_ACTIONS_ENABLED=false`.
- `APPROVAL_REQUIRED=true` and task lacks server-owned `_serverApproved=true`.
- Extension-side `EXTENSION_LIVE_ACTIONS_ENABLED=false`.

### Solutions

- For normal development, do nothing; dry-run is the intended safe behavior.
- For a controlled live test, use a dedicated test account/page/group, explicitly enable the required server and extension guards, and approve only after reviewing the payload.

### Verification

- Safe validation should complete with `dryRun=true`.
- Do not call `POST /tasks/{task_id}/approve` during cleanup or dry-run validation.

## Issue: Account-targeted live task fails because `fb_uid` is missing

### Symptoms

- Live mutating worker task fails closed before extension dispatch.
- Error mentions missing or unresolved `fb_uid`.

### Root Cause

- Live mutating tasks require exact account routing. FBKit must not fall back to an arbitrary connected session for account-targeted live actions.

### Common Triggers

- Local account record was created without a resolved Facebook UID.
- Extension session is connected but not matched to the task account.

### Solutions

- Verify extension session through `GET /api/status`.
- Ensure the local account has the correct `fb_uid` before live dispatch.
- Keep dry-run mode until account routing is verified.

### Verification

- `GET /api/status` shows a session with the expected `fb_uid`.
- Dry-run task can route safely.
- Live mutating task does not dispatch unless exact routing is available.

## Issue: ZooPost target metrics never update

### Symptoms

- Completed ZooPost posts keep showing zero reach and engagement.
- FBKit logs `Unknown method: get_post_metrics` or a 401 metrics response.

### Root Cause

- The extension router did not implement the read-only `get_post_metrics` command.
- Metrics uploads used an optional development user bearer token instead of the paired agent credential.

### Common Triggers

- Running the normal pairing helper, which configures `ZOOPOST_AGENT_CREDENTIAL` but no development bearer token.
- Starting metrics collection while the target post is not visible in the connected Facebook tab.

### Solutions

- Keep the extension metrics handler and agent-gateway metrics endpoint aligned.
- Authenticate metrics uploads with `X-Agent-Credential`.
- Treat a post that is not visible in the current tab as unavailable rather than uploading fabricated metrics.
- Process only a bounded batch of recent posts and record `metrics_synced_at` after a successful upload.
- Use `ZOOPOST_METRICS_BATCH_LIMIT`, `ZOOPOST_METRICS_REFRESH_SECONDS`, and `ZOOPOST_METRICS_MAX_AGE_DAYS` to tune refresh load.

### Verification

- `python -m pytest tests\unit\test_extension_dry_run.py tests\unit\test_zoopost_adapter.py tests\unit\test_crud.py -q` passes from `flowkit`.
- `python -m pytest tests\contract\test_target_metrics.py -q` passes from `zoopost-cloud`.
