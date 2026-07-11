"""Static security assertions for demo tunnel PowerShell scripts.

These tests do not execute PowerShell; they parse the scripts and the
vite config to prove the public tunnel cannot target a dynamic API/WS
proxy and that no Cloud bearer is injected into the browser path.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT.parent / "scripts"
TUNNEL_START = SCRIPTS_DIR / "demo-sales-local-pilot-tunnel-start.ps1"
TUNNEL_DASH = SCRIPTS_DIR / "demo-sales-local-pilot-tunnel-dashboard-start.ps1"
VITE_CONFIG = REPO_ROOT / "dashboard" / "vite.config.ts"
CLIENT_TS = REPO_ROOT / "dashboard" / "src" / "api" / "client.ts"
USE_WEBSOCKET_TS = REPO_ROOT / "dashboard" / "src" / "api" / "useWebSocket.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_vite_config_rejects_bearer_env():
    source = _read(VITE_CONFIG)
    assert "ZOOPOST_CLOUD_DEV_BEARER_TOKEN" in source
    assert "dashboardProxyBearerSubprotocol" not in source
    # No Authorization header injection remains.
    assert "Authorization" not in source


def test_vite_config_binds_loopback():
    source = _read(VITE_CONFIG)
    assert "host: '127.0.0.1'" in source
    assert "loopback" in source.lower()


def test_client_ts_has_no_bearer_storage():
    source = _read(CLIENT_TS)
    assert "zoopostBearerToken" not in source
    assert "getZooPostBearerToken" not in source
    assert "Authorization" not in source
    assert "localStorage" not in re.sub(r'(?m)^\s*//.*$', '', source)
    assert "sessionStorage" not in re.sub(r'(?m)^\s*//.*$', '', source)


def test_use_websocket_has_no_bearer_subprotocol():
    source = _read(USE_WEBSOCKET_TS)
    assert "getZooPostBearerToken" not in source
    assert "bearer.b64" not in source
    assert "dashboardWebSocketProtocols" not in source


def test_tunnel_start_refuses_dev_server_and_tokens():
    source = _read(TUNNEL_START)
    assert "5173" in source
    assert "ZOOPOST_CLOUD_DEV_BEARER_TOKEN" in source
    assert "loopback" in source.lower()
    # Default target must be the static server, not port 5173.
    assert re.search(r"DashboardUrl\s*=\s*\"http://127\.0\.0\.1:3000\"", source)


def test_tunnel_dashboard_start_is_static_only():
    source = _read(TUNNEL_DASH)
    assert "npm run build" in source
    assert "npx serve" in source
    assert "ZOOPOST_CLOUD_DEV_BEARER_TOKEN" in source
    assert "npm run dev" not in source
    # No Vite proxy table in the static server invocation.
    assert "proxy:" not in source
    assert "configureServer" not in source


def test_no_bearer_canary_in_dashboard_source():
    dashboard_src = REPO_ROOT / "dashboard" / "src"
    if not dashboard_src.exists():
        pytest.skip("dashboard src not found")
    offenders = []
    for path in dashboard_src.rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "zoopostBearerToken" in text or "getZooPostBearerToken" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    for path in dashboard_src.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "zoopostBearerToken" in text or "getZooPostBearerToken" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    # Test files may reference the string to assert its absence; allow
    # only inside *.test.* files.
    real = [p for p in offenders if ".test." not in p]
    assert not real, f"bearer storage references remain in: {real}"
