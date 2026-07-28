"""Contracts and redaction helpers for the read-only page-clone slice."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

from agent.config import MEDIA_DIR


MAX_POSTS = 25
MAX_CANDIDATES = 8
MAX_MEDIA_PER_POST = 10
MAX_DEADLINE_SECONDS = 30
MAX_TEXT_CHARS = 500

_ALLOWED_KEYS = {
    "source_url",
    "max_posts",
    "candidate_limit",
    "max_media_per_post",
    "deadline_seconds",
    "download_media",
}
_WIRE_KEYS = {
    "sourceUrl",
    "maxPosts",
    "candidateLimit",
    "maxMediaPerPost",
    "deadlineSeconds",
    "downloadMedia",
}
_RESERVED_PAGE_PATHS = {
    "groups",
    "watch",
    "reel",
    "reels",
    "posts",
    "events",
    "marketplace",
    "login",
    "share",
    "photo",
}


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def canonicalize_page_url(value: str) -> str:
    """Return a canonical HTTPS Facebook page URL or raise ``ValueError``."""

    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 2048:
        raise ValueError("source_url must be a non-empty string")
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https" or not (
        host == "facebook.com" or host.endswith(".facebook.com")
    ):
        raise ValueError("source_url must use an HTTPS Facebook host")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("source_url contains unsupported URL components")

    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise ValueError("source_url must identify a page")
    first = path_parts[0].lower()
    query = parse_qs(parsed.query, keep_blank_values=False)
    if first == "profile.php":
        page_id = query.get("id", [""])[0]
        if len(path_parts) != 1 or not page_id.isdigit() or len(page_id) < 5:
            raise ValueError("profile.php page URL requires a numeric id")
        return "https://www.facebook.com/profile.php?id=" + page_id
    if first in _RESERVED_PAGE_PATHS or len(path_parts) > 1 and first != "pages":
        raise ValueError("URL does not identify a Facebook page")
    if first == "pages":
        if len(path_parts) != 3 or not path_parts[2].isdigit() or len(path_parts[2]) < 5:
            raise ValueError("/pages URL requires a numeric page id")
        path = "/" + "/".join(path_parts)
    else:
        path = "/" + path_parts[0]
    return urlunsplit(("https", "www.facebook.com", path, "", ""))


def _bounded_int(payload: dict, key: str, default: int, maximum: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value < 1 or value > maximum:
        raise ValueError(f"{key} must be between 1 and {maximum}")
    return value


def normalize_page_clone_request(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("page-clone request must be an object")
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ValueError("unsupported page-clone fields: " + ", ".join(sorted(unknown)))
    download_media = payload.get("download_media", False)
    if not isinstance(download_media, bool):
        raise ValueError("download_media must be a boolean")
    return {
        "source_url": canonicalize_page_url(payload.get("source_url", "")),
        "max_posts": _bounded_int(payload, "max_posts", MAX_POSTS, MAX_POSTS),
        "candidate_limit": _bounded_int(payload, "candidate_limit", MAX_CANDIDATES, MAX_CANDIDATES),
        "max_media_per_post": _bounded_int(
            payload, "max_media_per_post", MAX_MEDIA_PER_POST, MAX_MEDIA_PER_POST
        ),
        "deadline_seconds": _bounded_int(
            payload, "deadline_seconds", MAX_DEADLINE_SECONDS, MAX_DEADLINE_SECONDS
        ),
        "download_media": download_media,
    }


def normalize_page_clone_task_payload(payload: dict) -> dict:
    """Validate the public camelCase task payload and return its canonical form."""
    if not isinstance(payload, dict):
        raise ValueError("page-clone task payload must be an object")
    unknown = set(payload) - _WIRE_KEYS
    if unknown:
        raise ValueError("unsupported page-clone fields: " + ", ".join(sorted(unknown)))
    request = normalize_page_clone_request({
        "source_url": payload.get("sourceUrl", ""),
        "max_posts": payload.get("maxPosts", MAX_POSTS),
        "candidate_limit": payload.get("candidateLimit", MAX_CANDIDATES),
        "max_media_per_post": payload.get("maxMediaPerPost", MAX_MEDIA_PER_POST),
        "deadline_seconds": payload.get("deadlineSeconds", MAX_DEADLINE_SECONDS),
        "download_media": payload.get("downloadMedia", False),
    })
    return {
        "sourceUrl": request["source_url"],
        "maxPosts": request["max_posts"],
        "candidateLimit": request["candidate_limit"],
        "maxMediaPerPost": request["max_media_per_post"],
        "deadlineSeconds": request["deadline_seconds"],
        "downloadMedia": request["download_media"],
    }


def redact_page_clone_task_payload(payload: dict) -> dict:
    """Replace a terminal task's raw source URL with a durable local reference."""
    raw_payload = payload if isinstance(payload, dict) else {}
    try:
        request = normalize_page_clone_task_payload(raw_payload)
    except ValueError:
        return {
            "schemaVersion": 1,
            "sourceRef": _hash(raw_payload.get("sourceUrl", "")),
        }
    return {
        "schemaVersion": 1,
        "sourceRef": _hash(request["sourceUrl"]),
        "maxPosts": request["maxPosts"],
        "candidateLimit": request["candidateLimit"],
        "maxMediaPerPost": request["maxMediaPerPost"],
        "deadlineSeconds": request["deadlineSeconds"],
    }


def _safe_text(value: object) -> str:
    return str(value or "")[:MAX_TEXT_CHARS]


def _safe_warnings(value: object) -> list[str]:
    """Keep bounded diagnostics while removing raw media URLs and query tokens."""
    if not isinstance(value, list):
        return []
    warnings = []
    for warning in value:
        if not isinstance(warning, str):
            continue
        warning = re.sub(r"https?://\S+", "[redacted URL]", warning).strip()
        if warning:
            warnings.append(warning[:MAX_TEXT_CHARS])
        if len(warnings) >= MAX_MEDIA_PER_POST:
            break
    return warnings


def redact_page_clone_result(result: dict) -> dict:
    """Create a durable, secret-free evidence representation."""

    if not isinstance(result, dict):
        raise ValueError("page-clone result must be an object")
    source_url = canonicalize_page_url(result.get("source_url", ""))
    profile = result.get("profile") if isinstance(result.get("profile"), dict) else {}
    redacted = {
        "schema_version": 1,
        "source_ref": _hash(source_url),
        "profile": {
            "id_hash": _hash(profile.get("id", "")),
            "name": _safe_text(profile.get("name")),
            "category": _safe_text(profile.get("category")),
        },
        "posts": [],
        "warnings": _safe_warnings(result.get("warnings")),
    }
    for post in result.get("posts", []) if isinstance(result.get("posts"), list) else []:
        if not isinstance(post, dict):
            continue
        media = []
        for item in post.get("media", []) if isinstance(post.get("media"), list) else []:
            if not isinstance(item, dict):
                continue
            parsed = urlsplit(str(item.get("url", "")))
            if parsed.scheme != "https" or not parsed.hostname:
                continue
            redacted_media = {
                    "host": parsed.hostname.lower(),
                    "url_hash": _hash(parsed.geturl()),
                    "type": _safe_text(item.get("type")),
            }
            local_path = item.get("local_path")
            if isinstance(local_path, str) and local_path:
                try:
                    media_root = Path(MEDIA_DIR).resolve()
                    safe_path = Path(local_path).resolve()
                    safe_path.relative_to(media_root)
                    redacted_media["media_path"] = str(safe_path)
                except (OSError, ValueError):
                    pass
            media.append(redacted_media)
            if len(media) >= MAX_MEDIA_PER_POST:
                break
        redacted["posts"].append(
            {
                "id_hash": _hash(post.get("id", "")),
                "message": _safe_text(post.get("message")),
                "created_time": _safe_text(post.get("created_time")),
                "media": media,
            }
        )
        if len(redacted["posts"]) >= MAX_POSTS:
            break
    return redacted
