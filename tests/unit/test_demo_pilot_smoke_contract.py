"""Contract tests for pilot smoke evidence and share-pack paths (Phase 5 Task 1).

Smoke cannot pass by skipping evidence/share-pack execution. Missing
prerequisite is BLOCKED, not pass.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
SMOKE_SCRIPT = SCRIPTS_DIR / "demo-sales-local-pilot-smoke.ps1"
EVIDENCE_SCRIPT = SCRIPTS_DIR / "demo-sales-local-pilot-evidence.ps1"


def _run_powershell(script_path: Path, args: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-File", str(script_path)] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def test_smoke_fails_without_evidence_in_fresh_runtime():
    """Smoke invoked in a fresh temp runtime with no evidence must exit non-zero."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run_powershell(SMOKE_SCRIPT, ["-RuntimePath", tmpdir, "-IncludeSharePack"])
        assert result.returncode != 0, \
            f"Smoke passed without evidence — should be BLOCKED.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "BLOCKED" in result.stdout or "evidence" in result.stdout.lower(), \
            f"Expected BLOCKED message about evidence.\nstdout: {result.stdout}"


def test_smoke_passes_with_sanitized_fixture_evidence_and_sharepack():
    """Smoke with sanitized fixture evidence and -IncludeSharePack runs all steps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        evidence_path = runtime / "demo-sales-local-pilot-evidence.md"
        # Write a minimal sanitized fixture evidence file
        evidence_path.write_text(
            "# Pilot Evidence\n\n"
            "## Campaign Summary\n- Dry-run completed: yes\n"
            "## Success Evidence\n- 3 posts posted\n"
            "## Safety Gate\n- LIVE_ACTIONS_ENABLED=false\n"
            "- DRY_RUN_DEFAULT=true\n",
            encoding="utf-8",
        )
        result = _run_powershell(SMOKE_SCRIPT, ["-RuntimePath", str(runtime), "-IncludeSharePack"], timeout=120)
        assert result.returncode == 0, \
            f"Smoke failed with evidence.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        # No SKIP in output (share-pack was included and evidence was present)
        assert "SKIP:" not in result.stdout, \
            f"Smoke output contains SKIP.\nstdout: {result.stdout}"
        # Share pack was generated
        assert "share pack" in result.stdout.lower() or "PASS: share pack" in result.stdout, \
            f"Share pack step not found in output.\nstdout: {result.stdout}"
