"""FBKit — Default Strategy Seeder.

Pre-populates the task_strategy table with known-good Facebook 2024 selectors
extracted from content-fb.js. This gives the system a baseline to work from
on first run, rather than starting with zero knowledge.

Run once at startup or manually via: python -m agent.db.seed_strategies
"""
import asyncio
import logging

from agent.db.schema import init_db
from agent.db import crud

logger = logging.getLogger(__name__)

# ─── Known-Good Facebook 2024 Selectors ────────────────────
# Extracted from content-fb.js — the ground truth for each action.

DEFAULT_STRATEGIES = [
    {
        "task_type": "LIKE_POST",
        "selectors": {
            "likeBtn": 'div[aria-label="Like"][aria-pressed]',
            "likeBtnVi": 'div[aria-label="Thích"][aria-pressed]',
            "likeBtnFallback": 'div[aria-label="Like"]',
            "likeBtnViFallback": 'div[aria-label="Thích"]',
            "reactionBar": 'div[data-testid="like_def"]',
        },
        "wait_strategies": [
            {"step": "page_load", "wait_ms": 3500},
            {"step": "reaction_hover", "wait_ms": 2000, "note": "Hold hover to reveal reaction bar"},
            {"step": "after_click", "wait_ms": 1500},
        ],
        "notes": "FB 2024: Like button uses aria-pressed attribute to indicate state. Check aria-pressed='true' before clicking to avoid toggle-off.",
    },
    {
        "task_type": "COMMENT_POST",
        "selectors": {
            "commentTrigger": 'div[aria-label="Leave a comment"]',
            "commentTriggerVi": 'div[aria-label="Để lại bình luận"]',
            "commentInput": 'div[aria-label="Write a comment"][contenteditable="true"]',
            "commentInputAlt": 'div[aria-label="Write a comment…"][contenteditable="true"]',
            "commentInputVi": 'div[aria-label="Viết bình luận"][contenteditable="true"]',
            "commentInputLexical": 'div[data-lexical-editor="true"][contenteditable="true"]',
            "commentInputFallback": 'div[contenteditable="true"][role="textbox"]',
        },
        "wait_strategies": [
            {"step": "page_load", "wait_ms": 3500},
            {"step": "trigger_expand", "wait_ms": 1200},
            {"step": "before_type", "wait_ms": 500},
            {"step": "after_type", "wait_ms": 1000},
        ],
        "notes": "FB 2024: Comment requires clicking trigger first to expand. Uses contenteditable divs, not textarea. Submit via Enter key.",
    },
    {
        "task_type": "SHARE_POST",
        "selectors": {
            "shareBtn": 'div[aria-label="Share"][role="button"]',
            "shareBtnVi": 'div[aria-label="Chia sẻ"][role="button"]',
            "shareMenu": 'div[role="menuitem"]',
        },
        "wait_strategies": [
            {"step": "page_load", "wait_ms": 3500},
            {"step": "menu_open", "wait_ms": 1500},
            {"step": "after_select", "wait_ms": 2000},
        ],
        "workarounds": [
            {"error": "Share menu did not open", "fix": "Try clicking share button again with longer delay, FB may lazy-load the menu"},
        ],
        "notes": "FB 2024: Share opens a menuitem-based dropdown. Look for 'Share to Feed' or 'Share now' options.",
    },
    {
        "task_type": "POST_TEXT",
        "selectors": {
            "composer": '[aria-label="Create a post"]',
            "composerAlt": '[aria-label="What\'s on your mind?"]',
            "textArea": 'div[contenteditable="true"][role="textbox"]',
            "textAreaLexical": 'div[data-lexical-editor="true"]',
            "postBtn": 'div[aria-label="Post"]',
            "postBtnVi": 'div[aria-label="Đăng"]',
        },
        "wait_strategies": [
            {"step": "composer_click", "wait_ms": 1500},
            {"step": "after_type", "wait_ms": 2000},
            {"step": "after_submit", "wait_ms": 3000},
        ],
        "notes": "FB 2024: Composer may be a simple div[role=button] that expands into a dialog with contenteditable textbox.",
    },
    {
        "task_type": "POST_REEL",
        "selectors": {
            "fileInput": 'input[type="file"][accept*="video"]',
            "fileInputFallback": 'input[type="file"]',
            "reelBtn": 'div[aria-label="Create a Reel"]',
            "reelBtnVi": 'div[aria-label="Tạo thước phim"]',
            "nextBtn": 'div[aria-label="Next"]',
            "nextBtnVi": 'div[aria-label="Tiếp"]',
            "publishBtn": 'div[aria-label="Publish"]',
            "publishBtnVi": 'div[aria-label="Đăng"]',
        },
        "wait_strategies": [
            {"step": "page_load", "wait_ms": 5000},
            {"step": "video_processing", "wait_ms": 12000},
            {"step": "after_next", "wait_ms": 3000},
            {"step": "after_publish", "wait_ms": 6000},
        ],
        "workarounds": [
            {"error": "Could not find file input for Reel upload", "fix": "Ensure reels/create URL loaded. Try refreshing page."},
            {"error": "Could not find Reel creation button", "fix": "Navigate directly to /reels/create URL instead of looking for button."},
        ],
        "notes": "FB 2024: Reel upload uses chrome.debugger for file input. Allow extra time for video processing.",
    },
    {
        "task_type": "SEND_MESSAGE",
        "selectors": {
            "msgInput": 'div[aria-label="Message"][contenteditable="true"]',
            "msgInputAlt": 'div[role="textbox"][contenteditable="true"]',
            "msgInputVi": 'div[aria-label="Aa"][contenteditable="true"]',
            "searchInput": 'input[aria-label="To"]',
            "suggestion": 'ul[role="listbox"] li',
            "suggestionAlt": 'div[role="option"]',
        },
        "wait_strategies": [
            {"step": "page_load", "wait_ms": 3000},
            {"step": "search_results", "wait_ms": 2000},
            {"step": "after_send", "wait_ms": 1500},
        ],
        "notes": "Navigate to /messages/t/{uid} for direct messaging, /messages/new for search-based. Submit via Enter key.",
    },
    {
        "task_type": "ADD_FRIEND",
        "selectors": {
            "addBtn": 'div[aria-label="Add friend"]',
            "addBtnAlt": 'div[aria-label="Add Friend"]',
            "addBtnVi": 'div[aria-label="Thêm bạn bè"]',
            "addBtnViAlt": 'div[aria-label="Kết bạn"]',
        },
        "wait_strategies": [
            {"step": "page_load", "wait_ms": 3000},
            {"step": "after_click", "wait_ms": 1500},
        ],
        "notes": "Check if already friends before sending request.",
    },
    {
        "task_type": "ACCEPT_FRIEND",
        "selectors": {
            "confirmBtn": 'div[aria-label="Confirm"]',
            "confirmBtnVi": 'div[aria-label="Xác nhận"]',
        },
        "wait_strategies": [
            {"step": "page_load", "wait_ms": 3000, "note": "Navigate to /friends/requests first"},
            {"step": "after_click", "wait_ms": 1500},
        ],
        "notes": "Navigate to /friends/requests then click first Confirm button.",
    },
    {
        "task_type": "CHECK_LOGIN",
        "selectors": {
            "profileLink": '[aria-label="Your profile"]',
            "accountMenu": '[aria-label="Account"]',
            "profileBrowser": '[data-pagelet="ProfileBrowser"]',
        },
        "notes": "Quick login check — no interaction needed, just verify any of these selectors exist.",
    },
]


async def seed_default_strategies():
    """Seed the database with default known-good strategies.

    Only creates strategies that don't already exist (won't overwrite
    user-customized or learned strategies).
    """
    count = 0
    for s in DEFAULT_STRATEGIES:
        existing = await crud.get_strategy(s["task_type"], s.get("url_pattern", "*"))
        if existing:
            logger.debug("Strategy for %s already exists, skipping", s["task_type"])
            continue

        await crud.upsert_strategy(
            task_type=s["task_type"],
            url_pattern=s.get("url_pattern", "*"),
            selectors=s.get("selectors"),
            wait_strategies=s.get("wait_strategies"),
            workarounds=s.get("workarounds"),
            notes=s.get("notes"),
        )
        count += 1
        logger.info("Seeded strategy: %s", s["task_type"])

    logger.info("Seeded %d/%d default strategies", count, len(DEFAULT_STRATEGIES))
    return count


async def main():
    await init_db()
    count = await seed_default_strategies()
    print(f"✅ Seeded {count} default strategies")


if __name__ == "__main__":
    asyncio.run(main())
