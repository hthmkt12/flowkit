"""UTC time helpers that preserve FBKit's existing naive ISO storage format."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime for legacy SQLite fields."""
    return datetime.now(UTC).replace(tzinfo=None)


def utc_now_iso() -> str:
    """Return current UTC time as a naive ISO string."""
    return utc_now().isoformat()


def utc_now_ms() -> int:
    """Return current UTC epoch time in milliseconds."""
    return int(datetime.now(UTC).timestamp() * 1000)


def utc_from_timestamp_iso(timestamp: float) -> str:
    """Return a UTC timestamp as a naive ISO string."""
    return datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None).isoformat()
