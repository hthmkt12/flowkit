"""Tests for ZooPost agent env setup script safety checks."""

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "zoopost-agent-env-setup.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("zoopost_agent_env_setup", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "cloud_url",
    [
        "https://cloud.example",
        "http://localhost:8200",
        "http://127.0.0.1:8200",
        "http://[::1]:8200",
    ],
)
def test_secure_cloud_url_check_allows_tls_and_loopback_http(cloud_url):
    script = _load_script()

    script.require_secure_cloud_url(cloud_url)


@pytest.mark.parametrize("cloud_url", ["http://cloud.example", "ws://cloud.example", "wss://cloud.example"])
def test_secure_cloud_url_check_rejects_plaintext_remote_or_non_http_url(cloud_url):
    script = _load_script()

    with pytest.raises(SystemExit, match="Refusing unsupported or plaintext remote"):
        script.require_secure_cloud_url(cloud_url)


def test_exchange_token_rejects_plaintext_remote_before_network(monkeypatch):
    script = _load_script()

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("urlopen must not be called for plaintext remote URLs")

    monkeypatch.setattr(script.urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(SystemExit, match="Refusing unsupported or plaintext remote"):
        script.exchange_token("http://cloud.example", "install-1", "registration-secret", "bearer-secret")
