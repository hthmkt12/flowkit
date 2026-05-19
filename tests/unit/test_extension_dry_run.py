import re
from pathlib import Path


EXTENSION_SCRIPT = (
    Path(__file__).resolve().parents[2] / "extension" / "content-fb.js"
)


MUTATING_HANDLERS = [
    "handlePostText",
    "handleSendMessage",
    "handleLikePost",
    "handleCommentPost",
    "handleAddFriend",
    "handlePostWithMedia",
    "handleSharePost",
    "handleAcceptFriend",
    "handleJoinGroup",
    "handleLeaveGroup",
    "handleFollowPage",
    "handleUnfollowPage",
]


MUTATING_METHODS = [
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
]


READ_ONLY_METHODS = [
    "scrape_profile",
    "scrape_group",
    "scrape_live_comments",
    "get_page_state",
]


DANGEROUS_MARKERS = [
    "window.location.href",
    "await humanClick(",
    "await humanType(",
    "dispatchEvent(new KeyboardEvent",
    "chrome.runtime.sendMessage({",
]


def _source() -> str:
    return EXTENSION_SCRIPT.read_text(encoding="utf-8")


def _handler_body(source: str, handler_name: str) -> str:
    match = re.search(
        rf"async function {handler_name}\(params\) \{{(?P<body>.*?)\n\}}\n\n/\*\*",
        source,
        re.DOTALL,
    )
    assert match, f"Could not extract {handler_name} body"
    return match.group("body")


def _router_body(source: str) -> str:
    match = re.search(
        r"chrome\.runtime\.onMessage\.addListener\(\(message, sender, sendResponse\) => \{(?P<body>.*?)\n\}\);",
        source,
        re.DOTALL,
    )
    assert match, "Could not extract message router body"
    return match.group("body")


def test_dry_run_helpers_return_structured_result_fields():
    source = _source()

    assert "function isDryRun(params)" in source
    assert "function dryRunResult(" in source
    for field in ["dryRun", "wouldClick", "elementFound", "selectorUsed", "url", "safetyReason"]:
        assert field in source


def test_extension_live_actions_disabled_by_default():
    source = _source()

    assert "const EXTENSION_LIVE_ACTIONS_ENABLED = false;" in source
    assert "function shouldForceExtensionDryRun(params)" in source
    assert "!EXTENSION_LIVE_ACTIONS_ENABLED" in source


def test_background_reports_extension_live_guard_state():
    background = (EXTENSION_SCRIPT.parent / "background.js").read_text(encoding="utf-8")

    assert "const EXTENSION_LIVE_ACTIONS_ENABLED = false;" in background
    assert "extensionLiveActionsEnabled: EXTENSION_LIVE_ACTIONS_ENABLED" in background


def test_background_connects_when_service_worker_loads():
    background = (EXTENSION_SCRIPT.parent / "background.js").read_text(encoding="utf-8")

    startup_index = background.index("chrome.runtime.onStartup.addListener")
    storage_index = background.index("chrome.storage.onChanged.addListener")
    load_connect_index = background.index("connectWS();", startup_index + 1)
    assert startup_index < load_connect_index < storage_index


def test_background_reports_profile_identity_and_heartbeat():
    background = (EXTENSION_SCRIPT.parent / "background.js").read_text(encoding="utf-8")

    assert "async function getProfileIdentity()" in background
    assert "const currentFbUid = await getFbUid();" in background
    assert "fb_uid: currentFbUid" in background
    assert "loggedIn: !!currentFbUid" in background
    assert "profileId:" in background
    assert "profileName:" in background
    assert 'type: "ping"' in background
    assert "profileIdentity" in background


def test_background_refuses_dispatch_when_expected_fb_uid_changes():
    background = (EXTENSION_SCRIPT.parent / "background.js").read_text(encoding="utf-8")

    assert "params?.expectedFbUid" in background
    assert "currentFbUid !== params.expectedFbUid" in background
    assert "Facebook account changed before dispatch" in background


def test_router_defines_mutating_methods_separately_from_read_only_methods():
    source = _source()

    assert "const MUTATING_METHODS = new Set([" in source
    for method in MUTATING_METHODS:
        assert f'"{method}"' in source
    for method in READ_ONLY_METHODS:
        assert f'"{method}"' not in source.split("const MUTATING_METHODS = new Set([")[1].split("]);", 1)[0]


def test_router_forces_extension_dry_run_before_dispatching_mutating_methods():
    source = _source()
    body = _router_body(source)

    router_guard_index = body.find("MUTATING_METHODS.has(method) && shouldForceExtensionDryRun(params)")
    assert router_guard_index != -1, "router does not force dry-run for mutating methods"

    for method in MUTATING_METHODS:
        dispatch_index = body.find(f'case "{method}":')
        assert dispatch_index != -1, f"router does not dispatch {method}"
        assert router_guard_index < dispatch_index, f"router guard appears after {method} dispatch"


def test_mutating_handlers_check_dry_run_before_dangerous_dom_actions():
    source = _source()

    for handler_name in MUTATING_HANDLERS:
        body = _handler_body(source, handler_name)
        dry_run_index = body.find("isDryRun(params)")
        assert dry_run_index != -1, f"{handler_name} does not check dryRun"

        dangerous_indexes = [
            index
            for marker in DANGEROUS_MARKERS
            if (index := body.find(marker)) != -1
        ]
        assert dangerous_indexes, f"{handler_name} has no tracked dangerous action"
        first_dangerous_index = min(dangerous_indexes)
        assert dry_run_index < first_dangerous_index, (
            f"{handler_name} checks dryRun after a dangerous DOM action"
        )


def test_mutating_handlers_check_extension_live_guard_before_dangerous_dom_actions():
    source = _source()

    for handler_name in MUTATING_HANDLERS:
        body = _handler_body(source, handler_name)
        guard_index = body.find("shouldForceExtensionDryRun(params)")
        assert guard_index != -1, f"{handler_name} does not check extension live guard"

        dangerous_indexes = [
            index
            for marker in DANGEROUS_MARKERS
            if (index := body.find(marker)) != -1
        ]
        assert dangerous_indexes, f"{handler_name} has no tracked dangerous action"
        first_dangerous_index = min(dangerous_indexes)
        assert guard_index < first_dangerous_index, (
            f"{handler_name} checks extension live guard after a dangerous DOM action"
        )
