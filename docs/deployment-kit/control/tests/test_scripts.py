from pathlib import Path
import socket
import subprocess
import threading
import tempfile


def _wsl_path(path: Path) -> str:
    drive = path.drive.rstrip(":").lower()
    tail = path.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


class _ResetServer:
    def __enter__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen()
        self.port = self._socket.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def _serve(self):
        while self._running:
            try:
                conn, _ = self._socket.accept()
            except OSError:
                return
            conn.close()

    def __exit__(self, exc_type, exc, tb):
        self._running = False
        self._socket.close()
        self._thread.join(timeout=1)
        return False


def test_reset_control_state_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "reset-control-state.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "POSTGRES_CONTAINER" in result.stdout
    assert "REDIS_CONTAINER" in result.stdout


def test_clean_queue_history_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "clean-queue-history.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "INCLUDE_DEAD" in result.stdout
    assert "FORCE=0" in result.stdout


def test_create_demo_project_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "create-demo-project.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "CONTROL_API_URL" in result.stdout
    assert "CHAPTER_COUNT" in result.stdout


def test_public_http_fresh_smoke_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "public-http-fresh-smoke.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "POSTGRES_DSN" in result.stdout
    assert "TARGET_DURATION_SECONDS" in result.stdout
    assert "WAIT_TIMEOUT_SECONDS" in result.stdout


def test_public_http_fresh_smoke_script_dry_run_loads_profile():
    script = Path(__file__).resolve().parents[1] / "scripts" / "public-http-fresh-smoke.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        profile = root / "host-demo.env"
        profile.write_text(
            "\n".join(
                [
                    "CONTROL_API_URL=http://127.0.0.1:18080",
                    "PYTHON_BIN=python3",
                ]
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"CONTROL_PROFILE_FILE='{_wsl_path(profile)}'",
                        "POSTGRES_DSN='postgresql://fk:test@127.0.0.1:5432/fk_control'",
                        "SOURCE_TITLE='Fresh Smoke Title'",
                        "SOURCE_BRIEF='Fresh smoke brief'",
                        "TARGET_DURATION_SECONDS='8'",
                        "CHAPTER_COUNT='1'",
                        "MATERIAL_ID='realistic'",
                        "DRY_RUN='1'",
                        f"'{_wsl_path(script)}'",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert '"status": "dry_run"' in result.stdout
    assert '"control_api_url": "http://127.0.0.1:18080"' in result.stdout
    assert '"target_duration_seconds": 8' in result.stdout
    assert '"chapter_count": 1' in result.stdout
    assert '"material_id": "realistic"' in result.stdout
    assert '"postgres_dsn_present": true' in result.stdout


def test_start_control_api_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "start-control-api.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "CONTROL_API_PORT" in result.stdout
    assert "PYTHON_BIN" in result.stdout


def test_start_scheduler_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "start-scheduler.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "POSTGRES_DSN" in result.stdout
    assert "REDIS_URL" in result.stdout


def test_run_control_demo_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "run-control-demo.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "START_SERVICES" in result.stdout
    assert "RESET_STATE" in result.stdout
    assert "CONTROL_API_PID_FILE" in result.stdout
    assert "WAIT_FOR_ASSIGNMENTS" in result.stdout


def test_control_service_script_reports_stopped_status():
    script = Path(__file__).resolve().parents[1] / "scripts" / "control-service.sh"

    with subprocess.Popen(
        ["bash", "-lc", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ):
        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"RUNTIME_ROOT='{_wsl_path(Path.cwd())}'",
                        "CONTROL_API_URL='http://127.0.0.1:9'",
                        f"'{_wsl_path(script)}'",
                        "status",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert '"control_api_running": false' in result.stdout.lower()
    assert '"scheduler_running": false' in result.stdout.lower()


def test_control_service_script_status_handles_connection_reset():
    script = Path(__file__).resolve().parents[1] / "scripts" / "control-service.sh"

    with _ResetServer() as server:
        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"RUNTIME_ROOT='{_wsl_path(Path.cwd())}'",
                        f"CONTROL_API_URL='http://127.0.0.1:{server.port}'",
                        f"'{_wsl_path(script)}'",
                        "status",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert '"status": "unreachable"' in result.stdout.lower()


def test_control_service_script_health_handles_connection_reset():
    script = Path(__file__).resolve().parents[1] / "scripts" / "control-service.sh"

    with _ResetServer() as server:
        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"CONTROL_API_URL='http://127.0.0.1:{server.port}'",
                        "WAIT_TIMEOUT_SECONDS='1'",
                        "POLL_INTERVAL_SECONDS='0.1'",
                        f"'{_wsl_path(script)}'",
                        "health",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 1
    assert '"status": "timeout"' in result.stdout.lower()


def test_control_service_script_status_loads_profile_file():
    script = Path(__file__).resolve().parents[1] / "scripts" / "control-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        api_pid = root / "control-api.pid"
        scheduler_pid = root / "scheduler.pid"
        api_pid.write_text("123\n", encoding="utf-8")
        scheduler_pid.write_text("456\n", encoding="utf-8")
        profile = root / "host-demo.env"
        profile.write_text(
            "\n".join(
                [
                    f"CONTROL_API_PID_FILE={_wsl_path(api_pid)}",
                    f"SCHEDULER_PID_FILE={_wsl_path(scheduler_pid)}",
                    "CONTROL_API_URL=http://127.0.0.1:9",
                ]
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"CONTROL_PROFILE_FILE='{_wsl_path(profile)}'",
                        f"'{_wsl_path(script)}'",
                        "status",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert '"control_api_pid": 123' in result.stdout
    assert '"scheduler_pid": 456' in result.stdout


def test_control_service_script_start_uses_profile_start_scripts():
    script = Path(__file__).resolve().parents[1] / "scripts" / "control-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        calls = root / "calls.log"
        api_pid = root / "control-api.pid"
        scheduler_pid = root / "scheduler.pid"
        api_start = root / "api-start.sh"
        scheduler_start = root / "scheduler-start.sh"
        api_start.write_text(
            "#!/usr/bin/env bash\n"
            f"echo api >> '{_wsl_path(calls)}'\n",
            encoding="utf-8",
            newline="\n",
        )
        scheduler_start.write_text(
            "#!/usr/bin/env bash\n"
            f"echo scheduler >> '{_wsl_path(calls)}'\n",
            encoding="utf-8",
            newline="\n",
        )
        profile = root / "host-demo.env"
        profile.write_text(
            "\n".join(
                [
                    f"CONTROL_API_START_SCRIPT={_wsl_path(api_start)}",
                    f"SCHEDULER_START_SCRIPT={_wsl_path(scheduler_start)}",
                    f"CONTROL_API_PID_FILE={_wsl_path(api_pid)}",
                    f"SCHEDULER_PID_FILE={_wsl_path(scheduler_pid)}",
                    "CONTROL_API_URL=http://127.0.0.1:9",
                ]
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"CONTROL_PROFILE_FILE='{_wsl_path(profile)}'",
                        "WAIT_FOR_HEALTH=0",
                        "START_DELAY_SECONDS=0",
                        f"'{_wsl_path(script)}'",
                        "start",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        called = calls.read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert sorted(called) == ["api", "scheduler"]


def test_two_lane_lab_service_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "two-lane-lab-service.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "LANE_01_SERVICE_SCRIPT" in result.stdout
    assert "LANE_02_SERVICE_SCRIPT" in result.stdout
    assert "<start|park|status>" in result.stdout


def test_two_lane_lab_service_script_status_aggregates_wrappers():
    script = Path(__file__).resolve().parents[1] / "scripts" / "two-lane-lab-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        control_stub = root / "control.sh"
        lane01_stub = root / "lane01.sh"
        lane02_stub = root / "lane02.sh"

        control_stub.write_text("#!/usr/bin/env bash\necho '{\"component\":\"control\",\"state\":\"up\"}'\n", encoding="utf-8", newline="\n")
        lane01_stub.write_text("#!/usr/bin/env bash\necho '{\"component\":\"lane-01\",\"state\":\"ready\"}'\n", encoding="utf-8", newline="\n")
        lane02_stub.write_text("#!/usr/bin/env bash\necho '{\"component\":\"lane-02\",\"state\":\"paused\"}'\n", encoding="utf-8", newline="\n")

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"CONTROL_SERVICE_SCRIPT='{_wsl_path(control_stub)}'",
                        f"LANE_01_SERVICE_SCRIPT='{_wsl_path(lane01_stub)}'",
                        f"LANE_02_SERVICE_SCRIPT='{_wsl_path(lane02_stub)}'",
                        f"'{_wsl_path(script)}'",
                        "status",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert '"control"' in result.stdout
    assert '"lane_01"' in result.stdout
    assert '"lane_02"' in result.stdout
    assert '"paused"' in result.stdout


def test_two_lane_lab_service_script_uses_default_host_demo_profile():
    script = Path(__file__).resolve().parents[1] / "scripts" / "two-lane-lab-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        control_stub = root / "control.sh"
        lane01_stub = root / "lane01.sh"
        lane02_stub = root / "lane02.sh"

        control_stub.write_text(
            "#!/usr/bin/env bash\n"
            "echo \"{\\\"profile\\\":\\\"$CONTROL_PROFILE_FILE\\\"}\"\n",
            encoding="utf-8",
            newline="\n",
        )
        lane01_stub.write_text("#!/usr/bin/env bash\necho '{\"component\":\"lane-01\"}'\n", encoding="utf-8", newline="\n")
        lane02_stub.write_text("#!/usr/bin/env bash\necho '{\"component\":\"lane-02\"}'\n", encoding="utf-8", newline="\n")

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"CONTROL_SERVICE_SCRIPT='{_wsl_path(control_stub)}'",
                        f"LANE_01_SERVICE_SCRIPT='{_wsl_path(lane01_stub)}'",
                        f"LANE_02_SERVICE_SCRIPT='{_wsl_path(lane02_stub)}'",
                        f"'{_wsl_path(script)}'",
                        "status",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert "host-demo.env" in result.stdout


def test_two_lane_lab_service_script_park_stops_lanes_before_control():
    script = Path(__file__).resolve().parents[1] / "scripts" / "two-lane-lab-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        log_file = root / "calls.log"
        stub_body = (
            "#!/usr/bin/env bash\n"
            f"echo \"$(basename \"$0\"):$1\" >> '{_wsl_path(log_file)}'\n"
            "echo '{\"ok\":true}'\n"
        )
        control_stub = root / "control.sh"
        lane01_stub = root / "lane01.sh"
        lane02_stub = root / "lane02.sh"
        for stub in (control_stub, lane01_stub, lane02_stub):
            stub.write_text(stub_body, encoding="utf-8", newline="\n")

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"CONTROL_SERVICE_SCRIPT='{_wsl_path(control_stub)}'",
                        f"LANE_01_SERVICE_SCRIPT='{_wsl_path(lane01_stub)}'",
                        f"LANE_02_SERVICE_SCRIPT='{_wsl_path(lane02_stub)}'",
                        f"'{_wsl_path(script)}'",
                        "park",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        calls = log_file.read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert calls[:3] == ["lane01.sh:stop", "lane02.sh:stop", "control.sh:stop"]


def test_control_compose_exposes_pythonpath_for_all_python_services():
    compose_file = Path(__file__).resolve().parents[1] / "docker-compose.control.yml"

    content = compose_file.read_text(encoding="utf-8")

    assert "PYTHONPATH: /srv/control" in content
