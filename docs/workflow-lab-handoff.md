# Workflow Lab handoff state

## Verified locally

- Versioned read-only contracts, redaction, replayability analyzer, adapter registry, isolated SQLite store and profile-scoped inspect API.
- Pure extension capture/controller and exclusive lease primitives with Node tests.
- Read-only dashboard route and disabled-by-default local MCP.
- Synthetic capture-to-MCP proof is secret-free; full Python suite passed with `PYTHONUTF8=1`.

## Explicitly not claimed

- No real Facebook HAR is imported or uploaded.
- No response-body capture, arbitrary HTTP replay, mutation, adapter promotion, or Cloud MCP exposure exists.
- `lease.mjs` is not yet wired into the existing `background.js` upload/debugger lifecycle.
- Chrome lifecycle evidence (debugger conflict, tab close, logout/UID drift, worker wake reconciliation) is still manual and requires the Page Clone P4 shared-seam handoff.
- Root ZooPost MCP verifier remains environment-blocked by the optional `mcp` package dependency.

## Safe rollback

Disable the capture flag/key, stop active controllers, revoke local capture credentials, release leases, then run Workflow Lab TTL GC. Remove only the isolated Workflow Lab modules and runtime database; preserve unrelated pilot/Page Clone changes.
