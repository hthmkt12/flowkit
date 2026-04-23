# FlowKit Deployment Kit

This folder contains a practical deployment starter kit for the 10-lane blueprint.

Use it to stand up:

- 1 control VM
- 10 worker VMs
- 1 isolated FlowKit lane per worker

Contents:

- `control/`
  - control-plane docker-compose
  - env template
  - Postgres schema
  - Redis job contract
  - service descriptions
  - fresh public-http smoke helper
  - one-command local public-http proof wrapper
- `worker/`
  - lane directory layout
  - systemd units
  - lane env template
  - Chrome startup scripts
  - artifact upload replay helper
  - live worker-kit sync helper
- `lane-env/`
  - ready-to-copy env files for lane-01 to lane-10
- `two-lane-same-vm-hth2-box-handoff.md`
  - current same-VM lab state for `lane-01` + `lane-02` on `hth2-box`

Recommended order:

1. Read [10-lane-production-blueprint.md](/F:/vm201 Coolify/flowkit/docs/10-lane-production-blueprint.md)
2. Bring up `control/`
3. Bring up `worker/` on one test worker
4. Validate one lane end to end
5. Replicate for lanes 02-10

## Same-VM Lab Path

The deployment kit now also documents a non-production lab path for running a second isolated lane on the same VM.

Current lab shape on `hth2-box`:

- `lane-01` stays on `8100/9222`
- `lane-02` uses `8110/9232`
- lane-02 worker health uses `18182`
- lane-02 uses its own runtime root, Chrome profile, and unpacked extension bundle

Supporting pieces:

- worker bootstrap now supports custom deploy root and per-lane port overrides
- extension bundles can be rendered with lane-specific endpoints using:
  - `worker/scripts/render-extension-bundle.py`
- host-process same-VM lab orchestration can be coordinated with:
  - `control/scripts/two-lane-lab-service.sh`
- local Windows same-VM lab orchestration can be coordinated with:
  - `control/scripts/two-lane-local-lab.ps1`
- host-demo VM profile is captured in:
  - `control/host-demo.env`

Use these docs for the lab path:

1. [worker/BOOTSTRAP-RUNBOOK.md](/F:/vm201 Coolify/flowkit/docs/deployment-kit/worker/BOOTSTRAP-RUNBOOK.md)
2. [two-lane-same-vm-hth2-box-handoff.md](/F:/vm201 Coolify/flowkit/docs/deployment-kit/two-lane-same-vm-hth2-box-handoff.md)

Same-VM remote orchestration helper:

```bash
cd docs/deployment-kit/control
./scripts/two-lane-lab-service.sh status
./scripts/two-lane-lab-service.sh start
./scripts/two-lane-lab-service.sh park
```

Direct control wrapper with the host-demo profile:

```bash
cd docs/deployment-kit/control
CONTROL_PROFILE_FILE=./host-demo.env ./scripts/control-service.sh status
CONTROL_PROFILE_FILE=./host-demo.env ./scripts/control-service.sh start
CONTROL_PROFILE_FILE=./host-demo.env ./scripts/control-service.sh stop
```

Same-VM local Windows orchestration helper:

```powershell
cd F:\vm201 Coolify\flowkit\docs\deployment-kit\control\scripts
powershell -NoProfile -ExecutionPolicy Bypass -File .\two-lane-local-lab.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\two-lane-local-lab.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File .\two-lane-local-lab.ps1 park
```

One-command local proof wrapper:

```powershell
cd F:\vm201 Coolify\flowkit\docs\deployment-kit\control\scripts
powershell -NoProfile -ExecutionPolicy Bypass -File .\public-http-proof.ps1 run
```

## Operator Quick Reference

Three commands matter most for the current same-VM lab:

1. Sync the canonical worker kit to both live lane roots:

```bash
cd /path/to/flowkit
./docs/deployment-kit/worker/scripts/sync-live-worker-kit.sh
```

2. Run one remote low-cost public-HTTP fresh smoke on the VM:

```bash
cd /home/hth2/flowkit-control-demo/control
CONTROL_PROFILE_FILE=./host-demo.env POSTGRES_DSN='postgresql://...' ./scripts/public-http-fresh-smoke.sh
```

3. Run the full local-to-remote proof wrapper from Windows:

```powershell
cd F:\vm201 Coolify\flowkit\docs\deployment-kit\control\scripts
powershell -NoProfile -ExecutionPolicy Bypass -File .\public-http-proof.ps1 run
```

Operator notes:

- leave `SOURCE_TITLE` unset if you want the smoke helpers to auto-generate a timestamped title
- park the lab again after any live proof to avoid unnecessary credit spend

Important:

- production recommendation is still `1 lane per worker VM`
- same-VM dual-lane is only for lab validation and debugging
