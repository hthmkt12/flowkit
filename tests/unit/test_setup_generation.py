"""Tests for AI tool setup generation."""

import importlib.util
from pathlib import Path


def _load_setup_module():
    setup_path = Path(__file__).resolve().parents[2] / "setup.py"
    spec = importlib.util.spec_from_file_location("fbkit_setup", setup_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_codex_writes_fbkit_safety_first_root_instructions(tmp_path, monkeypatch):
    setup_mod = _load_setup_module()
    agents_md = tmp_path / "AGENTS.md"
    monkeypatch.setattr(setup_mod, "AGENTS_MD", agents_md)

    setup_mod.generate_codex([])

    content = agents_md.read_text(encoding="utf-8")
    assert "FBKit / FlowKit" in content
    assert "LIVE_ACTIONS_ENABLED=false" in content
    assert "Do not trigger, approve, or enable real Facebook/social actions" in content
    assert "Google Flow" not in content
    assert "/fk:" not in content
