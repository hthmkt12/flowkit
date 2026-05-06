"""FBKit — SQLite schema and connection management."""
import logging
import aiosqlite
from agent.config import DB_PATH

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None

SCHEMA = """
-- ─── Account (Facebook accounts) ────────────────────────────
CREATE TABLE IF NOT EXISTS account (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    fb_uid          TEXT,
    email           TEXT,
    status          TEXT DEFAULT 'ACTIVE'
                    CHECK(status IN ('ACTIVE','PAUSED','BANNED','LOGGED_OUT')),
    profile_url     TEXT,
    avatar_url      TEXT,
    cookies_valid   INTEGER DEFAULT 0,
    last_active     DATETIME,
    notes           TEXT,
    daily_posts     INTEGER DEFAULT 0,
    daily_messages  INTEGER DEFAULT 0,
    daily_likes     INTEGER DEFAULT 0,
    daily_comments  INTEGER DEFAULT 0,
    daily_friends   INTEGER DEFAULT 0,
    daily_reset_at  DATE,
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now')),
    cookies_data    TEXT,
    session_data    TEXT
);

-- ─── Post ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS post (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    post_type       TEXT NOT NULL DEFAULT 'TEXT'
                    CHECK(post_type IN ('TEXT','IMAGE','VIDEO','LINK','STORY','REEL')),
    content         TEXT,
    media_paths     TEXT,          -- JSON array of local file paths
    target_type     TEXT DEFAULT 'TIMELINE'
                    CHECK(target_type IN ('TIMELINE','GROUP','PAGE','STORY','REEL')),
    target_id       TEXT,          -- Group/Page FB ID
    target_name     TEXT,
    status          TEXT DEFAULT 'DRAFT'
                    CHECK(status IN ('DRAFT','SCHEDULED','POSTING','POSTED','FAILED')),
    scheduled_at    DATETIME,
    posted_at       DATETIME,
    fb_post_id      TEXT,
    fb_post_url     TEXT,
    error_message   TEXT,
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_post_account ON post(account_id);
CREATE INDEX IF NOT EXISTS idx_post_status ON post(status);
CREATE INDEX IF NOT EXISTS idx_post_scheduled ON post(scheduled_at);

-- ─── Message ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS message (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    recipient_name  TEXT NOT NULL,
    recipient_uid   TEXT,
    content         TEXT NOT NULL,
    media_path      TEXT,
    status          TEXT DEFAULT 'PENDING'
                    CHECK(status IN ('PENDING','SCHEDULED','SENDING','SENT','FAILED')),
    scheduled_at    DATETIME,
    sent_at         DATETIME,
    error_message   TEXT,
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_message_account ON message(account_id);
CREATE INDEX IF NOT EXISTS idx_message_status ON message(status);

-- ─── Task (FBKit job queue) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS task (
    id              TEXT PRIMARY KEY,
    account_id      TEXT REFERENCES account(id),
    task_type       TEXT NOT NULL CHECK(task_type IN (
        'POST_TEXT','POST_IMAGE','POST_VIDEO','POST_LINK',
        'POST_STORY','POST_REEL','REUP_VIDEO',
        'SEND_MESSAGE','SEND_BULK_MESSAGE',
        'LIKE_POST','COMMENT_POST','SHARE_POST',
        'ADD_FRIEND','ACCEPT_FRIEND',
        'JOIN_GROUP','LEAVE_GROUP',
        'FOLLOW_PAGE','UNFOLLOW_PAGE',
        'SCRAPE_PROFILE','SCRAPE_GROUP',
        'CHECK_LOGIN'
    )),
    payload         TEXT,          -- JSON payload
    ref_id          TEXT,          -- Reference to post/message/etc.
    status          TEXT DEFAULT 'PENDING'
                    CHECK(status IN ('PENDING','PROCESSING','COMPLETED','FAILED','CANCELLED')),
    priority        INTEGER DEFAULT 0,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    scheduled_at    DATETIME,
    started_at      DATETIME,
    completed_at    DATETIME,
    result          TEXT,          -- JSON result
    error_message   TEXT,
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_task_status ON task(status);
CREATE INDEX IF NOT EXISTS idx_task_type ON task(task_type);
CREATE INDEX IF NOT EXISTS idx_task_scheduled ON task(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_task_priority ON task(priority DESC);
CREATE INDEX IF NOT EXISTS idx_task_status_scheduled_priority ON task(status, scheduled_at, priority DESC);
CREATE INDEX IF NOT EXISTS idx_task_account_status ON task(account_id, status);

-- ─── FB Group ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fb_group (
    id              TEXT PRIMARY KEY,
    account_id      TEXT REFERENCES account(id) ON DELETE CASCADE,
    group_fb_id     TEXT,
    name            TEXT NOT NULL,
    url             TEXT,
    member_count    INTEGER,
    status          TEXT DEFAULT 'JOINED'
                    CHECK(status IN ('JOINED','LEFT','PENDING','BLOCKED')),
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_group_account ON fb_group(account_id);

-- ─── Activity Log (audit trail) ─────────────────────────────
CREATE TABLE IF NOT EXISTS activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      TEXT REFERENCES account(id),
    action          TEXT NOT NULL,
    detail          TEXT,
    created_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_activity_account ON activity_log(account_id);
CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_log(created_at);

-- ─── Spy Ad (competitor ad monitoring) ──────────────────────
CREATE TABLE IF NOT EXISTS spy_ad (
    id              TEXT PRIMARY KEY,
    target_id       TEXT NOT NULL,
    fb_ad_id        TEXT,
    page_name       TEXT,
    ad_text         TEXT,
    media_url       TEXT,
    ad_status       TEXT DEFAULT 'ACTIVE',
    first_seen      DATETIME DEFAULT (datetime('now')),
    last_seen       DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_spy_ad_target ON spy_ad(target_id);
CREATE INDEX IF NOT EXISTS idx_spy_ad_fb ON spy_ad(fb_ad_id);

-- ─── Scraped Data (group members, profile info, comments) ──
CREATE TABLE IF NOT EXISTS scraped_data (
    id              TEXT PRIMARY KEY,
    account_id      TEXT REFERENCES account(id),
    data_type       TEXT NOT NULL
                    CHECK(data_type IN ('GROUP_MEMBERS','PROFILE_INFO','LIVE_COMMENTS','POST_COMMENTS','PAGE_FOLLOWERS')),
    source_url      TEXT,
    source_id       TEXT,
    data            TEXT,          -- JSON blob
    item_count      INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_scraped_type ON scraped_data(data_type);
CREATE INDEX IF NOT EXISTS idx_scraped_source ON scraped_data(source_id);

-- ─── Seed Campaign (auto-engagement campaigns) ─────────────
CREATE TABLE IF NOT EXISTS seed_campaign (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    config          TEXT,          -- JSON config
    status          TEXT DEFAULT 'ACTIVE'
                    CHECK(status IN ('ACTIVE','PAUSED','COMPLETED','CANCELLED')),
    stats           TEXT,          -- JSON stats
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_seed_campaign_status ON seed_campaign(status);

-- ─── Task Strategy (learned automation patterns) ────────────
CREATE TABLE IF NOT EXISTS task_strategy (
    id              TEXT PRIMARY KEY,
    task_type       TEXT NOT NULL,
    url_pattern     TEXT DEFAULT '*',
    selectors       TEXT,          -- JSON: known-good CSS selectors
    wait_strategies TEXT,          -- JSON: timing/wait approaches
    workarounds     TEXT,          -- JSON: error workarounds
    success_count   INTEGER DEFAULT 0,
    fail_count      INTEGER DEFAULT 0,
    last_success    DATETIME,
    last_failure    DATETIME,
    notes           TEXT,          -- human-readable strategy notes
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_type_url ON task_strategy(task_type, url_pattern);
CREATE INDEX IF NOT EXISTS idx_strategy_type ON task_strategy(task_type);

-- ─── Task Trace (structured execution traces) ───────────────
CREATE TABLE IF NOT EXISTS task_trace (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT REFERENCES task(id) ON DELETE CASCADE,
    task_type       TEXT NOT NULL,
    account_id      TEXT,
    status          TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILURE')),
    duration_ms     INTEGER,
    steps           TEXT,          -- JSON: [{action, selector, result, timestamp}]
    error_detail    TEXT,
    strategy_id     TEXT REFERENCES task_strategy(id),
    created_at      DATETIME DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trace_task ON task_trace(task_id);
CREATE INDEX IF NOT EXISTS idx_trace_type ON task_trace(task_type);
CREATE INDEX IF NOT EXISTS idx_trace_status ON task_trace(status);

-- ─── Spy Target (competitor page/ad monitoring) ──────────────
CREATE TABLE IF NOT EXISTS spy_target (
    id              TEXT PRIMARY KEY,
    page_name       TEXT NOT NULL,
    page_id         TEXT NOT NULL,
    page_url        TEXT,
    check_interval  INTEGER DEFAULT 3600,
    last_checked    DATETIME,
    ads_found       INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'ACTIVE'
                    CHECK(status IN ('ACTIVE','PAUSED')),
    created_at      DATETIME DEFAULT (datetime('now')),
    updated_at      DATETIME DEFAULT (datetime('now'))
);
"""


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


_MIGRATIONS = [
    "ALTER TABLE account ADD COLUMN cookies_data TEXT",
    "ALTER TABLE account ADD COLUMN session_data TEXT",
    "CREATE INDEX IF NOT EXISTS idx_task_status_scheduled_priority ON task(status, scheduled_at, priority DESC)",
    "CREATE INDEX IF NOT EXISTS idx_task_account_status ON task(account_id, status)",
]


async def init_db():
    db = await get_db()
    await db.executescript(SCHEMA)

    for stmt in _MIGRATIONS:
        try:
            await db.execute(stmt)
        except Exception as exc:
            # Safe for re-run / legacy DBs where column/index already exists.
            logger.debug("Migration skipped (%s): %s", stmt, exc)

    await db.commit()
    logger.info("Database initialized: %s", DB_PATH)


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
        logger.info("Database closed")
