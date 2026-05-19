from pathlib import Path


POPUP_SCRIPT = Path(__file__).resolve().parents[2] / "extension" / "popup.js"


def _source() -> str:
    return POPUP_SCRIPT.read_text(encoding="utf-8")


def test_popup_reads_only_local_agent_status_and_pending_count():
    source = _source()

    assert "const AGENT_API = \"http://127.0.0.1:8100\";" in source
    assert "`${AGENT_API}/api/status`" in source
    assert "`${AGENT_API}/api/tasks/pending/count`" in source
    assert "fetch(`${AGENT_API}/api/status`," in source
    assert "fetch(`${AGENT_API}/api/tasks/pending/count`," in source
    assert "fetch(`${AGENT_API}/api/status`, {\n      signal: AbortSignal.timeout(3000),\n      headers,\n    })" in source
    assert "fetch(`${AGENT_API}/api/tasks/pending/count`, {\n          signal: AbortSignal.timeout(3000),\n          headers,\n        })" in source
    assert "/api/tasks" not in source.replace("/api/tasks/pending/count", "")
    assert "ZOOPOST" not in source


def test_popup_uses_local_api_key_only_for_local_agent_requests():
    source = _source()

    assert "chrome.storage.local.get([\"fbkitApiKey\"])" in source
    assert "\"X-API-Key\": apiKey" in source
    assert "headers," in source
    assert "Authorization" not in source
    assert "registration_token" not in source
    assert "credential" not in source.lower()


def test_popup_checks_facebook_page_state_without_mutating_messages():
    source = _source()

    assert "chrome.tabs.query" in source
    assert "https://www.facebook.com/*" in source
    assert "https://web.facebook.com/*" in source
    assert "chrome.tabs.sendMessage" in source
    assert 'method: "get_page_state"' in source
    for mutating_method in [
        "post_text",
        "post_with_media",
        "send_message",
        "like_post",
        "comment_post",
        "share_post",
        "add_friend",
        "accept_friend",
        "join_group",
        "leave_group",
        "follow_page",
        "unfollow_page",
    ]:
        assert mutating_method not in source


def test_popup_has_safe_empty_and_unavailable_states():
    source = _source()

    assert "No FB Tab" in source
    assert "No Content Script" in source
    assert "Not Logged In" in source
    assert "Agent unreachable:" in source
    assert "Offline" in source
    assert "Unknown" in source


def test_popup_dashboard_button_opens_only_local_agent_docs():
    source = _source()

    assert "btn-dashboard" in source
    assert "chrome.tabs.create({ url: `${AGENT_API}/docs` })" in source
    assert "http://" not in source.replace("http://127.0.0.1:8100", "")
    assert "https://" not in source.replace("https://www.facebook.com/*", "").replace("https://web.facebook.com/*", "")
