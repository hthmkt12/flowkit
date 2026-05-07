"""Static checks for FBKit rollout gate documentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROLLOUT_DOC = ROOT / "docs" / "rollout-gates.md"
README = ROOT / "README.md"
ROADMAP = ROOT / "docs" / "project-roadmap.md"


def test_rollout_gates_doc_exists_and_defines_progression_gates():
    content = ROLLOUT_DOC.read_text(encoding="utf-8")

    for required in [
        "Gate 0: Local dry-run",
        "Gate 1: One dedicated test account",
        "Gate 2: Two-profile dry-run pilot",
        "Gate 3: Five-profile dry-run pilot",
        "Gate 4: Ten-profile dry-run pilot",
        "Gate 5: Distributed readiness review",
    ]:
        assert required in content


def test_rollout_gates_doc_keeps_live_actions_and_main_account_guardrails():
    content = ROLLOUT_DOC.read_text(encoding="utf-8")

    for required in [
        "Do not use a main Facebook account",
        "LIVE_ACTIONS_ENABLED=false",
        "DRY_RUN_DEFAULT=true",
        "APPROVAL_REQUIRED=true",
        "API_AUTH_ENABLED=true",
        "WS_AUTH_ENABLED=true",
        "EXTENSION_LIVE_ACTIONS_ENABLED=false",
        "No 50-account support is validated",
    ]:
        assert required in content


def test_rollout_gates_doc_covers_phase4_operational_limits():
    content = ROLLOUT_DOC.read_text(encoding="utf-8")

    for required in [
        "FBKIT_NODE_ID",
        "LIVE_ACCOUNT_LEASE_TTL_SECONDS",
        "lease heartbeat refresh is not implemented",
        "`/api/status` exposes operational metadata",
    ]:
        assert required in content


def test_readme_and_roadmap_link_rollout_gates_doc():
    readme = README.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")

    assert "docs/rollout-gates.md" in readme
    assert "rollout-gates.md" in roadmap
