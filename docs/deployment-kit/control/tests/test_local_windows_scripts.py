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
