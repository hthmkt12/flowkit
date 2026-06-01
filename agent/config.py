"""FBKit — Configuration."""
import os
import socket


def _is_truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _clamped_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _csv(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or default


# ─── Server ──────────────────────────────────────────────────
API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "8100"))
WS_HOST = os.environ.get("WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("WS_PORT", "9222"))
CORS_ALLOWED_ORIGINS = _csv(
    os.environ.get("CORS_ALLOWED_ORIGINS"),
    ["http://127.0.0.1:5173", "http://localhost:5173"],
)

# ─── Security / Auth ─────────────────────────────────────────
API_AUTH_ENABLED = _is_truthy(os.environ.get("API_AUTH_ENABLED"), default=False)
API_KEY = os.environ.get("API_KEY", "")

# Extension WS auth (supports separate rotation if needed)
WS_AUTH_ENABLED = _is_truthy(os.environ.get("WS_AUTH_ENABLED"), default=API_AUTH_ENABLED)
WS_API_KEY = os.environ.get("WS_API_KEY", API_KEY)

# ─── Database & Storage ──────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "fbkit.db")
DATA_ENCRYPTION_KEY = os.environ.get("DATA_ENCRYPTION_KEY", API_KEY)
MEDIA_DIR = os.environ.get("MEDIA_DIR", "media")

# ─── Worker ──────────────────────────────────────────────────
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", "1"))  # Sequential by default
FBKIT_NODE_ID = os.environ.get("FBKIT_NODE_ID") or f"{socket.gethostname()}:{os.getpid()}"
LIVE_ACCOUNT_LEASE_TTL_SECONDS = _clamped_int(
    os.environ.get("LIVE_ACCOUNT_LEASE_TTL_SECONDS"),
    default=900,
    minimum=60,
    maximum=3600,
)
LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS = _clamped_int(
    os.environ.get("LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS"),
    default=60,
    minimum=5,
    maximum=300,
)

# ─── Safety Gate ──────────────────────────────────────────────
# Defaults protect personal accounts from accidental live mutations.
LIVE_ACTIONS_ENABLED = _is_truthy(os.environ.get("LIVE_ACTIONS_ENABLED"), default=False)
DRY_RUN_DEFAULT = _is_truthy(os.environ.get("DRY_RUN_DEFAULT"), default=True)
APPROVAL_REQUIRED = _is_truthy(os.environ.get("APPROVAL_REQUIRED"), default=True)

# ─── ZooPost Cloud Gateway ───────────────────────────────────
ZOOPOST_CLOUD_API_URL = os.environ.get("ZOOPOST_CLOUD_API_URL", "").strip()
ZOOPOST_AGENT_CREDENTIAL = os.environ.get("ZOOPOST_AGENT_CREDENTIAL", "").strip()
ZOOPOST_AGENT_INSTALLATION_ID = os.environ.get("ZOOPOST_AGENT_INSTALLATION_ID", "").strip()
ZOOPOST_GATEWAY_POLL_INTERVAL = _clamped_int(
    os.environ.get("ZOOPOST_GATEWAY_POLL_INTERVAL"),
    default=5,
    minimum=1,
    maximum=60,
)
ZOOPOST_GATEWAY_DISPATCH_LIMIT = _clamped_int(
    os.environ.get("ZOOPOST_GATEWAY_DISPATCH_LIMIT"),
    default=10,
    minimum=1,
    maximum=100,
)
ZOOPOST_GATEWAY_ACK_TIMEOUT = _clamped_int(
    os.environ.get("ZOOPOST_GATEWAY_ACK_TIMEOUT"),
    default=30,
    minimum=1,
    maximum=300,
)

# ─── Scheduler ───────────────────────────────────────────────
SCHEDULER_CHECK_INTERVAL = int(os.environ.get("SCHEDULER_CHECK_INTERVAL", "30"))  # seconds

# ─── Anti-Detection Delays (seconds) ────────────────────────
# Minimum and maximum random delays between actions
ACTION_DELAY_MIN = float(os.environ.get("ACTION_DELAY_MIN", "2.0"))
ACTION_DELAY_MAX = float(os.environ.get("ACTION_DELAY_MAX", "8.0"))

# Typing simulation delay per character (milliseconds)
TYPING_DELAY_MIN = int(os.environ.get("TYPING_DELAY_MIN", "40"))
TYPING_DELAY_MAX = int(os.environ.get("TYPING_DELAY_MAX", "150"))

# ─── Rate Limits (per account per day) ───────────────────────
RATE_LIMIT_POSTS_PER_DAY = int(os.environ.get("RATE_LIMIT_POSTS", "20"))
RATE_LIMIT_MESSAGES_PER_DAY = int(os.environ.get("RATE_LIMIT_MESSAGES", "50"))
RATE_LIMIT_LIKES_PER_DAY = int(os.environ.get("RATE_LIMIT_LIKES", "100"))
RATE_LIMIT_COMMENTS_PER_DAY = int(os.environ.get("RATE_LIMIT_COMMENTS", "50"))
RATE_LIMIT_FRIEND_REQUESTS_PER_DAY = int(os.environ.get("RATE_LIMIT_FRIENDS", "20"))

# ─── Session Limits ─────────────────────────────────────────
SESSION_ACTIVE_MIN = int(os.environ.get("SESSION_ACTIVE_MIN", "60"))  # minutes
SESSION_ACTIVE_MAX = int(os.environ.get("SESSION_ACTIVE_MAX", "180"))
SESSION_BREAK_MIN = int(os.environ.get("SESSION_BREAK_MIN", "15"))  # minutes
SESSION_BREAK_MAX = int(os.environ.get("SESSION_BREAK_MAX", "45"))

# ─── Facebook URLs ───────────────────────────────────────────
FB_BASE_URL = "https://www.facebook.com"
FB_MESSENGER_URL = "https://www.facebook.com/messages"
FB_MBASIC_URL = "https://mbasic.facebook.com"  # Fallback for simpler interactions

# ─── Telegram Notifications ─────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─── Spy Ads ─────────────────────────────────────────────────
SPY_ADS_CHECK_INTERVAL = int(os.environ.get("SPY_ADS_CHECK_INTERVAL", "3600"))  # seconds
