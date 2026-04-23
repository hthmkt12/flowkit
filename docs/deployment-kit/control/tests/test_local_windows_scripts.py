from pathlib import Path
import os
import subprocess
import tempfile


def _run_powershell_script(script: Path, args: list[str], env: dict[str, str] | None = None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        env=merged_env,
    )


def test_two_lane_local_lab_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "two-lane-local-lab.ps1"

    result = _run_powershell_script(script, ["--help"])

    assert result.returncode == 0
    assert "TUNNEL_SERVICE_SCRIPT" in result.stdout
    assert "CHROME_SERVICE_SCRIPT" in result.stdout
    assert "start|park|status" in result.stdout


def test_public_http_proof_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "public-http-proof.ps1"

    result = _run_powershell_script(script, ["--help"])

    assert result.returncode == 0
    assert "LOCAL_LAB_SCRIPT" in result.stdout
    assert "REMOTE_HOST" in result.stdout
    assert "REMOTE_FRESH_SMOKE_SCRIPT" in result.stdout


def test_public_http_proof_script_run_coordinates_local_and_remote():
    script = Path(__file__).resolve().parents[1] / "scripts" / "public-http-proof.ps1"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        log_file = root / "calls.log"
        local_stub = root / "local-lab.ps1"
        ssh_stub = root / "ssh-stub.cmd"

        local_stub.write_text(
            "param([string]$Action)\n"
            f"Add-Content -Path '{log_file}' -Value \"local:$Action\"\n"
            "Write-Output '{\"ok\":true}'\n",
            encoding="utf-8",
            newline="\n",
        )
        ssh_stub.write_text(
            "@echo off\r\n"
            f"echo ssh:%*>>\"{log_file}\"\r\n"
            "echo %* | findstr /C:\"public-http-fresh-smoke.sh\" >nul\r\n"
            "if %errorlevel%==0 (\r\n"
            "  echo {\"status\":\"completed\",\"artifact_urls\":[\"https://example.com/final.mp4\"]}\r\n"
            ")\r\n",
            encoding="utf-8",
            newline="\r\n",
        )

        result = _run_powershell_script(
            script,
            ["run"],
            env={
                "LOCAL_LAB_SCRIPT": str(local_stub),
                "SSH_EXE": str(ssh_stub),
                "REMOTE_HOST": "example-host",
                "REMOTE_CONTROL_ROOT": "/srv/control",
                "REMOTE_LANE_ENV": "/srv/lane-02/env/lane.env",
                "REMOTE_CONTROL_PROFILE": "/srv/control/host-demo.env",
                "SOURCE_TITLE": "Test Fresh Smoke",
                "SOURCE_BRIEF": "Test brief",
                "TARGET_DURATION_SECONDS": "8",
                "CHAPTER_COUNT": "1",
                "MATERIAL_ID": "realistic",
                "WAIT_FOR_READY": "0",
            },
        )
        calls = log_file.read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert '"status":  "completed"' in result.stdout or '"status":"completed"' in result.stdout
    assert calls[0] == "local:start"
    assert any("two-lane-lab-service.sh start" in line for line in calls)
    assert any("public-http-fresh-smoke.sh" in line for line in calls)
    assert "local:park" in calls
    assert any("two-lane-lab-service.sh park" in line for line in calls)


def test_two_lane_local_lab_script_status_aggregates_wrappers():
    script = Path(__file__).resolve().parents[1] / "scripts" / "two-lane-local-lab.ps1"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        tunnel_stub = root / "tunnels.ps1"
        chrome_stub = root / "chrome.ps1"

        tunnel_stub.write_text(
            "param([string]$Action)\n"
            "Write-Output '{\"component\":\"tunnels\",\"state\":\"up\"}'\n",
            encoding="utf-8",
            newline="\n",
        )
        chrome_stub.write_text(
            "param([string]$Action)\n"
            "Write-Output '{\"component\":\"chrome\",\"state\":\"ready\"}'\n",
            encoding="utf-8",
            newline="\n",
        )

        result = _run_powershell_script(
            script,
            ["status"],
            env={
                "TUNNEL_SERVICE_SCRIPT": str(tunnel_stub),
                "CHROME_SERVICE_SCRIPT": str(chrome_stub),
            },
        )

    assert result.returncode == 0
    assert '"tunnels"' in result.stdout
    assert '"chrome"' in result.stdout
    assert '"ready"' in result.stdout


def test_two_lane_local_lab_script_park_stops_chrome_before_tunnels():
    script = Path(__file__).resolve().parents[1] / "scripts" / "two-lane-local-lab.ps1"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        log_file = root / "calls.log"
        tunnel_stub = root / "tunnels.ps1"
        chrome_stub = root / "chrome.ps1"

        tunnel_stub.write_text(
            "param([string]$Action)\n"
            f"Add-Content -Path '{log_file}' -Value \"tunnels:$Action\"\n"
            "Write-Output '{\"ok\":true}'\n",
            encoding="utf-8",
            newline="\n",
        )
        chrome_stub.write_text(
            "param([string]$Action)\n"
            f"Add-Content -Path '{log_file}' -Value \"chrome:$Action\"\n"
            "Write-Output '{\"ok\":true}'\n",
            encoding="utf-8",
            newline="\n",
        )

        result = _run_powershell_script(
            script,
            ["park"],
            env={
                "TUNNEL_SERVICE_SCRIPT": str(tunnel_stub),
                "CHROME_SERVICE_SCRIPT": str(chrome_stub),
            },
        )
        calls = log_file.read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert calls[:2] == ["chrome:park", "tunnels:park"]


def test_local_tunnel_service_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "local-tunnel-service.ps1"

    result = _run_powershell_script(script, ["--help"])

    assert result.returncode == 0
    assert "SSH_EXE" in result.stdout
    assert "LANE_01_PORTS" in result.stdout
    assert "LANE_02_PORTS" in result.stdout


def test_local_chrome_service_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "local-chrome-service.ps1"

    result = _run_powershell_script(script, ["--help"])

    assert result.returncode == 0
    assert "CHROME_EXE" in result.stdout
    assert "LANE_01_PROFILE_DIR" in result.stdout
    assert "LANE_02_PROFILE_DIR" in result.stdout
