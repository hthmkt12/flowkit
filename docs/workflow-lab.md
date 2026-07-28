# FBKit Workflow Lab

Workflow Lab is a local, read-only inspection surface for attended capture metadata. It stores bounded positive-schema evidence in a dedicated SQLite store, classifies replayability, and exposes only reviewed adapters (`get_post_metrics` and `read_page_clone`) in inspect mode.

The capture layer never stores response bodies, headers, cookies, post bodies, query values, credentials, or arbitrary URLs. The dashboard and local MCP render opaque IDs and sanitized metadata only. MCP is disabled unless `WORKFLOW_LAB_MCP_ENABLED=1` (or `true`/`yes`) and requires a profile-scoped capture key.

Operational rollback is fail-closed: stop captures, revoke capture keys/nonces, release debugger leases, then run bounded GC. The debugger lease wiring into the existing service worker remains deferred until the Page Clone shared-seam handoff; no claim of synchronous cleanup is made during worker suspension.

## Verification

- `PYTHONUTF8=1 .venv\\Scripts\\python.exe -m pytest -q`: 655 passed.
- `node --test extension\\tests\\capture.test.mjs`: 6 passed.
- Dashboard: 61 tests passed, lint passed, build passed.
- Local Workflow Lab MCP: 2 tests passed.
- Synthetic capture → store → analyzer → adapter proof: 1 test passed with no fixture secret, query value, response body, or credential in serialized evidence.
- Root ZooPost MCP verifier: **16 passed**, import check OK after installing the declared `integrations/zoopost-mcp-readonly/requirements-runtime.txt` dependencies into the nested venv.
