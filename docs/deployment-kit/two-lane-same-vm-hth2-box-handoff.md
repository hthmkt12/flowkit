# Two-Lane Same-VM Handoff: `hth2-box`

## Goal

Continue from the current hybrid demo and implement **2 real lanes on the same VM `hth2-box`**.

Target shape:

- `lane-01` stays on `127.0.0.1:8100` + `127.0.0.1:9222`
- `lane-02` gets its own runtime on `127.0.0.1:8110` + `127.0.0.1:9232`
- each lane has:
  - separate runtime dir
  - separate worker dir
  - separate Chrome profile
  - separate extension build/config
  - separate Google account session

## Current status after April 22, 2026 update

### Repo changes now in place

- extension now reads lane-specific endpoints from `manifest.json` `flowkit` config
- new render utility exists:
  - `docs/deployment-kit/worker/scripts/render-extension-bundle.py`
- new render helper exists:
  - `docs/deployment-kit/worker/fk_worker/extension_bundle.py`
- `bootstrap-lane.sh` now supports:
  - custom `DEPLOY_ROOT`
  - custom API / WS / runner-health ports
  - empty `SUDO_BIN` for non-root host demo bootstrap
  - missing `tests/` and missing `systemd/` source dirs

### Local Windows state

- lane-02 unpacked extension rendered to:
  - `C:\temp\flowkit-extension-unpacked-lane-02`
- lane-02 Chrome profile root created:
  - `C:\temp\flowkit-real-chrome-lane-02\UserData`
- lane-02 tunnel process started locally:
  - `ssh -N -L 8110:127.0.0.1:8110 -L 9232:127.0.0.1:9232 hth2-box`
- lane-02 Chrome was launched with the new profile and extension path
- April 22 follow-up:
  - local Tailscale was found logged out
  - `tailscale login` was completed on the local Windows machine
  - local tailnet state is back to `BackendState=Running`
  - local node IP is now `100.109.92.89`
  - `hth2-box` later came back online on Tailscale
  - lane-02 tunnel is active again for:
    - `8110`
    - `9232`
    - `18182`
  - lane-02 Chrome was launched again with:
    - `chrome://extensions`
    - `https://labs.google/fx/tools/flow`
  - important Chrome note:
    - current branded Chrome ignored plain `--load-extension`
    - the launch that actually worked used:
      - `--disable-features=DisableLoadExtensionCommandLineSwitch,DisableDisableExtensionsExceptCommandLineSwitch`

### Current live state after reconnect

- local lane-02 health now reports:
  - `http://127.0.0.1:8110/health`
  - `extension_connected=true`
  - `ws.connected=true`
- local lane-02 Flow status now reports:
  - `http://127.0.0.1:8110/api/flow/status`
  - `connected=true`
  - `flow_key_present=true`
- lane-02 runner health now reports:
  - `http://127.0.0.1:18182/ready`
  - `200`
- lane-02 runner process was restarted on VM and is now listening on:
  - `127.0.0.1:18182`
- control demo services were restarted on VM and are now up again:
  - `fk_control.api`
  - `fk_control.scheduler`

### Current live state after ops-hardening bring-up

As of April 22, 2026 later in the day:

- control host-process services are up again on `hth2-box`:
  - `http://127.0.0.1:18080/health` -> `{"status":"ok","postgres":true,"redis":true}`
  - live process model:
    - `python3 -m fk_control.api`
    - `python3 -m fk_control.scheduler`
- local Windows tunnels are active for both lanes:
  - lane-01:
    - `8100 -> 8100`
    - `9222 -> 9222`
  - lane-02:
    - `8110 -> 8110`
    - `9232 -> 9232`
    - `18182 -> 18182`
- local Chrome profiles were launched again with the correct unpacked extensions:
  - lane-01:
    - `C:\temp\flowkit-real-chrome\UserData`
    - `C:\temp\flowkit-extension-unpacked`
  - lane-02:
    - `C:\temp\flowkit-real-chrome-lane-02\UserData`
    - `C:\temp\flowkit-extension-unpacked-lane-02`
- both host-process lane runners are currently running on VM:
  - lane-01:
    - `http://127.0.0.1:18181/ready` -> `200`
    - status now `idle`
  - lane-02:
    - `http://127.0.0.1:18182/ready` -> `200`
    - status now `idle`
- control `/overview` now shows both real lanes as dispatchable:
  - `lane-01.status=idle`
  - `lane-02.status=idle`
  - both lanes now have:
    - `lane_metadata.runner_ready=true`
    - `dispatchable_reason=ready`
    - `extension_connected=true`
    - `flow_connected=true`

### Important ops-hardening notes from live bring-up

- the new readiness gating works live:
  - when extension/account was not connected, a lane stayed `paused`
  - after reconnect, the same lane moved automatically to `idle`
  - `/ready` stayed `503` until the lane was truly usable
- lane-02 was the first live proof:
  - runner stayed up
  - `/health` reported:
    - `dispatchable_reason=extension_disconnected`
  - after local Chrome reconnect, lane-02 moved to:
    - `runner_ready=true`
    - `status=idle`
- lane-01 needed one extra env correction on VM to match the host-demo control stack:
  - `REDIS_URL` changed from:
    - `redis://127.0.0.1:16379/0`
    - to `redis://127.0.0.1:6379/0`
  - `POSTGRES_DSN` changed from host publish port `15432`
    - to direct host-local `5432`
  - backup saved at:
    - `/home/hth2/flowkit-worker-demo/env/lane.env.bak.ops-hardening`
- current control wrapper usage on this VM is slightly special:
  - repo script:
    - `control/scripts/control-service.sh`
  - but this host demo uses host-local Postgres/Redis and published API `18080`
  - when using the wrapper directly on VM, pass host-demo env overrides:
    - `CONTROL_API_URL=http://127.0.0.1:18080`
    - `CONTROL_API_PORT=18080`
    - `POSTGRES_DSN=postgresql://...@127.0.0.1:5432/fk_control`
    - `REDIS_URL=redis://127.0.0.1:6379/0`
    - `PYTHON_BIN=python3`

### Latest auth/readiness finding

After both local profiles were reconnected and both runners restarted:

- lane-02 is fully ready again:
  - `/api/flow/credits` returns real credits
  - runner reports:
    - `flow_auth_valid=true`
    - `runner_ready=true`
    - status `idle`
- lane-01 exposed an additional real bug and account issue:
  - local `GET http://127.0.0.1:8100/api/flow/credits` returned:
    - embedded JSON `error`
    - code `401`
    - status `UNAUTHENTICATED`
  - direct local create-project attempt on lane-01 failed with:
    - `Flow createProject failed: Unauthorized (UNAUTHORIZED)`
  - important nuance:
    - this credits/auth failure came back as HTTP `200` with an embedded `error` object
    - readiness logic was patched locally to detect that case
  - after syncing the patch and restarting runners:
    - lane-01 now correctly moves to status `paused`
    - lane-01 metadata shows:
      - `flow_auth_valid=false`
      - `dispatchable_reason=flow_auth_invalid`
    - lane-02 stays `idle`

Current best interpretation:

- same-VM dual lane runtime layout is healthy
- gating now prevents false-positive dispatch into a bad account session
- only remaining live blocker is lane-01 Google auth/session refresh inside the local lane-01 Chrome profile

### Latest low-cost live proof after hardening

One extra direct low-cost proof was run on lane-02 after readiness hardening:

- direct local API call:
  - `POST http://127.0.0.1:8110/api/projects`
- result:
  - project created successfully on real Flow
  - returned project id:
    - `a0353d82-d7ee-4ce1-97ed-03ea09453142`
  - title:
    - `Lane 02 Direct Create Only Smoke 2026-04-22 16-38`
- immediate post-check:
  - `GET http://127.0.0.1:8110/api/flow/credits` still returned valid credits
  - lane-02 runner stayed:
    - `idle`
    - `runner_ready=true`

Interpretation:

- lane-02 is not only "connected"
- lane-02 is now proven able to execute at least the first real paid/control-relevant Flow action after ops-hardening
- this was done without re-running a full chapter pipeline

### Final state after lane-01 auth refresh

Later in the same session, lane-01 local Chrome was restarted cleanly on the
correct profile and the auth state recovered:

- local `GET http://127.0.0.1:8100/api/flow/credits` now returns real credits:
  - `100`
- lane-01 runner now reports:
  - `flow_auth_valid=true`
  - `runner_ready=true`
  - status `idle`
- control `/overview` now shows:
  - `lane-01.status=idle`
  - `lane-02.status=idle`
  - both lanes have:
    - `dispatchable_reason=ready`

Another low-cost direct proof was then run on lane-01:

- direct local API call:
  - `POST http://127.0.0.1:8100/api/projects`
- result:
  - project created successfully on real Flow
  - returned project id:
    - `80cb55f6-95f5-4675-bed0-bf703ea4c687`
  - title:
    - `Lane 01 Direct Create Only Smoke 2026-04-22 16-43`
- immediate post-check:
  - lane-01 credits still returned valid data
  - lane-01 runner stayed `idle`

End-of-session interpretation:

- same-VM dual lane is now operational in the lab in a meaningful sense
- both lanes are:
  - independently wired
  - independently authenticated
  - independently `ready`
  - each proven able to execute direct `create-project`
- next meaningful proof beyond this point would be a control-routed chapter run,
  which is more credit-sensitive than the direct create-only checks above

### Additional control-plane create-only proof

One more low-cost proof was run through the control-plane job contract itself:

- a control project/chapter was created directly in control DB:
  - project id:
    - `791c0c5d-48e9-4026-b460-b2f4f25e63e9`
  - chapter id:
    - `383145d8-7fdf-47bb-af29-f4a967ce9f95`
- scheduler lane choice logic selected:
  - `lane-02`
- only the first control job was intentionally enqueued:
  - `CREATE_PROJECT`
  - job id:
    - `deb53350-d7fb-437e-8092-0a1ba7b1edb7`
- that control job completed successfully
- chapter now has a real Flow project id:
  - `c1f4a660-13fb-4d55-8c26-e354bf87876f`
- to avoid running the rest of the pipeline, the chapter was intentionally tagged as:
  - `review_required`
  - with metadata note:
    - `stopped intentionally after CREATE_PROJECT for low-cost control-plane proof`

Interpretation:

- control DB rows
- control job persistence
- Redis lane queue contract
- runner consumption
- and real Flow create-project

have now all been proven together without releasing a full paid chapter pipeline.

### Additional low-cost lane-01 pipeline proof after control create-only

The lane-01 control smoke chapter was pushed a bit further, still staying below
video generation:

- chapter:
  - `2d203365-f19c-47f1-b7ea-ddf20674df46`
- project:
  - `9765a16e-f869-4142-abda-53e85996a15e`
- local Flow project id:
  - `ffb39de3-ef92-40cf-a72e-b7dc03cfe0b9`

Control-routed jobs completed successfully on `lane-01`:

- `CREATE_PROJECT`
- `CREATE_ENTITIES`
- `CREATE_VIDEO`
- `CREATE_SCENES`
- `GEN_REFS`
- `GEN_IMAGES`

Concrete lane-01 proof after `GEN_IMAGES`:

- local scene list for video:
  - `3b43d114-e7e8-473b-b0af-5089887cb55a`
- scene:
  - `13c6ea9a-cf70-4550-8aeb-d8ad8770f8b6`
- scene image output:
  - `vertical_image_status=COMPLETED`
  - `vertical_image_media_id=aaa88516-f3fc-4f62-a9c1-41885f8d5cfc`
- reference entity for that chapter also has real media:
  - entity id:
    - `4958cac8-1a50-4be7-8818-c25c1617dc4f`
  - ref media id:
    - `c13aa193-5993-4023-a3a1-9fc62bc09579`

Important:

- lane-01 credits still remained readable after this proof:
  - `100`
- lane-01 runner stayed:
  - `idle`
  - `runner_ready=true`
- chapter was intentionally forced back to:
  - `review_required`
  - to avoid flowing into `GEN_VIDEOS`

Interpretation:

- lane-01 is now proven not only for auth and create-project
- it is also proven through the first real media-generation stages of the
  control-routed worker path on the same VM lab setup

Current logical next spend-heavy step, if ever resumed:

- `GEN_VIDEOS` for the 1-scene lane-01 control smoke chapter
- this is the first next step that is materially more credit-sensitive than the
  work already completed above

### Latest lane-01 video proof

That "next spend-heavy step" was later exercised once for the same 1-scene
lane-01 control smoke chapter:

- chapter:
  - `2d203365-f19c-47f1-b7ea-ddf20674df46`
- video:
  - `3b43d114-e7e8-473b-b0af-5089887cb55a`
- scene:
  - `13c6ea9a-cf70-4550-8aeb-d8ad8770f8b6`

Control-routed `GEN_VIDEOS` on `lane-01` completed successfully:

- job id:
  - `2e3a4c2d-9331-4a90-b7a4-9b4d0627c1a4`
- result on scene row:
  - `vertical_video_status=COMPLETED`
  - `vertical_video_media_id=d37cc7fe-289b-42d0-bb69-08acb35a97a9`

Immediate post-check:

- lane-01 credits still remained valid:
  - dropped from `100` to `80`
- lane-01 runner stayed:
  - `idle`
  - `runner_ready=true`
- chapter was intentionally kept at:
  - `review_required`
  - to avoid moving into `CONCAT_CHAPTER` / `UPLOAD_ARTIFACTS`

Updated interpretation:

- lane-01 is now proven through:
  - auth
  - create-project
  - create-entities
  - create-video
  - create-scenes
  - gen-refs
  - gen-images
  - gen-videos

At this point the next meaningful unpaid-ish boundary is gone.
The remaining next steps are fundamentally end-of-chapter steps:

- `CONCAT_CHAPTER`
- `UPLOAD_ARTIFACTS`

Those are operationally cheaper than video generation, but they only make sense
if we intentionally decide to complete this smoke chapter end-to-end.

### Final lane-01 end-to-end completion state

The lane-01 control smoke chapter was later finished through the remaining end
stages:

- chapter:
  - `2d203365-f19c-47f1-b7ea-ddf20674df46`
- concat job:
  - `ceaddccc-2c3d-4ba7-af10-35ae91121989`
- upload job:
  - `efab712a-8e4e-4212-91ba-cf621065960a`

What happened:

- both jobs initially executed the real work
- but job completion bookkeeping failed with:
  - `Object of type UUID is not JSON serializable`
- root cause:
  - worker `CONCAT_CHAPTER` / `UPLOAD_ARTIFACTS` result payloads returned
    `chapter_id` as Python `UUID` instead of string
- repo fix was added locally:
  - stage result ids are now stringified before `mark_job_completed()`
- live lane worker code was synced with the fix

Live chapter state after repair:

- chapter now marked:
  - `completed`
- `chapter_output_uri`:
  - `/home/hth2/flowkit-worker-demo/runtime/output/control_create_only_smoke_lane_01_2026_04_22_chapter_01/control_create_only_smoke_lane_01_2026_04_22_chapter_01_final.mp4`
- artifact row exists:
  - `chapter_final`
  - `storage_uri=file:///home/hth2/flowkit-worker-demo/runtime/output/control_create_only_smoke_lane_01_2026_04_22_chapter_01/control_create_only_smoke_lane_01_2026_04_22_chapter_01_final.mp4`
- control job rows repaired to:
  - `CONCAT_CHAPTER -> completed`
  - `UPLOAD_ARTIFACTS -> completed`

Important nuance:

- the final mp4 currently exists but is `root:root` on disk
- this does not block the proof chapter from being completed
- to prevent recurrence, updated `fk_worker/media.py` was synced to both live
  worker roots after this incident

Current strongest proof now available:

- lane-02:
  - previously completed a full smoke chapter end-to-end
- lane-01:
  - now also completed a control-routed smoke chapter end-to-end

This means both real lanes on the same VM lab have now been proven with
meaningful end-to-end work, not only connect-only or create-only steps.

### Final lane-02 control-routed completion state

The earlier lane-02 control smoke chapter was later pushed through the same
remaining stages and repaired to completion as well:

- chapter:
  - `383145d8-7fdf-47bb-af29-f4a967ce9f95`
- project:
  - `791c0c5d-48e9-4026-b460-b2f4f25e63e9`
- local Flow project id:
  - `c1f4a660-13fb-4d55-8c26-e354bf87876f`

Control-routed stages now proven on lane-02 for that chapter:

- `CREATE_PROJECT`
- `CREATE_ENTITIES`
- `CREATE_VIDEO`
- `CREATE_SCENES`
- `GEN_REFS`
- `GEN_IMAGES`
- `GEN_VIDEOS`
- `CONCAT_CHAPTER`
- `UPLOAD_ARTIFACTS`

Live final outputs:

- final chapter file:
  - `/home/hth2/flowkit-worker-demo-lane-02/runtime/output/control_create_only_smoke_2026_04_22_chapter_01/control_create_only_smoke_2026_04_22_chapter_01_final.mp4`
- artifact rows exist:
  - `chapter_final`
  - `manifest`

Important nuance:

- lane-02 initially hit the same UUID-serialization bookkeeping bug seen on
  lane-01 for:
  - `CONCAT_CHAPTER`
  - `UPLOAD_ARTIFACTS`
- this happened because the live runner process had not yet reloaded the synced
  code fix
- after repairing DB state, both lane runners were restarted so the live
  processes now run the fixed worker code

### Current end-of-session truth

Control `/overview` now shows:

- `lane-01.status=idle`
- `lane-02.status=idle`
- `chapter_status_counts.completed=3`
- the completed chapters of interest are:
  - lane-01 control-routed smoke:
    - `2d203365-f19c-47f1-b7ea-ddf20674df46`
  - lane-02 control-routed smoke:
    - `383145d8-7fdf-47bb-af29-f4a967ce9f95`
  - earlier lane-02 full smoke:
    - `18f6fb64-98ec-4d54-8ed9-64dcd5de1b43`

Strongest final interpretation:

- same-VM dual-lane lab on `hth2-box` is now proven not only structurally
- both real lanes have completed meaningful control-routed end-to-end chapter
  work
- the remaining failed chapter is historical and not the active blocking state

### Current smoke result

New smoke project after reconnect:

- title: `Lane 02 Single Chapter Smoke 2026-04-22 09-02`
- project id: `9e134864-af02-47c9-9b6b-cdabbf67bb14`
- chapter id: `18f6fb64-98ec-4d54-8ed9-64dcd5de1b43`
- chapter slug: `lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01`

Observed result:

- chapter assigned to `lane-02`
- `CREATE_PROJECT` completed successfully on first attempt
- chapter received:
  - `local_flow_project_id=5024576b-4a6b-45fb-9f41-bd634fde6dda`
- `CREATE_ENTITIES` completed
- `CREATE_VIDEO` completed
- `CREATE_SCENES` completed
- `GEN_REFS` completed
- `GEN_IMAGES` completed
- `GEN_VIDEOS` completed
- later failure was no longer extension/account related
- failure moved to:
  - `CONCAT_CHAPTER`
  - error:
    - `Permission denied` under `/home/hth2/flowkit-worker-demo-lane-02/runtime/output/.../4k/...mp4`

### Credit-saving stop point

User requested short smoke only, not a full paid run.

Actions taken:

- lane-02 runner was stopped intentionally after the short proof run
- control scheduler was also stopped intentionally
- local tunnel / extension wiring can be re-used next session

State at stop time:

- `fk_worker.runner` stopped
- `fk_control.scheduler` stopped
- `18182/ready` no longer serving because the runner was intentionally shut down
- chapter `18f6fb64-98ec-4d54-8ed9-64dcd5de1b43` ended `failed`
- proof already achieved before stop:
  - second account connected
  - real lane-02 got the chapter
  - real Flow project was created
  - lane-02 progressed through media-generation stages

### Post-stop debugging findings

- the first `CONCAT_CHAPTER` failure was confirmed to be a real host-permission bug:
  - chapter output dir was created as `root:root`
  - path:
    - `/home/hth2/flowkit-worker-demo-lane-02/runtime/output/lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01`
- root cause:
  - `flowkit-lane-02-agent` container was running with empty Docker `Config.User`
  - this wrote runtime output as root on the bind mount
- live VM mitigation applied:
  - `flowkit-lane-02-agent` was recreated with:
    - `--user 1000:1000`
  - lane-02 runtime ownership was repaired back to `hth2:hth2`
  - `8110/health` still worked after recreation
- live lane-02 root was also synced with the updated worker kit pieces:
  - `docker-compose.worker.yml`
  - `Dockerfile.worker`
  - `lane.env.example`
  - `scripts/bootstrap-lane.sh`
  - `fk_worker/stages.py`
- live `env/lane.env` now includes:
  - `FLOWKIT_UID=1000`
  - `FLOWKIT_GID=1000`
- after the permission fix, rerunning `CONCAT_CHAPTER` no longer failed on file ownership
- the next real bug found was logical, not infra:
  - one scene had:
    - `vertical_video_status=FAILED`
    - `vertical_video_url=null`
  - scene id:
    - `77dadaa7-f396-432f-b80a-e3ea1d1a4be4`
  - failed request row:
    - request id row: `1ec80191-b1b6-49ec-8b29-12bf693b7fed`
    - Flow operation id: `ed972a10f55c34b355cf781539528b64`
    - stored error before agent patch:
      - `Operation failed: ed972a10f55c34b355cf781539528b64`
  - batch status for `GENERATE_VIDEO` on that video at last inspection:
    - `total=15`
    - `completed=14`
    - `failed=1`
    - `all_succeeded=false`
  - because worker stage logic only trusted batch request completion, the pipeline had incorrectly advanced beyond `GEN_VIDEOS`
- repo fix now added:
  - worker compose runs containers as host UID:GID
  - `GEN_IMAGES` / `GEN_VIDEOS` / `UPSCALE` now fail fast when request status or final scene output is not actually ready
  - agent SDK poller now extracts richer operation error text when Flow returns structured error details
- important:
  - repo fix was made locally in this repo
  - agent error-detail patch was also copied into the live `flowkit-lane-02-agent` container and the container was restarted
  - lane-02 runner and scheduler were intentionally left stopped after smoke to avoid further credit usage
  - after a later clean restart of `flowkit-lane-02-agent`, the previous startup warning:
    - `Failed to load custom materials: attempt to write a readonly database`
    - did not reappear
  - zero-credit DB write probe succeeded on live lane-02 agent:
    - `POST /api/materials` created `lane_02_probe_material`
    - `DELETE /api/materials/lane_02_probe_material` succeeded
  - interpretation:
    - current agent DB write path is healthy after the ownership/user fix
  - one controlled low-cost retry was later allowed for the single failed scene only:
    - request row reset from `FAILED` back to `PENDING`
    - because `retry_count` was already `4` and `MAX_RETRIES=5`, this effectively allowed one final attempt
    - the retry succeeded
    - scene `77dadaa7-f396-432f-b80a-e3ea1d1a4be4` now has:
      - `vertical_video_status=COMPLETED`
      - `vertical_video_media_id=7cd1c47b-539c-4e89-9919-00452c7f87e6`
  - after that retry:
    - `GENERATE_VIDEO` batch status became:
      - `total=15`
      - `completed=15`
      - `failed=0`
      - `all_succeeded=true`
  - local zero-credit replay of `CONCAT_CHAPTER` and `UPLOAD_ARTIFACTS` was then run directly on VM
  - chapter is now `completed` in control DB:
    - `chapter_output_uri=/home/hth2/flowkit-worker-demo-lane-02/runtime/output/lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01/lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01_final.mp4`
  - artifact rows now exist for that chapter:
    - `chapter_final`
    - `manifest`
    - both stored via local fallback `file://...`
  - control-job consistency was repaired after the direct replay:
    - `CONCAT_CHAPTER` job `26882d73-25d7-4d1e-8e13-d23a76bb86ed` is now `completed`
    - `UPLOAD_ARTIFACTS` job `3c0d1819-fcc6-4db7-aa95-cc853f7f4f3a` is now `completed`
  - chapter metadata was also cleaned up:
    - `failed_job_type=null`
    - `last_error_text=null`
    - `repair_note='completed via direct local replay after single-scene retry'`
  - another small code bug was found during that replay and fixed locally in repo:
    - `fk_worker.storage.update_chapter_state()` had been missing `chapter_output_uri`
- another ownership issue was also found and fixed locally in repo:
  - `fk_worker.media` used `docker run` without `--user`, so `norm/*.mp4` and final concat outputs were still root-owned
  - repo patch now passes `FLOWKIT_UID:GID` into media helper Docker commands
  - existing files from the completed smoke chapter were chowned back to `hth2:hth2`
  - bootstrap kit was improved again:
    - `bootstrap-lane.sh` now supports optional `APP_SOURCE=/path/to/flowkit/repo`
    - when provided, bootstrap copies app source straight into `DEPLOY_ROOT/app`
    - this avoids leaving new lane roots with an empty `app/` directory

### Current VM state

- lane-02 worker root exists:
  - `/home/hth2/flowkit-worker-demo-lane-02`
- lane-02 env is prepared for:
  - API `8110`
  - WS `9232`
  - runner health `18182`
- second agent container is running:
  - container name: `flowkit-lane-02-agent`
- lane-02 agent health:
  - `http://127.0.0.1:8110/health`
  - reachable
  - `extension_connected=false`
- lane-02 runner health:
  - `http://127.0.0.1:18182/health`
  - reachable
  - `ready` still `503` because API is reachable but extension/token is not
- control services:
  - `fk_control.api` running on `18080`
  - `fk_control.scheduler` running
- demo Postgres/Redis stack is up via:
  - `control-postgres-1`
  - `control-redis-1`

### Control-plane state

- `seed-lanes.sql` was applied
- control overview now shows:
  - `lane_count=10`
  - `offline=9`
  - `idle=1`
- only `lane-02` is left `idle`
- other lanes are forced `offline` so the smoke project pins to `lane-02`

### Smoke run already exercised

Smoke project:

- title: `Lane 02 Single Chapter Smoke`
- project id: `6be54715-db27-4280-86c3-e3af1be814dd`
- chapter id: `b70c9bf7-45d0-4b87-a98e-5e08e36d6ca8`

Observed result:

- chapter assigned to `lane-02`
- `CREATE_PROJECT` job was actually attempted on `lane-02`
- `CREATE_PROJECT` failed after retries with:
  - `POST /api/projects failed: Extension not connected — cannot create project on Google Flow`
- downstream jobs were marked dead because the chapter failed at the first real stage

This proves:

- control scheduler is routing into `lane:02:jobs`
- lane-02 runner is alive and consuming
- lane-02 agent on `8110` is reachable
- remaining blocker is the local lane-02 browser/account handshake, not the same-VM worker layout

## Current repo state

Important local changes already made in repo:

- control-plane scaffold + tests
- worker scaffold + tests
- dashboard queue cleanup
- worker Docker-media fallback for `ffmpeg/ffprobe`
- local artifact fallback for upload
- clearer Flow create-project error handling

Relevant files:

- `docs/deployment-kit/control/fk_control/dashboard.py`
- `docs/deployment-kit/control/fk_control/planning.py`
- `docs/deployment-kit/control/fk_control/scheduler.py`
- `docs/deployment-kit/control/fk_control/storage.py`
- `docs/deployment-kit/control/scripts/*.sh`
- `docs/deployment-kit/worker/fk_worker/client.py`
- `docs/deployment-kit/worker/fk_worker/config.py`
- `docs/deployment-kit/worker/fk_worker/media.py`
- `docs/deployment-kit/worker/fk_worker/runner.py`
- `docs/deployment-kit/worker/fk_worker/stages.py`
- `docs/deployment-kit/worker/scripts/*.sh`
- `agent/api/projects.py`

Repo working tree note:

- `agent/api/projects.py` is modified
- `tests/unit/test_projects_api.py` is untracked
- most `docs/deployment-kit/` content is still untracked

## Current VM state on `hth2-box`

### Disk / RAM

- root filesystem already expanded from ~24G to ~48G
- current root free space is healthy again
- OpenClaw and related images/volumes were removed

### Running services now

At last check:

- `flowkit` Coolify runtime container is up
- `coolify` core containers are up
- demo `fk_control.api` is currently **down**
- demo `fk_control.scheduler` is currently **down**
- demo `lane-01` worker runner is currently **down**

Health snapshot at last check:

- `http://127.0.0.1:8100/health` → `extension_connected=false`
- `http://127.0.0.1:8100/api/flow/status` → `connected=false`, `flow_key_present=true`
- `http://127.0.0.1:18080/health` → refused
- `http://127.0.0.1:18181/health` → refused

Interpretation:

- FlowKit agent is up on VM
- browser extension is not currently connected because the local Chrome/tunnel session is not currently active
- demo control/worker host processes need restart before continuing

## What was proven already

### Lane-01 full pipeline

One real chapter was completed end-to-end on `lane-01`:

- `CREATE_PROJECT`
- `CREATE_ENTITIES`
- `CREATE_VIDEO`
- `CREATE_SCENES`
- `GEN_REFS`
- `GEN_IMAGES`
- `GEN_VIDEOS`
- `CONCAT_CHAPTER`
- `UPLOAD_ARTIFACTS`

The upload path used local fallback, not real R2.

Chapter:

- `Lane 01 Single Chapter v12`

Final file:

- `/home/hth2/flowkit-worker-demo/runtime/output/lane_01_single_chapter_v12_chapter_01/lane_01_single_chapter_v12_final_reencode.mp4`

Artifact DB record points to:

- `file:///home/hth2/flowkit-worker-demo/runtime/output/lane_01_single_chapter_v12_chapter_01/lane_01_single_chapter_v12_final_reencode.mp4`

### Dashboard cleanup

- `/overview` raw queues are clean after `clean-queue-history.sh`
- dashboard default queue view hides zero-depth noise

## Hard blockers for 2 lanes on the same VM

### 1. Extension is hardcoded to lane-01 ports

Current extension uses fixed endpoints:

- WS: `ws://127.0.0.1:9222`
- callback HTTP: `http://127.0.0.1:8100/api/ext/callback`
- manifest host permission includes `http://127.0.0.1:8100/*`

Files:

- `extension/background.js`
- `extension/manifest.json`

Implication:

- to run lane-02 on the same machine, a second extension copy or parameterized extension config is required

### 2. Current local browser setup only represents one account/profile

Known local profile path:

- `C:\temp\flowkit-real-chrome\UserData`

Known unpacked extension path:

- `C:\temp\flowkit-extension-unpacked`

Implication:

- lane-02 needs a second Chrome profile and second Google account session

### 3. Current app/runtime design is single-lane by default

To make same-VM dual lane real, lane-02 needs:

- separate `FLOW_AGENT_DIR`
- separate API/WS ports
- separate worker health port
- separate worker root/output/logs

## Recommended implementation plan for next session

### Preferred same-VM lane-02 shape

Keep lane-01 unchanged.

Add lane-02 with:

- API: `127.0.0.1:8110`
- WS: `127.0.0.1:9232`
- runner health: `127.0.0.1:18182`
- worker root: `/home/hth2/flowkit-worker-demo-lane-02`
- runtime dir: `/home/hth2/flowkit-worker-demo-lane-02/runtime`
- profile dir on local Windows:
  - `C:\temp\flowkit-real-chrome-lane-02\UserData`
- extension dir on local Windows:
  - `C:\temp\flowkit-extension-unpacked-lane-02`

### Recommended technical moves

1. Parameterize extension endpoints or create a lane-02 extension copy
2. Add lane-02 worker env and scripts
3. Add lane-02 host-process runner on VM
4. Add second local SSH tunnel:
   - `8110 -> 8110`
   - `9232 -> 9232`
5. Launch second Chrome profile with second extension + second Google account
6. Seed/control-test a single-chapter project pinned to lane-02

## Lowest-cost next action now

If the next session is still minimizing credit burn, do **not** restart the full scheduler pipeline first.

Retry only the one failed scene directly through the already-connected lane-02 agent:

- scene id:
  - `77dadaa7-f396-432f-b80a-e3ea1d1a4be4`
- project id:
  - `5024576b-4a6b-45fb-9f41-bd634fde6dda`
- video id:
  - `d16cdceb-934b-41b3-9dd5-8b94a2e73242`

Suggested direct request:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8110/api/requests `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"type":"GENERATE_VIDEO","orientation":"VERTICAL","scene_id":"77dadaa7-f396-432f-b80a-e3ea1d1a4be4","project_id":"5024576b-4a6b-45fb-9f41-bd634fde6dda","video_id":"d16cdceb-934b-41b3-9dd5-8b94a2e73242"}'
```

Then inspect only:

- `GET /api/requests?scene_id=77dadaa7-f396-432f-b80a-e3ea1d1a4be4`
- `GET /api/requests/batch-status?video_id=d16cdceb-934b-41b3-9dd5-8b94a2e73242&type=GENERATE_VIDEO&orientation=VERTICAL`
- `GET /api/scenes?video_id=d16cdceb-934b-41b3-9dd5-8b94a2e73242`

Why this is the cheapest meaningful retry:

- it spends at most one scene-video retry, not a whole chapter rerun
- it bypasses control scheduler and lane-runner
- it should now surface a clearer upstream error message because the live agent poller was patched

## Exact next-session prompt

Use this in the next Codex session:

```text
Continue in repo F:\\vm201 Coolify\\flowkit.

Read first:
- F:\\vm201 Coolify\\flowkit\\README.md
- F:\\vm201 Coolify\\flowkit\\docs\\10-lane-production-blueprint.md
- F:\\vm201 Coolify\\flowkit\\docs\\deployment-kit\\two-lane-same-vm-hth2-box-handoff.md

Goal:
- implement 2 real lanes on the same VM hth2-box
- keep lane-01 as-is on 8100/9222
- add lane-02 on 8110/9232
- do NOT fake multi-lane by reusing one profile/account/runtime

Current facts to respect:
- lane-01 already proved end-to-end with local artifact fallback
- control/dashboard cleanup is already done
- current VM root is 48G with healthy free space
- control API, scheduler, and lane-01 runner are currently down and may need restart
- current agent on VM is still on 8100/9222
- extension is hardcoded to 8100/9222 in extension/background.js and extension/manifest.json
- current local profile is C:\\temp\\flowkit-real-chrome\\UserData
- current local extension is C:\\temp\\flowkit-extension-unpacked

Required implementation direction:
1. Create a proper lane-02 runtime/worker layout:
   - /home/hth2/flowkit-worker-demo-lane-02
   - API 8110
   - WS 9232
   - health 18182
2. Add a lane-02 extension strategy:
   - either parameterize the extension endpoints cleanly
   - or generate a second unpacked extension copy for lane-02
3. Add second local Chrome profile guidance/launch command for lane-02
4. Add second SSH tunnel command for lane-02
5. Restart/verify control API + scheduler + lane-01 if needed
6. Bring up lane-02 worker and prove a single chapter can at least reach CREATE_PROJECT with the second account

Important:
- use TDD for code changes where practical
- verify with commands, don’t just assume
- keep /overview raw contract stable unless absolutely necessary
- preserve lane-01 working path

Target success for this session:
- lane-02 runtime and worker are actually launchable
- local lane-02 browser/extension wiring is ready
- one single-chapter run assigned to lane-02 is exercised
```

## Recommended first commands next session

On VM:

- check/restart:
  - `/home/hth2/flowkit-control-demo/start-control-api.sh`
  - `/home/hth2/flowkit-control-demo/start-scheduler.sh`
- check lane-01 runner:
  - `/home/hth2/flowkit-worker-demo/scripts/run-worker-demo.sh`

On Windows:

- restore lane-01 tunnel if needed:
  - `ssh -N -L 8100:127.0.0.1:8100 -L 9222:127.0.0.1:9222 hth2-box`
- plan second tunnel:
  - `ssh -N -L 8110:127.0.0.1:8110 -L 9232:127.0.0.1:9232 hth2-box`

## Notes

- If same-VM two-lane starts getting messy, stop and explicitly compare:
  - same VM dual lane
  - second VM for lane-02
- But the requested direction for next session is to pursue same-VM lane-02 first.

## April 23, 2026 update: R2 upload is now proven

This update supersedes the older "next session" prompt above for storage proof.

### What was proved

A zero-credit live replay of the real worker upload stage was run directly on
`hth2-box` for the already-completed control-routed `lane-02` chapter:

- project id:
  - `791c0c5d-48e9-4026-b460-b2f4f25e63e9`
- chapter id:
  - `383145d8-7fdf-47bb-af29-f4a967ce9f95`
- output root:
  - `/home/hth2/flowkit-worker-demo-lane-02/runtime/output/control_create_only_smoke_2026_04_22_chapter_01`

Replay specifics:

- lane env loaded from:
  - `/home/hth2/flowkit-worker-demo-lane-02/env/lane.env`
- live worker code loaded from:
  - `/home/hth2/flowkit-worker-demo-lane-02/fk_worker`
- temporary proof override:
  - `ALLOW_LOCAL_ARTIFACT_FALLBACK=0`
- actual stage invoked:
  - `handle_upload_artifacts()`

Observed result:

- stage finished:
  - `status=completed`
  - `upload_mode=r2`
- uploaded URIs:
  - `s3://dgt-audio/projects/791c0c5d_48e9_4026_b460_b2f4f25e63e9/control_create_only_smoke_2026_04_22_chapter_01/final.mp4`
  - `s3://dgt-audio/projects/791c0c5d_48e9_4026_b460_b2f4f25e63e9/control_create_only_smoke_2026_04_22_chapter_01/meta.json`
- artifact count for that chapter moved:
  - `2 -> 4`
- newest artifact rows are now:
  - `chapter_final` with `upload_mode=r2`
  - `manifest` with `upload_mode=r2`
- previous `local_fallback` artifact rows remain as historical rows:
  - `chapter_final`
  - `manifest`

Direct R2 verification also passed:

- `head_object` on `final.mp4` returned:
  - `content_length=4907033`
  - `content_type=video/mp4`
- `head_object` on `meta.json` returned:
  - `content_length=372`
  - `content_type=application/json`

### Interpretation

- real object storage write path is now proven on live worker code with live
  lane env
- no Google Flow credit was spent for this proof
- no local Chrome profile, SSH tunnel, control API, scheduler, or runner
  restart was required
- `R2_PUBLIC_BASE` is still blank, so storage URIs remain `s3://...`, not
  public HTTP URLs

### Lowest-cost next action now

If the goal remains minimizing credit burn:

- keep the lab parked
- do **not** restart scheduler/control just to re-prove storage
- treat R2 upload proof as complete

Only optional follow-up work remains:

1. Set and verify `R2_PUBLIC_BASE` if public artifact URLs are needed.
2. Decide whether to keep or prune older `local_fallback` artifact rows for
   chapters later re-uploaded to R2.
3. Otherwise stop here; same-VM dual lane plus R2 upload proof is already in a
   good end state for this lab.

## April 23, 2026 update: live bucket switched from `dgt-audio` to `veo3`

The earlier `dgt-audio` choice was only a temporary live workaround while
checking which bucket the provided S3 credentials could actually access.

Later verification on the live VM showed:

- `HeadBucket(veo3)` succeeds
- `HeadBucket(flowkit-output)` still fails with not-found
- `CreateBucket(flowkit-output)` still fails with access denied

To separate this project from the temporary `dgt-audio` bucket:

- `/home/hth2/flowkit-worker-demo/env/lane.env` was updated to:
  - `R2_BUCKET=veo3`
- `/home/hth2/flowkit-worker-demo-lane-02/env/lane.env` was updated to:
  - `R2_BUCKET=veo3`

Zero-credit replay proof was then run again on the same completed `lane-02`
chapter:

- chapter id:
  - `383145d8-7fdf-47bb-af29-f4a967ce9f95`
- replay still forced:
  - `ALLOW_LOCAL_ARTIFACT_FALLBACK=0`

Observed result:

- uploaded URIs now also exist under:
  - `s3://veo3/projects/791c0c5d_48e9_4026_b460_b2f4f25e63e9/control_create_only_smoke_2026_04_22_chapter_01/final.mp4`
  - `s3://veo3/projects/791c0c5d_48e9_4026_b460_b2f4f25e63e9/control_create_only_smoke_2026_04_22_chapter_01/meta.json`
- artifact count for that chapter moved:
  - `4 -> 6`
- newest artifact rows are now:
  - `chapter_final` with `storage_uri` in `veo3`
  - `manifest` with `storage_uri` in `veo3`
- direct `head_object` verification passed for both uploaded objects in
  `veo3`

Current interpretation:

- live bucket for this lab should now be treated as:
  - `veo3`
- older historical artifact rows under:
  - `file://...`
  - `s3://dgt-audio/...`
  still remain in the DB for the same chapter
- newest successful live object-storage proof now points at:
  - `s3://veo3/...`

## April 23, 2026 cleanup: stale artifact history removed for test chapter

The user approved cleanup for the test chapter artifact history after the move
to `veo3`.

Target chapter:

- chapter id:
  - `383145d8-7fdf-47bb-af29-f4a967ce9f95`

Cleanup actions completed:

- deleted 4 stale artifact DB rows for that chapter:
  - 2 rows with `storage_uri=file://...`
  - 2 rows with `storage_uri=s3://dgt-audio/...`
- deleted the 2 old `dgt-audio` objects for that chapter:
  - `final.mp4`
  - `meta.json`
- kept the local files on VM in place
- kept the newest `veo3` artifact rows in place

Post-cleanup verification:

- artifact row count for that chapter moved:
  - `6 -> 2`
- remaining rows are only:
  - `chapter_final` -> `s3://veo3/.../final.mp4`
  - `manifest` -> `s3://veo3/.../meta.json`
- direct `head_object` verification still passes for both remaining `veo3`
  objects
- direct `head_object` verification on the deleted `dgt-audio` objects now
  returns not found

Current end state for that chapter:

- DB history is clean
- live storage source of truth is `veo3`
- no stale `file://...` or `s3://dgt-audio/...` rows remain for that chapter

## April 23, 2026 cleanup: remaining stale artifact rows were migrated and removed

After the first cleanup, two older completed test chapters still had
`file://...` artifact rows and no `veo3` replacement yet:

1. `2d203365-f19c-47f1-b7ea-ddf20674df46`
   - `control_create_only_smoke_lane_01_2026_04_22_chapter_01`
2. `18f6fb64-98ec-4d54-8ed9-64dcd5de1b43`
   - `lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01`

Both chapters were handled with zero-credit direct replay using live worker code
and current lane env, again forcing:

- `ALLOW_LOCAL_ARTIFACT_FALLBACK=0`

Observed upload results:

- chapter `2d203365-f19c-47f1-b7ea-ddf20674df46`
  - uploaded `chapter_final` into:
    - `s3://veo3/projects/9765a16e_f869_4142_abda_53e85996a15e/control_create_only_smoke_lane_01_2026_04_22_chapter_01/final.mp4`
- chapter `18f6fb64-98ec-4d54-8ed9-64dcd5de1b43`
  - uploaded `chapter_final` into:
    - `s3://veo3/projects/9e134864_af02_47c9_9b6b_cdabbf67bb14/lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01/final.mp4`
  - uploaded `manifest` into:
    - `s3://veo3/projects/9e134864_af02_47c9_9b6b_cdabbf67bb14/lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01/meta.json`

Cleanup results:

- for chapter `2d203365-f19c-47f1-b7ea-ddf20674df46`
  - deleted 1 stale `file://...` row
  - remaining artifact rows:
    - 1 `veo3` row
- for chapter `18f6fb64-98ec-4d54-8ed9-64dcd5de1b43`
  - deleted 2 stale `file://...` rows
  - remaining artifact rows:
    - 2 `veo3` rows

Post-cleanup verification:

- chapter metadata for both chapters now reports:
  - `upload_mode=r2`
  - `uploaded_uris` pointing at `s3://veo3/...`
- direct `head_object` verification passed for all remaining `veo3` objects
- final global control-DB scan returned:
  - no remaining artifact rows with:
    - `storage_uri like 'file://%'`
    - `storage_uri like 's3://dgt-audio/%'`

Current storage end state:

- live bucket for this lab is `veo3`
- control DB no longer contains stale artifact rows pointing at:
  - `file://...`
  - `s3://dgt-audio/...`

## April 23, 2026 update: public HTTP artifact URLs are now live

The next follow-up goal was to stop returning `s3://...` URIs and move artifact
rows to public HTTP URLs.

### Public bucket access

Bucket:

- `veo3`

Managed public domain:

- `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev`

What happened:

- Cloudflare MCP could read bucket domain state but failed on the write step with
  authentication error
- local `wrangler` CLI was then used with:
  - `CLOUDFLARE_ACCOUNT_ID=75adc0ed2db47e1731c8f6105492cc0b`
- `wrangler r2 bucket dev-url enable veo3` succeeded
- direct public HTTP checks then returned `200` for existing `veo3` objects

### Live env updates

Both live worker env files were updated to include:

- `R2_PUBLIC_BASE=https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev`

Updated files:

- `/home/hth2/flowkit-worker-demo/env/lane.env`
- `/home/hth2/flowkit-worker-demo-lane-02/env/lane.env`

### Important live sync note

The repo already had `R2_PUBLIC_BASE` support, but the live worker roots on VM
were still on an older copy of:

- `fk_worker/config.py`
- `fk_worker/upload.py`

Those files were synced from the repo deployment kit into both live worker
roots:

- `/home/hth2/flowkit-worker-demo/fk_worker/`
- `/home/hth2/flowkit-worker-demo-lane-02/fk_worker/`

This was required so live worker uploads would actually emit HTTP URLs instead
of `s3://...`.

### Zero-credit migration to public URLs

Three completed test chapters were normalized from `s3://veo3/...` into public
HTTP URLs:

1. `2d203365-f19c-47f1-b7ea-ddf20674df46`
   - `control_create_only_smoke_lane_01_2026_04_22_chapter_01`
2. `18f6fb64-98ec-4d54-8ed9-64dcd5de1b43`
   - `lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01`
3. `383145d8-7fdf-47bb-af29-f4a967ce9f95`
   - `control_create_only_smoke_2026_04_22_chapter_01`

Migration method:

- zero-credit direct replay via `handle_upload_artifacts()`
- forced:
  - `ALLOW_LOCAL_ARTIFACT_FALLBACK=0`
- then deleted stale `s3://veo3/...` rows for the same chapters after public
  URL verification passed

Observed result:

- lane-01 chapter now remains as:
  - `chapter_final -> https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/9765a16e_f869_4142_abda_53e85996a15e/control_create_only_smoke_lane_01_2026_04_22_chapter_01/final.mp4`
- lane-02 older smoke chapter now remains as:
  - `chapter_final -> https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/9e134864_af02_47c9_9b6b_cdabbf67bb14/lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01/final.mp4`
  - `manifest -> https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/9e134864_af02_47c9_9b6b_cdabbf67bb14/lane_02_single_chapter_smoke_2026_04_22_09_02_chapter_01/meta.json`
- lane-02 control-routed chapter now remains as:
  - `chapter_final -> https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/791c0c5d_48e9_4026_b460_b2f4f25e63e9/control_create_only_smoke_2026_04_22_chapter_01/final.mp4`
  - `manifest -> https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/791c0c5d_48e9_4026_b460_b2f4f25e63e9/control_create_only_smoke_2026_04_22_chapter_01/meta.json`

### Final verification

Final control-DB scan returned:

- no remaining artifact rows with:
  - `storage_uri like 'file://%'`
  - `storage_uri like 's3://dgt-audio/%'`
  - `storage_uri like 's3://veo3/%'`

Artifact rows now present for the migrated test chapters are:

- public `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/...` URLs only

Current end state:

- live bucket remains `veo3`
- public `r2.dev` access is enabled
- live worker envs include `R2_PUBLIC_BASE`
- migrated test chapter artifact rows now use public HTTP URLs, not `s3://...`

## April 23, 2026 proof: new fresh run now stores public HTTP URLs directly

After the public URL cutover, one brand-new low-cost control-routed run was
executed to prove that a fresh chapter now lands directly on public HTTP
artifact URLs without any replay or artifact migration step.

Created via control API:

- project id:
  - `4e316049-d093-48f4-b260-8cfd589f4e3d`
- chapter id:
  - `1b9776bd-3427-4ae4-b85f-0022a9a5e2cf`
- title:
  - `Public HTTP Fresh Smoke 2026-04-23 10-22`
- target shape:
  - `1 chapter`
  - `8 seconds`
  - `1 scene`

Observed scheduler behavior:

- control scheduler selected:
  - `lane-02`
- lane state moved:
  - `idle -> busy -> idle`

Observed stage progression:

- `CREATE_PROJECT -> completed`
- `CREATE_ENTITIES -> completed`
- `CREATE_VIDEO -> completed`
- `CREATE_SCENES -> completed`
- `GEN_REFS -> completed`
- `GEN_IMAGES -> completed`
- `GEN_VIDEOS -> completed`
- `CONCAT_CHAPTER -> completed`
- `UPLOAD_ARTIFACTS -> completed`

Observed chapter result:

- final chapter status:
  - `completed`
- final local output:
  - `/home/hth2/flowkit-worker-demo-lane-02/runtime/output/public_http_fresh_smoke_2026_04_23_10_22_chapter_01/public_http_fresh_smoke_2026_04_23_10_22_chapter_01_final.mp4`
- chapter metadata now includes:
  - `upload_mode=r2`
  - `uploaded_uris` pointing directly at public `https://...` URLs

Artifact rows created for the fresh chapter:

- `chapter_final`
  - `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/4e316049_d093_48f4_b260_8cfd589f4e3d/public_http_fresh_smoke_2026_04_23_10_22_chapter_01/final.mp4`
- `manifest`
  - `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/4e316049_d093_48f4_b260_8cfd589f4e3d/public_http_fresh_smoke_2026_04_23_10_22_chapter_01/meta.json`

Direct public verification passed:

- `final.mp4`
  - `HTTP 200`
  - `content-type=video/mp4`
  - `content-length=3354090`
- `meta.json`
  - `HTTP 200`
  - `content-type=application/json`
  - `content-length=380`

Meaning:

- the system is now proven beyond replay/migration cleanup
- a brand-new control-routed chapter can finish and write public HTTP artifact
  URLs directly on first completion
- no artifact post-fix was needed for this fresh chapter

Post-proof ops step:

- local Windows lab was parked again
- remote VM control API, scheduler, and lane runners were parked again
- lab end state after proof is intentionally back to parked to avoid further
  credit spend

## April 23, 2026 tooling update: one-command fresh smoke helper now exists

To avoid repeating manual API + DB polling steps, a new control helper was added
to the repo:

- `docs/deployment-kit/control/scripts/public-http-fresh-smoke.sh`

Purpose:

- create a tiny `1 chapter / 8 seconds / 1 scene` control-routed project
- poll via control DB until the chapter reaches `completed` or `failed`
- print the final artifact URLs

Important current contract:

- requires `POSTGRES_DSN`
- respects `CONTROL_PROFILE_FILE` for `CONTROL_API_URL`
- supports `DRY_RUN=1`

Live proof on `hth2-box`:

- the helper script was copied to:
  - `/home/hth2/flowkit-control-demo/control/scripts/public-http-fresh-smoke.sh`
- it was executed on the VM with:
  - `CONTROL_PROFILE_FILE=/home/hth2/flowkit-control-demo/control/host-demo.env`
  - `POSTGRES_DSN` loaded from lane env

Observed result:

- helper-created project id:
  - `319e34d6-f726-40b7-bb34-730be249c449`
- helper-created chapter id:
  - `81359efb-246b-4c98-b7b9-e1cea2b16dca`
- chapter completed successfully
- all chapter jobs completed
- returned artifact URLs were public HTTP URLs:
  - `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/319e34d6_f726_40b7_bb34_730be249c449/fresh_smoke_helper_2026_04_23_11_02_chapter_01/final.mp4`
  - `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/319e34d6_f726_40b7_bb34_730be249c449/fresh_smoke_helper_2026_04_23_11_02_chapter_01/meta.json`

Meaning:

- the fresh public-HTTP proof is now available as a reusable script, not only as
  an ad-hoc operator sequence

## April 23, 2026 tooling update: one-command local proof wrapper now exists

To avoid even the local multi-step orchestration, one more wrapper was added on
the Windows side:

- `docs/deployment-kit/control/scripts/public-http-proof.ps1`

Purpose:

- start local Windows lab
- start remote VM lab
- wait until remote control plus both lanes are actually ready
- execute the remote `public-http-fresh-smoke.sh`
- park both local and remote sides again in `finally`

Important current contract:

- action defaults to:
  - `run`
- also supports:
  - `status`
- useful environment overrides:
  - `LOCAL_LAB_SCRIPT`
  - `SSH_EXE`
  - `REMOTE_HOST`
  - `REMOTE_CONTROL_ROOT`
  - `REMOTE_CONTROL_PROFILE`
  - `REMOTE_LANE_ENV`
  - `WAIT_FOR_READY`

Live proof from the local Windows machine:

- wrapper was run directly from the repo
- it completed successfully end-to-end
- helper-created project id:
  - `375482ec-0d03-4685-89a8-70b989e3a449`
- helper-created chapter id:
  - `4be9ff20-7e58-44de-82aa-6ea894a58463`
- all chapter jobs completed
- returned artifact URLs were public HTTP URLs:
  - `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/375482ec_0d03_4685_89a8_70b989e3a449/public_http_fresh_smoke_chapter_01/final.mp4`
  - `https://pub-21eb0ffd95134c5a9fda96c012571194.r2.dev/projects/375482ec_0d03_4685_89a8_70b989e3a449/public_http_fresh_smoke_chapter_01/meta.json`

Post-proof verification:

- local wrapper status after completion returned:
  - no tunnels running
  - no Chrome profiles running
- remote wrapper status after completion returned:
  - control API stopped
  - scheduler stopped
  - lane runners stopped

Meaning:

- the entire same-VM public HTTP proof path is now scriptable from the local
  Windows machine with one command

## April 23, 2026 tooling update: operator quick reference + timestamped smoke titles

One more low-risk ops-hardening pass was added after the public-HTTP proof
wrappers were already in place.

Updated docs:

- `docs/deployment-kit/README.md`
  - now includes a short operator quick reference for the 3 most important
    commands:
    - live worker-kit sync
    - remote public-HTTP fresh smoke
    - local one-command public-HTTP proof wrapper

Updated scripts:

- `docs/deployment-kit/control/scripts/public-http-fresh-smoke.sh`
- `docs/deployment-kit/control/scripts/public-http-proof.ps1`

Current behavior change:

- if `SOURCE_TITLE` is not provided, both smoke helpers now auto-generate a
  timestamped default title
- wrapper default shape:
  - `Public HTTP Wrapper Smoke YYYY-MM-DD HH-MM-SS`
- remote helper default shape:
  - `Public HTTP Fresh Smoke YYYY-MM-DD HH-MM-SS`

Why this matters:

- repeated smoke runs no longer depend on the operator remembering to provide a
  unique title
- this reduces accidental title collisions during repeated low-cost proof runs
- the quick reference makes the current same-VM lab workflow easier to resume
  from the repo alone

Verification:

- control deployment-kit test suite was re-run after the hardening pass
- result:
  - `51 passed`

Current best operator posture remains:

- keep the lab parked by default
- only use the smoke helpers when a real live proof is intentionally needed
