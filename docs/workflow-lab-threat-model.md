# Workflow Lab threat model

Workflow Lab is local-only and read-only. Its durable evidence uses a positive schema: method, host, path shape, status, resource type, bounded timing, query-key shape, and capture-scoped value aliases. It never accepts or persists response bodies, headers, cookies, bearer tokens, POST bodies, URL fragments, or arbitrary CDP payloads.

The sealed capability gate permits only `inspect` for the reviewed `post_metrics` and `page_reader` adapters. There is no generic request executor, replay promotion, mutation operation, or user-controlled URL fetch path. Capture authentication is independent from the existing local agent transport and must be bound to the active profile and Facebook identity before a capture is accepted.

Retention is bounded by TTL, per-capture quotas, and explicit stop/delete controls. Redaction is applied before persistence, dashboard display, MCP exposure, or export. Any uncertainty fails closed and leaves the capture as analysis-only evidence.

| Boundary | Owner | Mitigation | Detection | Rollback |
| --- | --- | --- | --- | --- |
| Browser capture | extension capture module | debugger lease, dedicated nonce, metadata-only schema | capture audit and quota errors | stop capture, release lease, revoke nonce |
| Local persistence | WorkflowStore | isolated SQLite, TTL/GC, profile binding | startup/periodic GC and integrity checks | delete Workflow Lab store only |
| Adapter execution | sealed capability gate | `get_post_metrics`/`read_page_clone` inspect-only allowlist | denied-operation audit | unregister adapter and clear drafts |
| Export/MCP | local integration | opaque IDs, recursive redaction, off by default | secret-canary tests | disable integration and rotate local key |
