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


def test_dry_run_helpers_return_structured_result_fields():
    source = _source()

    assert "function isDryRun(params)" in source
    assert "function dryRunResult(" in source
    for field in ["dryRun", "wouldClick", "elementFound", "selectorUsed", "url"]:
        assert field in source


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
