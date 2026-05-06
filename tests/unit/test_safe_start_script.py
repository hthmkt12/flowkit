"""Tests for the safe Windows FBKit startup helper."""

from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "start-fbkit-safe.ps1"
README_PATH = Path(__file__).resolve().parents[2] / "README.md"


def test_safe_start_script_sets_safe_environment_defaults():
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    assert '$env:LIVE_ACTIONS_ENABLED = "false"' in content
    assert '$env:DRY_RUN_DEFAULT = "true"' in content
    assert '$env:APPROVAL_REQUIRED = "true"' in content
    assert '$env:API_AUTH_ENABLED = "false"' in content
    assert '$env:WS_AUTH_ENABLED = "false"' in content
    assert "LIVE_ACTIONS_ENABLED=true" not in content


def test_safe_start_script_has_print_only_mode_and_uses_repo_venv():
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "[switch]$PrintOnly" in content
    assert ".venv" in content
    assert "Scripts" in content
    assert "python.exe" in content
    assert "-m" in content
    assert "agent.main" in content


def test_readme_mentions_safe_start_helper():
    content = README_PATH.read_text(encoding="utf-8")

    assert "scripts/start-fbkit-safe.ps1" in content
    assert "-PrintOnly" in content
