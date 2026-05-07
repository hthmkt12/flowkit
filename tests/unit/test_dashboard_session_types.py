from pathlib import Path


DASHBOARD_SRC = Path(__file__).resolve().parents[2] / "dashboard" / "src"


def test_dashboard_extension_session_type_includes_phase3_health_fields():
    source = (DASHBOARD_SRC / "types" / "index.ts").read_text(encoding="utf-8")

    for field in [
        "extension_live_actions_enabled",
        "profile_id",
        "profile_name",
        "last_seen_age_s",
        "stale",
        "health",
    ]:
        assert field in source


def test_safety_gate_status_counts_only_non_stale_logged_in_sessions():
    source = (DASHBOARD_SRC / "components" / "SafetyGateStatus.tsx").read_text(encoding="utf-8")

    assert "!session.stale" in source
    assert "session.health !== 'stale'" in source or "!session.stale" in source


def test_safety_gate_status_connectivity_uses_fresh_sessions_not_raw_socket_state():
    source = (DASHBOARD_SRC / "components" / "SafetyGateStatus.tsx").read_text(encoding="utf-8")

    assert "const freshSessions" in source
    assert "const connected = freshSessions > 0" in source
