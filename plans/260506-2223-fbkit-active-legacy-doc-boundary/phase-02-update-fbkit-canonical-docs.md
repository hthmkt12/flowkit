# Phase 02 Update FBKit Canonical Docs

## Context Links

- Overview: `plan.md`
- Audit: `phase-01-audit-active-legacy-boundary.md`
- Active runtime source: `../../docs/codebase-summary.md`
- Existing architecture doc: `../../ARCHITECTURE.md`

## Overview

Priority: High

Status: Completed

This phase makes the smallest doc edits needed to show FBKit as current and Google Flow as legacy archive/reference.

## Requirements

- Keep active safety defaults prominent.
- Avoid broad rewrite of legacy sections.
- Prefer adding a clear current section over deleting history.
- Preserve existing README quick start commands.

## Architecture

The canonical current shape should be documented as:

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

## Related Files

- Modify: `ARCHITECTURE.md`
- Modify if needed: `README.md`
- Modify if needed: `docs/codebase-summary.md`
- Do not modify: `agent/**`, `extension/**`, `tests/**`, database files.

## Implementation Steps

- [x] Step 1: Add a current FBKit section at the top of `ARCHITECTURE.md`.

Insert after `# Flow Kit — Architecture` and before the current `## Overview` section:

````markdown
## Current Active Architecture: FBKit

FBKit is the active system in this repository. It is a local-first Facebook automation assistant using a Python FastAPI agent, a SQLite task queue, and a Chrome extension WebSocket bridge connected to a logged-in browser session.

The current architecture is safety-first:

- server Safety Gate enforces dry-run defaults before task creation
- worker re-enforces Safety Gate immediately before dispatch
- live mutating tasks require server-owned approval
- `FBClient` routes exact account targets by `fb_uid`
- the Chrome extension keeps an independent DOM-action guard
- live Facebook actions stay disabled unless the user explicitly requests a controlled live test with a safe target and verified Safety Gate behavior

Current FBKit data flow:

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

For verified Safety Gate entry points and runtime behavior, see `docs/codebase-summary.md`.

## Legacy Google Flow Archive

The sections below describe the original Google Flow video-generation architecture. They are retained for historical/reference use and are not the current FBKit operational architecture.
````

- [x] Step 2: Rename the old `## Overview` heading in `ARCHITECTURE.md`.

Change:

```markdown
## Overview
```

To:

```markdown
## Legacy Overview
```

- [x] Step 3: Strengthen README active/archive boundary only if the audit found ambiguity.

If needed, replace README lines near the documentation map with:

```markdown
For current work, treat FBKit as the active product. The Safety Gate model in `docs/codebase-summary.md`, the quick start below, and the FBKit safety rules in `CLAUDE.md` / `AGENTS.md` take precedence over legacy Google Flow archive sections.
```

Do not remove the existing quick start.

- [x] Step 4: Update `docs/codebase-summary.md` only if `ARCHITECTURE.md` now needs a cross-reference.

Add this short note under `## Current Runtime Shape` if absent:

```markdown
For high-level architecture orientation, read the current FBKit section at the top of `ARCHITECTURE.md` before using legacy Google Flow archive sections.
```

- [x] Step 5: Review exact changed docs.

Run:

```powershell
git diff -- README.md ARCHITECTURE.md docs/codebase-summary.md
```

Expected: only documentation text changed; no code, tests, database, or generated artifacts changed.

## Success Criteria

- `ARCHITECTURE.md` opens with current FBKit architecture.
- Legacy Google Flow architecture is clearly labeled archive/reference.
- README remains operationally correct for safe dry-run startup.
- Safety Gate defaults are not weakened.

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Markdown fence nesting breaks rendering | Use `text` fenced block inside markdown section exactly as shown. |
| Legacy content accidentally deleted | Add current section; avoid deletion. |
| Safety wording becomes less strict | Keep live-action warnings and env defaults unchanged. |

## Security Considerations

- No runtime commands that create tasks.
- No live Facebook action flags changed.
- No approval endpoint calls.

## Next Steps

- Proceed to Phase 3 validation.

## Unresolved Questions

- Should a future ADR record FBKit as active product and Google Flow as archive?
