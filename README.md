# FBKit / FlowKit

This repository currently runs **FBKit**, a local-first Facebook automation assistant built from the original FlowKit codebase. It uses a Python FastAPI agent, SQLite task queue, and a Chrome extension WebSocket bridge to run Facebook tasks through a logged-in browser session.

> **Safety default:** FBKit is dry-run first. Real mutating Facebook actions are disabled by default at both the server Safety Gate and the Chrome extension DOM-action layer.

## Documentation Map

Use the README in two parts:

- **Current FBKit operations:** sections from `Current FBKit Quick Start` through `Live Action Warning` describe the active Facebook automation workflow.
- **Legacy FlowKit archive:** sections from `Legacy FlowKit / Google Flow Archive` downward document the older Google Flow video pipeline and are retained for historical/reference use only.

For verified Safety Gate entry points and current runtime behavior, see `docs/codebase-summary.md`.

## Current FBKit Quick Start

### 1. Start the agent in safe local mode

PowerShell:

```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
.\.venv\Scripts\python.exe -m agent.main
```

Or use the safe Windows helper at `scripts/start-fbkit-safe.ps1`:

```powershell
.\scripts\start-fbkit-safe.ps1
```

Preview the safe environment and command without starting the agent:

```powershell
.\scripts\start-fbkit-safe.ps1 -PrintOnly
```

Bash/Git Bash/WSL:

```bash
LIVE_ACTIONS_ENABLED=false \
DRY_RUN_DEFAULT=true \
APPROVAL_REQUIRED=true \
API_AUTH_ENABLED=false \
WS_AUTH_ENABLED=false \
python -m agent.main
```

The agent listens on:

- REST API: `http://127.0.0.1:8100`
- Extension WebSocket: `ws://127.0.0.1:9222`

### 2. Load and connect the Chrome extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select `extension/`.
4. Open `https://www.facebook.com/` and sign in.
5. Verify the extension session:

```bash
curl http://127.0.0.1:8100/api/status
```

Look for a logged-in session with a non-empty `fb_uid`:

```json
{
  "extension": {
    "connected": true,
    "sessions": [{"fb_uid": "...", "logged_in": true}]
  }
}
```

### 3. Run the safe dry-run smoke test

```bash
python scripts/fbkit-dry-run-smoke.py
```

On Windows with the repo virtualenv:

```powershell
.\.venv\Scripts\python.exe scripts\fbkit-dry-run-smoke.py
```

The smoke script:

- checks `/api/status`
- finds the logged-in extension `fb_uid`
- finds or creates a matching local account
- submits exactly one task with `dryRun=true`
- defaults to `POST_TEXT`, with optional safe variants: `LIKE_POST`, `COMMENT_POST`, `SEND_MESSAGE`
- passes only if the task completes with `dryRun=true`

Run a specific dry-run variant:

```powershell
.\.venv\Scripts\python.exe scripts\fbkit-dry-run-smoke.py --variant LIKE_POST --content "https://www.facebook.com/example/posts/123"
```

It does **not** approve tasks and does **not** request live dispatch.

Validated dry-run variants recorded in `plans/reports/260506-1929-fbkit-dry-run-runtime-validation-report.md`:

- `POST_TEXT`
- `LIKE_POST`
- `COMMENT_POST`
- `SEND_MESSAGE`

## Safety Gate Defaults

FBKit centralizes mutation safety in `agent/services/safety_gate.py`.

| Env var | Safe default | Purpose |
|---|---:|---|
| `LIVE_ACTIONS_ENABLED` | `false` | Global switch for live Facebook mutations |
| `DRY_RUN_DEFAULT` | `true` | Default to dry-run when no explicit payload flag is provided |
| `APPROVAL_REQUIRED` | `true` | Require server-owned `_serverApproved=true` before live mutation |

Mutating task types include posting, messaging, liking, commenting, sharing, friend actions, group actions, page follow/unfollow, and video reup tasks.

Additional protections:

- external `/api/tasks` creation strips client-supplied approval/quota markers
- worker re-enforces Safety Gate immediately before extension dispatch
- live quota is reserved before live dispatch and skipped for dry-run tasks
- `FBClient` requires exact `fb_uid` routing when a task targets a specific Facebook account
- live mutating worker tasks fail closed if the account has no resolved `fb_uid`
- extension mutating handlers return before navigation/click/type/file-upload when `dryRun=true` or when `EXTENSION_LIVE_ACTIONS_ENABLED=false`
- extension-local live-action guard forces dry-run with `safetyReason: "extension_live_actions_disabled"`, independent of server payload approval

## Live Action Warning

Do **not** enable live Facebook actions on your main account as a first test.

Before any live test:

1. Create a dedicated test Facebook account/page/group.
2. Keep `LIVE_ACTIONS_ENABLED=false` until dry-run smoke tests pass.
3. Start with one low-risk post task.
4. Approve it through the server approval endpoint only after reviewing the payload.
5. Confirm the extension-side `EXTENSION_LIVE_ACTIONS_ENABLED` guard has been intentionally changed for a controlled test; otherwise the extension still forces dry-run.
6. Do not live-test inbox/comment/engagement automation until the posting flow is proven safe.

## Legacy FlowKit / Google Flow Archive

The sections below are legacy FlowKit / Google Flow documentation retained for historical context. They do not describe the current FBKit safety workflow above.

> **Current FBKit readiness:** use `GET /health` for a basic process check and `GET /api/status` for the active FBKit runtime and extension-session check. Historical `/health` references below belong to the legacy Google Flow archive and may describe richer legacy response fields.

## Legacy Showcase

All outputs below were generated end-to-end by this system — from story concept to final YouTube-ready video with thumbnails, narration, and branding.

### Generated YouTube Thumbnails

<p align="center">
  <img src="docs/images/thumbnail_hormuz.jpg" width="400" alt="Hormuz Strait naval blockade thumbnail" />
  <img src="docs/images/thumbnail_f15e_rescue.jpg" width="400" alt="F-15E pilot rescue thumbnail" />
</p>
<p align="center">
  <img src="docs/images/thumbnail_operation_resolve.jpg" width="400" alt="Operation Absolute Resolve thumbnail" />
  <img src="docs/images/thumbnail_tapalpa.jpg" width="400" alt="Tapalpa cartel operation thumbnail" />
</p>
<p align="center">
  <img src="docs/images/thumbnail_north_korea.jpg" width="400" alt="North Korea defection thumbnail" />
  <img src="docs/images/thumbnail_iran_israel.jpg" width="400" alt="Iran vs Israel conflict thumbnail" />
</p>

### Visual Consistency Across Scenes

The reference image system keeps characters consistent across an entire video. Each character is generated once as a reference, then the AI uses that reference in every scene — maintaining the same face, clothing, and features.

**Doctor character** — same face, glasses, white coat across 4 different scenes:

<p align="center">
  <img src="docs/images/scene_nk_doctor_surgery.jpg" width="200" alt="Doctor in surgery" />
  <img src="docs/images/scene_nk_doctor_operating.jpg" width="200" alt="Doctor in operating theater" />
  <img src="docs/images/scene_nk_doctor_interview1.jpg" width="200" alt="Doctor interview — gesturing" />
  <img src="docs/images/scene_nk_doctor_interview2.jpg" width="200" alt="Doctor interview — smiling" />
</p>

**Defector character** — same face across ICU, hospital, interview, and Seoul streets:

<p align="center">
  <img src="docs/images/scene_nk_defector_icu.jpg" width="200" alt="Defector in ICU" />
  <img src="docs/images/scene_nk_defector_hospital.jpg" width="200" alt="Defector in hospital with nurse" />
  <img src="docs/images/scene_nk_defector_interview.jpg" width="200" alt="Defector interview" />
  <img src="docs/images/scene_nk_defector_seoul.jpg" width="200" alt="Defector walking Seoul streets" />
</p>

<sub>All frames from a single 50-scene project. Both characters maintain consistent appearance across completely different settings and lighting conditions — powered by the reference image system.</sub>

### F-15E Rescue — Full Story Arc (25 scenes)

<p align="center">
  <img src="docs/images/scene_f15e_map.jpg" width="260" alt="Scene 1: Strategic map overview" />
  <img src="docs/images/scene_f15e_pilot.jpg" width="260" alt="Scene 3: Pilot walks from F-15E" />
  <img src="docs/images/scene_f15e_formation.jpg" width="260" alt="Scene 6: F-15E formation refueling" />
</p>
<p align="center">
  <img src="docs/images/scene_f15e_hit.jpg" width="260" alt="Scene 10: F-15E hit at night" />
  <img src="docs/images/scene_f15e_csar.jpg" width="260" alt="Scene 15: CSAR command center alert" />
  <img src="docs/images/scene_f15e_survival.jpg" width="260" alt="Scene 20: Pilot surviving in mountains" />
</p>

<sub>Strategic briefing → pilot departure → formation flight → aircraft hit → CSAR alert → pilot survival.</sub>

### Hormuz Strait — Naval Scenes

<p align="center">
  <img src="docs/images/scene_hormuz_patrol.jpg" width="400" alt="Iranian patrol boats in formation" />
  <img src="docs/images/scene_hormuz_bridge.jpg" width="400" alt="US Navy commander on bridge" />
</p>
<p align="center">
  <img src="docs/images/scene_hormuz_ciws.jpg" width="400" alt="CIWS engagement at sea" />
  <img src="docs/images/scene_hormuz_sunset.jpg" width="400" alt="Warship sailing into sunset" />
</p>

### What the Pipeline Produces

Each project goes through: **story → entities → reference images → scene images → 8s video clips → narration (TTS) → concat → thumbnails → YouTube upload** — all orchestrated via API or AI agent skills.

| Output | Description |
|--------|-------------|
| Reference images | One per character/location/prop — maintains visual consistency |
| Scene images | Composed using all referenced entities |
| 8-second video clips | Generated from scene images with camera motion + sound effects |
| 4K upscale | Optional upscale to 4K resolution |
| Narrator TTS | Voice-cloned narration per scene |
| Final video | All clips concatenated, trimmed to narrator timing |
| Thumbnails | YouTube-optimized with text overlays + branding |
| YouTube metadata | SEO-optimized title, description, tags, hashtags |

---

### Chrome Extension — Live Dashboard

<p align="center">
  <img src="docs/images/extension_screenshot.jpg" width="800" alt="Chrome extension showing request log, video generation progress, and Google Flow interface" />
</p>

<sub>The Chrome extension runs alongside Google Flow — showing real-time request log (614 total, 328 success), video generation progress, and token status. The Python agent communicates with the extension via WebSocket to automate all API calls.</sub>

## Legacy Google Flow Architecture

```
┌──────────────────┐     WebSocket      ┌──────────────────────┐
│  Python Agent    │◄──────────────────►│  Chrome Extension     │
│  (FastAPI+SQLite)│     localhost:9222  │  (MV3 Service Worker) │
│                  │                    │                       │
│  - REST API :8100│  ── commands ──►   │  - Token capture      │
│  - Queue worker  │  ◄── results ──    │  - reCAPTCHA solve    │
│  - Post-process  │                    │  - API proxy          │
│  - SQLite DB     │                    │  (on labs.google)     │
└──────────────────┘                    └──────────────────────┘
```

## Legacy Google Flow Quick Start

### One-command setup

```bash
./setup.sh
```

This checks and installs: Python 3.10+, pip, ffmpeg, ffprobe, Chrome, creates venv, installs dependencies, verifies imports.

> **Windows:** Use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) (`wsl --install`) or Git Bash. All bash scripts and commands assume a Unix shell.

### Manual setup

```bash
# Prerequisites: Python 3.10+, ffmpeg, Chrome
pip install -r requirements.txt
```

### Run

```bash
# 1. Load Chrome extension: chrome://extensions → Developer mode → Load unpacked → extension/
# 2. Open https://labs.google/fx/tools/flow and sign in
# 3. Start agent
source venv/bin/activate   # if using setup.sh
python -m agent.main

# 4. Verify
curl http://127.0.0.1:8100/health
# {"status":"ok","extension_connected":true}
```

## Legacy Google Flow Coolify Hybrid Deployment

This repo includes a `Dockerfile` and `docker-compose.yaml` for a hybrid Coolify setup:

- Coolify runs the Python agent/API on your VM
- Chrome extension + Google Flow tab stay on your local machine
- Local Chrome reaches the VM through SSH tunnel, so the extension can keep using `127.0.0.1`

### Coolify app settings

- **Build Pack:** Docker Compose
- **Compose file:** `/docker-compose.yaml`
- **Ports:** published only on loopback
  - `127.0.0.1:8100:8100`
  - `127.0.0.1:9222:9222`
- **Persistent volume:** `flowkit-runtime:/app/runtime`

### Required runtime env

```bash
FLOW_AGENT_DIR=/app/runtime
API_HOST=0.0.0.0
API_PORT=8100
WS_HOST=0.0.0.0
WS_PORT=9222
API_AUTH_ENABLED=true
API_KEY=replace-with-strong-random-secret
WS_AUTH_ENABLED=true
WS_API_KEY=replace-with-strong-random-secret
DATA_ENCRYPTION_KEY=replace-with-32-byte-secret-material
```

### Local SSH tunnel

Run this on your Windows machine before opening the extension:

```powershell
ssh -N -L 8100:127.0.0.1:8100 -L 9222:127.0.0.1:9222 hth2-box
```

Then:

1. Load `extension/` as unpacked extension in Chrome
2. Open `https://labs.google/fx/tools/flow`
3. Verify the agent over the tunnel:

```bash
curl http://127.0.0.1:8100/health
```

## Legacy Google Flow End-to-End Example: "Pippip the Fish Merchant"

A chubby cat sells fish at a market. 3 scenes, vertical, Pixar 3D style.

### How it works (read this first)

The system uses **reference images** to keep visuals consistent across scenes. Here's the mental model:

**1. Identify every visual element** that should look the same across scenes:
- Characters → `entity_type: "character"` (portrait reference)
- Places → `entity_type: "location"` (landscape reference)
- Important objects → `entity_type: "visual_asset"` (detail reference)

**2. Describe ONLY appearance** in the entity `description` — this generates the reference image:
- `"Chubby orange tabby cat with blue apron, straw hat"` (what it looks like)

**3. Write scene prompts as ACTION** — reference entities by name, describe what they DO:
- `"Pippip stands behind Fish Stall, arranging fish..."` (what happens)
- NOT: `"A chubby orange tabby cat wearing a blue apron stands behind a wooden stall..."` (don't repeat appearance)

**4. List all entities that appear** in each scene's `character_names` array — their reference images get passed to the AI as visual input, ensuring consistency.

```
Story idea
    ↓
Break into visual elements → characters[] array with entity_type + description
    ↓
Write scene prompts using entity NAMES → character_names lists which refs to use
    ↓
System generates ref image per entity → then composes scenes using those refs
```

### Using Skills (recommended)

Skills handle all the API calls, polling, and verification automatically. Use with Claude Code (`/fk-command`) or follow the recipe in `skills/*.md` for any AI agent.

```
/fk-create-project             ← interactive: asks story, creates entities + scenes
/fk-gen-refs <project_id>      ← generates all reference images, verifies UUIDs
/fk-gen-images <pid> <vid>     ← generates scene images with all refs applied
/fk-gen-videos <pid> <vid>     ← generates videos (2-5 min each, polls automatically)
/fk-concat <vid>               ← downloads + merges into final video
/fk-status <pid>               ← dashboard: what's done, what's next
```

Full pipeline in 5 commands. Each skill pre-checks dependencies (e.g. `/fk-gen-images` verifies all refs exist first).

### Manual API (step by step)

<details>
<summary>Click to expand raw curl commands</summary>

#### Step 1: Create project with reference entities

From the story, identify every visual element that repeats across scenes:

| Element | entity_type | description (appearance only) |
|---------|-------------|-------------------------------|
| Pippip | `character` | Chubby orange tabby cat, big green eyes, blue apron, straw hat |
| Fish Stall | `location` | Rustic wooden stall, thatched roof, ice display |
| Open Market | `location` | Southeast Asian market, colorful awnings, lanterns |
| Golden Fish | `visual_asset` | Golden koi, shimmering scales, magical glow |

```bash
curl -X POST http://127.0.0.1:8100/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pippip the Fish Merchant",
    "story": "Pippip is a chubby orange tabby cat who sells fish at a Southeast Asian open market. Scene 1: Morning setup. Scene 2: Staring at the golden fish. Scene 3: Eating the last fish at sunset.",
    "characters": [
      {"name": "Pippip", "entity_type": "character", "description": "Chubby orange tabby cat with big green eyes, blue apron, straw hat. Walks upright. Pixar-style 3D."},
      {"name": "Fish Stall", "entity_type": "location", "description": "Small rustic wooden market stall with thatched bamboo roof, crushed ice display, hanging brass scale."},
      {"name": "Open Market", "entity_type": "location", "description": "Bustling Southeast Asian open-air market with colorful awnings, hanging lanterns, stone walkway."},
      {"name": "Golden Fish", "entity_type": "visual_asset", "description": "Magnificent golden koi fish with shimmering iridescent scales, elegant fins, slight magical glow."}
    ]
  }'
# Save project_id from response
```

#### Step 2: Create video + scenes

Scene prompts reference entities by **name** (not description). `character_names` lists which reference images to apply.

```bash
# Create video
curl -X POST http://127.0.0.1:8100/api/videos \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<PID>", "title": "Pippip Episode 1"}'

# Scene 1 (ROOT) — Pippip + Fish Stall + Open Market appear
curl -X POST http://127.0.0.1:8100/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "<VID>", "display_order": 0,
    "prompt": "Pippip stands behind Fish Stall, arranging fresh fish on ice. Sunrise, golden light in Open Market. Pixar 3D.",
    "character_names": ["Pippip", "Fish Stall", "Open Market"],
    "chain_type": "ROOT"
  }'

# Scene 2 (CONTINUATION) — Golden Fish now appears
curl -X POST http://127.0.0.1:8100/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "<VID>", "display_order": 1,
    "prompt": "Pippip leans over Fish Stall, staring at Golden Fish on empty ice. Drooling. Open Market dark behind. Pixar 3D.",
    "character_names": ["Pippip", "Fish Stall", "Golden Fish", "Open Market"],
    "chain_type": "CONTINUATION", "parent_scene_id": "<scene-1-id>"
  }'

# Scene 3 (CONTINUATION)
curl -X POST http://127.0.0.1:8100/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "<VID>", "display_order": 2,
    "prompt": "Pippip sits on stool at Fish Stall eating Golden Fish with chopsticks. SOLD OUT sign. Open Market sunset. Pixar 3D.",
    "character_names": ["Pippip", "Fish Stall", "Golden Fish", "Open Market"],
    "chain_type": "CONTINUATION", "parent_scene_id": "<scene-2-id>"
  }'
```

#### Step 3-6: Generate refs → images → videos → concat

```bash
# Step 3: Generate reference images (one per entity, wait for each)
curl -X POST http://127.0.0.1:8100/api/requests \
  -d '{"type": "GENERATE_CHARACTER_IMAGE", "character_id": "<CID>", "project_id": "<PID>"}'
# Poll: GET /api/requests/<RID> until status=COMPLETED
# Repeat for each entity. Verify all have UUID media_id.

# Step 4: Generate scene images
curl -X POST http://127.0.0.1:8100/api/requests \
  -d '{"type": "GENERATE_IMAGE", "scene_id": "<SID>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "VERTICAL"}'
# Worker blocks if any ref is missing media_id

# Step 5: Generate videos (2-5 min each)
curl -X POST http://127.0.0.1:8100/api/requests \
  -d '{"type": "GENERATE_VIDEO", "scene_id": "<SID>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "VERTICAL"}'

# Step 6: Download + concat
curl -s "http://127.0.0.1:8100/api/scenes?video_id=<VID>"  # get video URLs
# Download each, normalize with ffmpeg, concat
```

</details>

---

## Legacy Google Flow Core Concepts

### Reference Image System

Every visual element that should stay consistent gets a **reference image** — characters, locations, props. Each reference has a UUID `media_id` used in all scene generations via `imageInputs`.

| Entity Type | Aspect Ratio | Composition |
|-------------|-------------|-------------|
| `character` | Portrait | Full body head-to-toe, front-facing, centered |
| `location` | Landscape | Establishing shot, level horizon, atmospheric |
| `creature` | Portrait | Full body, natural stance, distinctive features |
| `visual_asset` | Portrait | Detailed view, textures, scale reference |

### Scene Prompts = Action Only

Scene prompts describe **what happens**, not character appearance. The reference images maintain visual consistency.

```
DO:   "Pippip juggling fish at Fish Stall, crowd watching in Open Market"
DON'T: "Pippip the chubby orange tabby cat wearing a blue apron juggling..."
```

### Media ID = UUID

All `media_id` values are UUID format (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Never the base64 `CAMS...` mediaGenerationId.

### Two Prompts per Scene

Each scene has **two separate prompts**:
- `prompt` — describes the **still image** (frame 0): `"Luna steps out of rocket onto candy planet. Wide shot, sunrise."`
- `video_prompt` — describes the **8s video motion** with sub-clip timing and camera directions:

```
0-3s: Wide crane down, Luna steps out of rocket onto Candy Planet Surface. Luna gasps "It's beautiful!"
3-6s: Low angle tracking shot, Luna walks across candy ground, shallow DOF. Luna says "Everything is made of candy."
6-8s: Close-up Luna's face, eyes wide with wonder, golden hour backlight. Silence, ambient wind.
```

### Character Voice

Characters can have a `voice_description` (max ~30 words) for voice consistency:
```json
{"name": "Luna", "entity_type": "character", "description": "Small white cat...", "voice_description": "Soft curious childlike voice with wonder and slight purring"}
```

Voice descriptions are auto-appended to video prompts before generation.

### No Background Music

The worker auto-appends `"No background music. Keep only natural sound effects and ambient sounds."` to all video prompts. Sound effects from the scene (footsteps, splashing, wind) are preserved.

## Legacy Google Flow Pipeline Overview

```
1. Create project      POST /api/projects (with entities + story)
2. Create video        POST /api/videos
3. Create scenes       POST /api/scenes (chain_type: ROOT → CONTINUATION)
4. Gen ref images      POST /api/requests {type: GENERATE_CHARACTER_IMAGE} per entity
   → Wait ALL complete, verify all have UUID media_id
5. Gen scene images    POST /api/requests {type: GENERATE_IMAGE} per scene
   → Wait ALL complete
6. Gen videos          POST /api/requests {type: GENERATE_VIDEO} per scene
   → Wait ALL complete (2-5 min each)
7. (Optional) Upscale  POST /api/requests {type: UPSCALE_VIDEO} (TIER_TWO only)
8. Download + concat   ffmpeg normalize + concat
```

## Legacy Google Flow Skills (AI Agent Workflows)

Ready-to-use workflow recipes in `skills/` (also available as `/slash-commands` in Claude Code):

### Basic Pipeline

| Skill | Description |
|-------|-------------|
| `/fk-create-project` | Create project + entities + video + scenes interactively |
| `/fk-gen-refs` | Generate reference images for all entities |
| `/fk-gen-images` | Generate scene images with character refs |
| `/fk-gen-videos` | Generate videos from scene images |
| `/fk-concat` | Download + merge all scene videos |

### Advanced Video

| Skill | Description |
|-------|-------------|
| `/fk-gen-chain-videos` | Auto start+end frame chaining for smooth transitions (i2v_fl) |
| `/fk-insert-scene` | Multi-angle shots, cutaways, close-ups within a chain |
| `/fk-creative-mix` | Analyze story + suggest all techniques (chain, insert, r2v, parallel) |

### Reference

| Skill | Description |
|-------|-------------|
| `/fk-camera-guide` | Camera angles, movements, lighting, DOF for cinematic video prompts |

### TTS & Narration

| Skill | Description |
|-------|-------------|
| `/fk-gen-tts-template` | Create a voice template for consistent narration |
| `/fk-gen-narrator` | Generate narrator text + TTS for all scenes |
| `/fk-gen-text-overlays` | Generate text overlays from narrator text (dates, locations, stats) |
| `/fk-concat-fit-narrator` | Trim scene videos to fit narrator duration, then concat |

### YouTube

| Skill | Description |
|-------|-------------|
| `/fk-youtube-seo` | Generate SEO-optimized title, description, tags |
| `/fk-brand-logo` | Apply channel icon watermark to video/thumbnails |
| `/fk-youtube-upload` | Upload to YouTube with rule validation + scheduling |
| `/fk-thumbnail` | Generate YouTube-optimized thumbnails |

### Utilities

| Skill | Description |
|-------|-------------|
| `/fk-status` | Full project dashboard + recommended next action |
| `/fk-fix-uuids` | Repair any CAMS... media_ids to UUID format |
| `/fk-add-material` | Image material system |

### AI CLI Compatibility

Skills work with any AI CLI that can read files:

| CLI | Instructions | How skills work |
|-----|-------------|-----------------|
| Claude Code | `CLAUDE.md` (auto-loaded) | Native `/fk:` slash commands |
| Codex CLI | `AGENTS.md` → reads `CLAUDE.md` | User says `/fk:<name>`, agent reads `skills/fk:<name>.md` |
| Gemini CLI | `GEMINI.md` → reads `CLAUDE.md` | Same pattern |

## Legacy Google Flow Video Generation Techniques

| Technique | API Type | Use Case |
|-----------|----------|----------|
| **i2v** | `GENERATE_VIDEO` | Image → video (standard) |
| **i2v_fl** | `GENERATE_VIDEO` + endImage | Start+end frame → smooth scene transitions |
| **r2v** | `GENERATE_VIDEO_REFS` | Reference images → video (intros, dream sequences) |
| **Upscale** | `UPSCALE_VIDEO` | Video → 4K (TIER_TWO only) |

## Legacy Google Flow API Reference

### CRUD Endpoints

| Resource | Create | List | Get | Update | Delete |
|----------|--------|------|-----|--------|--------|
| Project | `POST /api/projects` | `GET /api/projects` | `GET /api/projects/{id}` | `PATCH /api/projects/{id}` | `DELETE /api/projects/{id}` |
| Character | `POST /api/characters` | `GET /api/characters` | `GET /api/characters/{id}` | `PATCH /api/characters/{id}` | `DELETE /api/characters/{id}` |
| Video | `POST /api/videos` | `GET /api/videos?project_id=` | `GET /api/videos/{id}` | `PATCH /api/videos/{id}` | `DELETE /api/videos/{id}` |
| Scene | `POST /api/scenes` | `GET /api/scenes?video_id=` | `GET /api/scenes/{id}` | `PATCH /api/scenes/{id}` | `DELETE /api/scenes/{id}` |
| Request | `POST /api/requests` | `GET /api/requests` | `GET /api/requests/{id}` | `PATCH /api/requests/{id}` | — |

### Special Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Server + extension status |
| `GET /api/flow/status` | Extension connection details |
| `GET /api/flow/credits` | User credits + tier |
| `GET /api/requests/pending` | Pending request queue |
| `GET /api/projects/{id}/characters` | Entities linked to project |

### Request Types

| Type | Required Fields | Async? | reCAPTCHA? |
|------|----------------|--------|------------|
| `GENERATE_CHARACTER_IMAGE` | character_id, project_id | No | Yes |
| `GENERATE_IMAGE` | scene_id, project_id, video_id, orientation | No | Yes |
| `GENERATE_VIDEO` | scene_id, project_id, video_id, orientation | Yes | Yes |
| `GENERATE_VIDEO_REFS` | scene_id, project_id, video_id, orientation | Yes | Yes |
| `UPSCALE_VIDEO` | scene_id, project_id, video_id, orientation | Yes | Yes |

## Legacy Google Flow Worker Behavior

- **Server handles throttling** — worker enforces max 5 concurrent + 10s cooldown automatically. Use `POST /api/requests/batch` to submit all at once; do NOT manually batch.
- **10s cooldown** between API calls (anti-spam, configurable via `API_COOLDOWN`)
- **Reference blocking** — scene image gen refuses if any referenced entity is missing `media_id`
- **Skip completed** — won't re-generate already-completed assets
- **Cascade clear** — regenerating image auto-resets downstream video + upscale
- **Retry** — failed requests retry up to 5 times
- **UUID enforcement** — extracts UUID from fifeUrl if response doesn't provide it directly
- **Voice context** — auto-appends character `voice_description` to video prompts
- **No background music** — auto-appends "no background music, keep sound effects" to all video prompts

## Legacy Google Flow Material System

Every project must have a `material` field that controls the visual style of generated images. Set it at project creation.

```bash
# List available materials
curl -s http://127.0.0.1:8100/api/materials

# Set on project
curl -X POST http://127.0.0.1:8100/api/projects \
  -d '{"name": "...", "material": "3d_pixar", ...}'
```

Materials control both entity `image_prompt` style and scene `scene_prefix`. Examples: `realistic`, `3d_pixar`, `anime`, `stop_motion`, `minecraft`, `oil_painting`.

## Legacy Google Flow Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `127.0.0.1` | REST API bind address |
| `API_PORT` | `8100` | REST API port |
| `WS_HOST` | `127.0.0.1` | WebSocket server bind |
| `WS_PORT` | `9222` | WebSocket server port |
| `POLL_INTERVAL` | `5` | Worker poll interval (seconds) |
| `MAX_RETRIES` | `5` | Max retries per request |
| `VIDEO_POLL_TIMEOUT` | `420` | Video gen poll timeout (seconds) |
| `API_COOLDOWN` | `10` | Seconds between API calls (anti-spam) |

## Legacy Google Flow Internal Architecture

```
agent/
├── main.py              # FastAPI app + WebSocket server
├── config.py            # Configuration (loads models.json)
├── models.json          # Video/upscale/image model mappings
├── db/
│   ├── schema.py        # SQLite schema (aiosqlite)
│   └── crud.py          # Async CRUD with column whitelisting
├── models/              # Pydantic models + Literal enums
├── api/                 # REST routes (projects, videos, scenes, characters, requests, flow)
├── services/
│   ├── flow_client.py   # WS bridge to extension
│   ├── headers.py       # Randomized browser headers
│   ├── tts.py           # OmniVoice TTS (subprocess-based)
│   ├── scene_chain.py   # Continuation scene logic
│   └── post_process.py  # ffmpeg trim/merge/music
└── worker/
    └── processor.py     # Queue processor + poller

extension/               # Chrome MV3 extension
skills/                  # AI agent workflow recipes (CLI-agnostic)
youtube/
├── auth.py              # OAuth2 multi-channel auth
├── upload.py            # Upload with scheduling + rule validation
└── channels/            # Per-channel config (gitignored)
    └── <channel_name>/
        ├── client_secrets.json  # OAuth2 credentials
        ├── token.json           # Auth token (auto-created)
        ├── channel_rules.json   # Upload rules + SEO defaults
        └── upload_history.json  # Upload log
CLAUDE.md                # AI agent instructions (Claude Code)
AGENTS.md                # AI agent instructions (Codex CLI)
GEMINI.md                # AI agent instructions (Gemini CLI)
```

## Legacy Google Flow TTS Narration (OmniVoice)

Optional narrator voice for scenes. Uses [OmniVoice](https://github.com/tuannguyenhoangit-droid/OmniVoice) — multilingual zero-shot TTS with voice cloning (600+ languages).

### Setup

See `skills/fk-gen-tts-template.md` for full install guide. Quick version:

```bash
pip install torch==2.8.0 torchaudio==2.8.0   # or +cu128 for NVIDIA
pip install omnivoice
python3 -c "from omnivoice import OmniVoice; print('OK')"
```

If OmniVoice is in a separate venv, point to it:
```bash
export TTS_PYTHON_BIN=/path/to/omnivoice-venv/bin/python3
```

### Workflow

1. **Create voice template** — `/fk-gen-tts-template` — generates an anchor voice WAV
2. **Add narrator text** to scenes — `PATCH /api/scenes/{id}` with `narrator_text`
3. **Generate narration** — `/fk-gen-narrator` — voice-clones the template for each scene
4. **Concat with narration** — `/fk-concat-fit-narrator` — trims scene videos to match TTS duration

CPU-only recommended (MPS produces artifacts). ~15-30s per scene.

## Legacy Google Flow YouTube Upload Pipeline

Automated upload with per-channel rules, SEO optimization, and brand watermarking.

### Setup

```bash
# 1. Place OAuth credentials
cp client_secrets.json youtube/channels/<channel_name>/

# 2. Authenticate (opens browser)
python3 youtube/auth.py <channel_name>              # Linux / Windows (WSL)
arch -arm64 python3 youtube/auth.py <channel_name>  # macOS Apple Silicon

# 3. Token saved to youtube/channels/<channel_name>/token.json (auto-refreshes)
```

### Channel Rules (`channel_rules.json`)

Each channel has a rules file controlling upload scheduling and SEO:

```json
{
  "shorts": {"max_per_day": 3, "optimal_times": ["07:00", "12:00", "17:00"]},
  "long_form": {"max_per_day": 1, "optimal_times": ["19:00"]},
  "scheduling": {"min_gap_hours": 4, "avoid_hours": [0,1,2,3,4,5]},
  "seo": {"niche": "...", "default_tags": [...], "title_max_chars": 65}
}
```

### Skill Chain

```
/fk-youtube-seo    → generates title, description, hashtags, tags
/fk-brand-logo     → applies channel icon watermark
/fk-youtube-upload  → validates rules + uploads (auto-detects Short vs Long-form)
```

Upload validation checks: max per day, min gap between uploads, avoid dead hours. Auto-detects Short (<61s + vertical 9:16) vs Long-form.

## Legacy Google Flow Troubleshooting

| Problem | Solution |
|---------|----------|
| Extension shows "Agent disconnected" | Start `python -m agent.main` |
| Extension shows "No token" | Open labs.google/fx/tools/flow |
| `CAPTCHA_FAILED: NO_FLOW_TAB` | Need a Google Flow tab open |
| 403 MODEL_ACCESS_DENIED | Tier mismatch — auto-detect should handle it |
| Scene images inconsistent | Check all refs have `media_id` (UUID). Run `/fk-fix-uuids` |
| media_id starts with CAMS... | Run `/fk-fix-uuids` to extract UUID from URL |
| Upscale permission denied | Requires PAYGATE_TIER_TWO account |

## License

MIT
