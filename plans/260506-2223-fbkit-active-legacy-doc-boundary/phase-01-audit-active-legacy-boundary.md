# Phase 01 Audit Active Legacy Boundary

## Context Links

- Overview: `plan.md`
- Active runtime source: `../../docs/codebase-summary.md`
- Operator entry point: `../../README.md`
- Current architecture conflict: `../../ARCHITECTURE.md`
- Agent rules: `../../CLAUDE.md`, `../../AGENTS.md`

## Overview

Priority: High

Status: Completed

This phase identifies exact documentation places where active FBKit and legacy Google Flow concepts are mixed. It does not edit files.

## Requirements

- Confirm active docs already state FBKit is current.
- Identify docs that still present Google Flow as current system architecture.
- Identify safety-critical wording that must be preserved.
- Avoid reading secrets, local databases, logs, cookies, or browser profiles.

## Related Files

- Read: `README.md`
- Read: `ARCHITECTURE.md`
- Read: `PLAN.md`
- Read: `docs/codebase-summary.md`
- Read: `CLAUDE.md`
- Read: `AGENTS.md`
- No files modified in this phase.

## Implementation Steps

- [x] Step 1: Search for docs that describe FlowKit or Google Flow as current.

Run from repo root `D:\vm extention  facebook\flowkit`:

```powershell
rg -n "Google Flow|FlowKit|FBKit|active project|active product|Current FBKit|Legacy FlowKit|Architecture" README.md ARCHITECTURE.md PLAN.md docs CLAUDE.md AGENTS.md
```

Expected: matches in `README.md`, `ARCHITECTURE.md`, `PLAN.md`, and `docs/codebase-summary.md`.

- [x] Step 2: Record files needing doc edits in the phase notes.

Use this exact classification:

```text
Edit needed:
- README.md: only if first-screen active/archive boundary needs stronger wording.
- ARCHITECTURE.md: add current FBKit architecture section before legacy Google Flow content.
- docs/codebase-summary.md: update only if it references missing canonical architecture doc after Phase 2.

No edit expected:
- CLAUDE.md: already enforces FBKit safety rules.
- AGENTS.md: already enforces FBKit safety rules.
- PLAN.md: legacy planning artifact; do not rewrite unless user confirms Google Flow is dead.
```

- [x] Step 3: Confirm Safety Gate language to preserve.

Check these strings are present in active docs:

```powershell
rg -n "LIVE_ACTIONS_ENABLED|DRY_RUN_DEFAULT|APPROVAL_REQUIRED|Safety Gate|dry-run|dryRun|extension_live_actions_disabled|_serverApproved" README.md docs/codebase-summary.md CLAUDE.md AGENTS.md
```

Expected: matches for all three env vars and Safety Gate behavior.

- [x] Step 4: Stop and ask user before any larger cleanup.

Ask this question if the audit shows Google Flow code/docs are still deeply referenced:

```text
Google Flow references are still broad. Should this plan remain docs-only, or should a separate legacy inventory/removal plan be created?
```

## Success Criteria

- Audit identifies exact docs to edit.
- No runtime code touched.
- No generated artifacts committed or saved outside this plan.

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Accidentally treating legacy docs as active | Use `docs/codebase-summary.md` as current source. |
| Over-scoping into cleanup | Keep this phase read-only. |
| Weakening safety guidance | Preserve all safe default language exactly. |

## Security Considerations

- Do not inspect `fbkit.db`, cookies, browser profiles, `.env`, or credentials.
- Do not run the agent or extension.
- Do not trigger task creation or approval endpoints.

## Next Steps

- Proceed to Phase 2 only after the audit confirms docs-only edits are enough.

## Unresolved Questions

- Is `PLAN.md` retained only as historical artifact, or should it be moved into a legacy archive later?
