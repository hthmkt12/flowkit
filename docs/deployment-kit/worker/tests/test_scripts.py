import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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


class _JsonHandler(BaseHTTPRequestHandler):
    payload = b'{"status":"ok"}'

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):  # noqa: A003
        return


class _JsonServer:
    def __enter__(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _JsonHandler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)
        return False


def test_lane_runner_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "lane-runner.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "PYTHON_BIN" in result.stdout
    assert "LOG_FILE" in result.stdout


def test_run_worker_demo_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "run-worker-demo.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "WAIT_FOR_HEALTH" in result.stdout
    assert "RUNNER_PID_FILE" in result.stdout


def test_verify_object_storage_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify-object-storage.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "ENV_FILE" in result.stdout
    assert "CHECK_NETWORK" in result.stdout
    assert "R2_PUBLIC_BASE" in result.stdout


def test_verify_object_storage_script_reports_missing_required_config():
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify-object-storage.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        env_dir = root / "env"
        env_dir.mkdir()
        lane_env = env_dir / "lane.env"
        lane_env.write_text(
            "\n".join(
                [
                    "R2_BUCKET=flowkit-output",
                    "R2_ENDPOINT=https://example.r2.cloudflarestorage.com",
                    "R2_PUBLIC_BASE=https://cdn.example.com/base/",
                    "R2_ACCESS_KEY_ID=",
                    "R2_SECRET_ACCESS_KEY=",
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
                        f"LANE_ROOT='{_wsl_path(root)}'",
                        f"'{_wsl_path(script)}'",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 1
    assert '"status": "missing_config"' in result.stdout
    assert "R2_ACCESS_KEY_ID" in result.stdout
    assert "R2_SECRET_ACCESS_KEY" in result.stdout


def test_upload_artifacts_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "upload-artifacts.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "CHAPTER_ID" in result.stdout
    assert "CLEANUP_STALE" in result.stdout
    assert "DRY_RUN" in result.stdout


def test_upload_artifacts_script_requires_chapter_id():
    script = Path(__file__).resolve().parents[1] / "scripts" / "upload-artifacts.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Usage:" in result.stdout


def test_upload_artifacts_script_dry_run_reports_loaded_config():
    script = Path(__file__).resolve().parents[1] / "scripts" / "upload-artifacts.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        env_dir = root / "env"
        env_dir.mkdir()
        lane_env = env_dir / "lane.env"
        lane_env.write_text(
            "\n".join(
                [
                    "LANE_ID=lane-02",
                    "R2_BUCKET=veo3",
                    "R2_ENDPOINT=https://example.r2.cloudflarestorage.com",
                    "R2_PUBLIC_BASE=https://cdn.example.com",
                    "R2_ACCESS_KEY_ID=test-access-key",
                    "R2_SECRET_ACCESS_KEY=test-secret-key",
                    "ALLOW_LOCAL_ARTIFACT_FALLBACK=1",
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
                        f"LANE_ROOT='{_wsl_path(root)}'",
                        "DRY_RUN='1'",
                        f"'{_wsl_path(script)}'",
                        "chapter-123",
                        "--cleanup-stale",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["chapter_id"] == "chapter-123"
    assert payload["cleanup_stale"] is True
    assert payload["lane_id"] == "lane-02"
    assert payload["r2_bucket"] == "veo3"
    assert payload["r2_public_base"] == "https://cdn.example.com"
    assert payload["allow_local_artifact_fallback"] is False


def test_repair_output_ownership_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "repair-output-ownership.sh"

    result = subprocess.run(
        ["bash", _wsl_path(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "EXPECT_OWNER" in result.stdout
    assert "DRY_RUN" in result.stdout
    assert "<scan|fix>" in result.stdout


def test_repair_output_ownership_script_scan_reports_mismatches():
    script = Path(__file__).resolve().parents[1] / "scripts" / "repair-output-ownership.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        output_root = root / "runtime" / "output"
        output_root.mkdir(parents=True)
        mismatched = output_root / "final.mp4"
        mismatched.write_text("video", encoding="utf-8")

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"OUTPUT_ROOT='{_wsl_path(output_root)}'",
                        "EXPECT_OWNER='root'",
                        "EXPECT_GROUP='root'",
                        f"'{_wsl_path(script)}'",
                        "scan",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert '"candidate_count": 1' in result.stdout
    assert "final.mp4" in result.stdout


def test_repair_output_ownership_script_fix_dry_run_emits_chown_commands():
    script = Path(__file__).resolve().parents[1] / "scripts" / "repair-output-ownership.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        output_root = root / "runtime" / "output"
        output_root.mkdir(parents=True)
        mismatched = output_root / "final.mp4"
        mismatched.write_text("video", encoding="utf-8")

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"OUTPUT_ROOT='{_wsl_path(output_root)}'",
                        "EXPECT_OWNER='root'",
                        "EXPECT_GROUP='root'",
                        "SUDO_BIN=''",
                        "DRY_RUN='1'",
                        f"'{_wsl_path(script)}'",
                        "fix",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0
    assert '"mode": "dry_run"' in result.stdout
    assert '"chown root:root' in result.stdout


def test_lane_service_script_reports_stopped_status():
    script = Path(__file__).resolve().parents[1] / "scripts" / "lane-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"LANE_ROOT='{_wsl_path(root)}'",
                        "RUNNER_HEALTH_URL='http://127.0.0.1:9/health'",
                        "RUNNER_READY_URL='http://127.0.0.1:9/ready'",
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
        assert '"runner_running": false' in result.stdout.lower()
        assert '"runner_pid": null' in result.stdout.lower()


def test_lane_service_script_status_handles_connection_reset():
    script = Path(__file__).resolve().parents[1] / "scripts" / "lane-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        with _ResetServer() as server:
            result = subprocess.run(
                [
                    "bash",
                    "-lc",
                    " ".join(
                        [
                            f"LANE_ROOT='{_wsl_path(root)}'",
                            f"RUNNER_HEALTH_URL='http://127.0.0.1:{server.port}/health'",
                            f"RUNNER_READY_URL='http://127.0.0.1:{server.port}/ready'",
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


def test_lane_service_script_loads_runner_port_from_lane_env():
    script = Path(__file__).resolve().parents[1] / "scripts" / "lane-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        env_dir = root / "env"
        env_dir.mkdir()
        payload_file = root / "health.json"
        payload_file.write_text('{"status":"ok"}\n', encoding="utf-8")
        lane_env = "\n".join(
            [
                f"RUNNER_HEALTH_URL=file://{_wsl_path(payload_file)}",
                f"RUNNER_READY_URL=file://{_wsl_path(payload_file)}",
            ]
        )
        (env_dir / "lane.env").write_text(f"{lane_env}\n", encoding="utf-8")
        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"LANE_ROOT='{_wsl_path(root)}'",
                        f"'{_wsl_path(script)}'",
                        "health",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert '"status": "ok"' in result.stdout.lower()


def test_lane_service_script_health_handles_connection_reset():
    script = Path(__file__).resolve().parents[1] / "scripts" / "lane-service.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        with _ResetServer() as server:
            result = subprocess.run(
                [
                    "bash",
                    "-lc",
                    " ".join(
                        [
                            f"LANE_ROOT='{_wsl_path(root)}'",
                            f"RUNNER_HEALTH_URL='http://127.0.0.1:{server.port}/health'",
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
        assert '"status": "unreachable"' in result.stdout.lower()


def test_bootstrap_lane_script_supports_same_vm_lane_overrides():
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-lane.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        deploy_root = root / "flowkit-worker-demo-lane-02"
        systemd_dir = root / "systemd"
        systemd_dir.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "DEPLOY_ROOT": _wsl_path(deploy_root),
                "SUDO_BIN": "",
                "SYSTEMCTL_BIN": "true",
                "SYSTEMD_DIR": _wsl_path(systemd_dir),
                "API_PORT_OVERRIDE": "8110",
                "WS_PORT_OVERRIDE": "9232",
                "RUNNER_HEALTH_PORT_OVERRIDE": "18182",
            }
        )

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"DEPLOY_ROOT='{_wsl_path(deploy_root)}'",
                        "SUDO_BIN=''",
                        "SYSTEMCTL_BIN='true'",
                        f"SYSTEMD_DIR='{_wsl_path(systemd_dir)}'",
                        "API_PORT_OVERRIDE='8110'",
                        "WS_PORT_OVERRIDE='9232'",
                        "RUNNER_HEALTH_PORT_OVERRIDE='18182'",
                        f"'{_wsl_path(script)}'",
                        "lane-02",
                        "flow-account-02",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        assert result.returncode == 0, result.stderr

        lane_env = (deploy_root / "env" / "lane.env").read_text(encoding="utf-8")
        assert "LANE_ID=lane-02" in lane_env
        assert "FLOW_ACCOUNT_ALIAS=flow-account-02" in lane_env
        assert f"FLOWKIT_ROOT={_wsl_path(deploy_root)}" in lane_env
        assert "API_PORT=8110" in lane_env
        assert "WS_PORT=9232" in lane_env
        assert "RUNNER_HEALTH_PORT=18182" in lane_env
        assert (deploy_root / "docker-compose.worker.yml").exists()
        assert (deploy_root / "Dockerfile.worker").exists()

        agent_service = (systemd_dir / "flowkit-agent-lane-02.service").read_text(encoding="utf-8")
        assert _wsl_path(deploy_root) in agent_service


def test_worker_compose_runs_containers_as_host_user():
    compose_file = Path(__file__).resolve().parents[1] / "docker-compose.worker.yml"

    content = compose_file.read_text(encoding="utf-8")

    assert 'user: "${FLOWKIT_UID:-1000}:${FLOWKIT_GID:-1000}"' in content


def test_bootstrap_lane_script_copies_app_source_when_provided():
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-lane.sh"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        deploy_root = root / "flowkit-worker-demo-lane-02"
        systemd_dir = root / "systemd"
        systemd_dir.mkdir()
        app_source = root / "app-source"
        (app_source / "agent").mkdir(parents=True)
        (app_source / "agent" / "__init__.py").write_text("", encoding="utf-8")
        (app_source / "agent" / "main.py").write_text("print('agent main')\n", encoding="utf-8")
        (app_source / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

        env = os.environ.copy()
        env.update(
            {
                "DEPLOY_ROOT": _wsl_path(deploy_root),
                "APP_SOURCE": _wsl_path(app_source),
                "SUDO_BIN": "",
                "SYSTEMCTL_BIN": "true",
                "SYSTEMD_DIR": _wsl_path(systemd_dir),
            }
        )

        result = subprocess.run(
            [
                "bash",
                "-lc",
                " ".join(
                    [
                        f"DEPLOY_ROOT='{_wsl_path(deploy_root)}'",
                        f"APP_SOURCE='{_wsl_path(app_source)}'",
                        "SUDO_BIN=''",
                        "SYSTEMCTL_BIN='true'",
                        f"SYSTEMD_DIR='{_wsl_path(systemd_dir)}'",
                        f"'{_wsl_path(script)}'",
                        "lane-02",
                        "flow-account-02",
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        assert (deploy_root / "app" / "agent" / "main.py").exists()
        assert (deploy_root / "app" / "requirements.txt").exists()
