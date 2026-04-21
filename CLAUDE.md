# Flow Kit

Base URL: `http://127.0.0.1:8100`

## Pre-flight

```bash
curl -s http://127.0.0.1:8100/health
# Must return: {"extension_connected": true}
```

## How to work

- Always use `/fk:*` skills - all rules and workflows live inside each skill
- Never write scripts to loop API calls - use `POST /api/requests/batch`
- `media_id` is always UUID format (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`), never `CAMS...` strings
- Before fixing any bug, always read `./docs/common-issues.md` first. If the symptom matches a known issue, try the documented checks and recovery path before editing code.
- After every bug fix, update `./docs/common-issues.md`. Use this exact entry format: `Symptoms / Root Cause / Common Triggers / Solutions / Verification`.
- Do not consider a bug fix complete until `./docs/common-issues.md` has been updated or the matching existing entry has been improved.

## Plan Verification Rules

Apply before finalizing any multi-step implementation plan or bug-fix plan. Trust but verify between repo scan, assumptions, and final plan.

### Verification discipline

1. Verify factual claims against repo files - re-check every endpoint, request type, env var, path, port, and model-related claim from code or README. Do not copy assumptions from memory.
2. Trace behavior, not just filenames - if a plan mentions an existing field, route, or worker stage, verify when it changes and under what conditions it changes.
3. No fabricated APIs or symbols - do not invent route names, extension messages, request types, service helpers, or Google Flow concepts that do not exist in this repo.
4. Verify state lifetime before adding fields - confirm whether state lives in request scope, worker loop, SQLite row, extension storage, browser session, or runtime files before changing an existing structure.
5. Verify bug premise against `./docs/common-issues.md` first - if the issue already matches a known pattern, the plan must use the documented checks before proposing code changes.
6. Match config and payload shape exactly - if a plan reuses an existing request body, scene payload, or config object, verify field names and required values exactly as implemented.
7. Verify external or upstream-facing endpoints before adding them to a plan - FlowKit has internal API routes plus Google Flow behavior through the extension; do not conflate them.

### Scope and coverage

8. Scan backend and extension separately - `agent/` and `extension/` are different systems with different responsibilities. Do not assume a fix in one covers the other.
9. Enumerate all callers before changing shared contracts - if a route, model, or payload changes, list the API handler, worker code, extension usage, skills, and tests that must move with it.
10. Verify async pipeline dependencies - for image and video generation plans, confirm prerequisites like reference images, UUID `media_id` values, and downstream reset behavior before proposing changes.
11. Search delete and rename scope deeply - if removing or renaming a symbol, grep the whole repo and list every affected reference in the plan.

### Phasing and ordering

12. Re-scout when scope changes - if a deferred phase becomes active, re-check the current code instead of reusing stale assumptions from earlier notes.
13. Make phase gates explicit - each phase should state its verify condition, for example route tests pass, extension config still loads, or `/health` returns the expected state.
14. Bug fix plans need reproduction first - write down how to reproduce or test the failure before proposing the fix path.
15. Documentation updates are part of done - if a bug is fixed or a recurring issue is clarified, the plan must include updating `./docs/common-issues.md` before completion.

## Skills

| Skill | When to use |
|-------|-------------|
| `/fk-create-project` | New project with entities + scenes |
| `/fk-research` | Fact-check before scripting |
| `/fk-gen-refs` | Generate reference images for entities |
| `/fk-gen-images` | Generate scene images |
| `/fk-gen-videos` | Generate scene videos |
| `/fk-gen-chain-videos` | Videos with scene chaining transitions |
| `/fk-review-video` | Review video quality before upscale |
| `/fk-review-board` | Visual scene review board for feedback |
| `/fk-concat` | Download + concat final video |
| `/fk-concat-fit-narrator` | Concat trimmed to narrator duration |
| `/fk-gen-narrator` | Generate narrator text + TTS |
| `/fk-gen-text-overlays` | Generate text overlays from narrator text |
| `/fk-gen-tts-template` | Create voice template for narration |
| `/fk-gen-music` | Generate music via Suno |
| `/fk-creative-mix` | Creative video mixing techniques |
| `/fk-pipeline` | Full pipeline orchestration |
| `/fk-monitor` | Monitor running pipeline |
| `/fk-status` | Project status dashboard |
| `/fk-switch-project` | Switch active project |
| `/fk-fix-uuids` | Fix non-UUID media_ids |
| `/fk-refresh-urls` | Refresh expired GCS URLs |
| `/fk-add-material` | Set image material style |
| `/fk-change-model` | Change video/image model |
| `/fk-insert-scene` | Insert scenes into chain |
| `/fk-upload-image` | Upload local image to get media_id |
| `/fk-thumbnail` | Generate YouTube thumbnails |
| `/fk-brand-logo` | Apply channel logo watermark |
| `/fk-youtube-seo` | Generate YouTube metadata |
| `/fk-youtube-upload` | Upload to YouTube |
| `/fk-camera-guide` | Cinematic camera reference |
| `/fk-thumbnail-guide` | Thumbnail design reference |
| `/fk-import-voice` | Import existing voice template |
| `/fk-dashboard` | Live statusline setup |
