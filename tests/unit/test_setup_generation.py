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


def test_generate_gemini_md_writes_fbkit_safety_first_root_instructions(tmp_path, monkeypatch):
    setup_mod = _load_setup_module()
    gemini_md = tmp_path / "GEMINI.md"
    monkeypatch.setattr(setup_mod, "GEMINI_MD", gemini_md)

    setup_mod.generate_gemini_md([])

    content = gemini_md.read_text(encoding="utf-8")
    assert "FBKit / FlowKit" in content
    assert "LIVE_ACTIONS_ENABLED=false" in content
    assert "Do not trigger, approve, or enable real Facebook/social actions" in content
    assert "Google Flow" not in content


def test_setup_source_does_not_keep_stale_google_flow_root_templates():
    setup_path = Path(__file__).resolve().parents[2] / "setup.py"
    source = setup_path.read_text(encoding="utf-8")

    assert "_CRITICAL_RULES" not in source
    assert "_PIPELINE_OVERVIEW" not in source
    assert "_BATCH_API" not in source
    assert "/api/requests/batch" not in source
    assert "Media ID is always UUID" not in source
    assert "Image Material required" not in source
    assert "Google Flow" not in source
