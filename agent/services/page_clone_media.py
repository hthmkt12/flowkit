"""Bounded, allowlisted Page Clone image caching."""

from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlsplit

import httpx

from agent.config import MEDIA_DIR

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_VIDEO_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
_ALLOWED_SUFFIXES = (".facebook.com", ".fbcdn.net", ".fbsbx.com")


def _image_extension(body: bytes) -> str | None:
    if body.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if body.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return ".webp"
    return None


def _video_extension(body: bytes) -> str | None:
    return ".mp4" if len(body) >= 12 and body[4:8] == b"ftyp" else None


def _allowed_media_url(value: object) -> str | None:
    try:
        parsed = urlsplit(str(value))
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        return None
    if host != "facebook.com" and not host.endswith(_ALLOWED_SUFFIXES):
        return None
    return parsed.geturl()


async def cache_page_clone_media(result: dict, task_id: str) -> dict:
    """Download bounded image media without following redirects or arbitrary hosts."""
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    posts = data.get("posts") if isinstance(data, dict) else None
    if not isinstance(posts, list):
        return result

    root = Path(MEDIA_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    warnings = data.setdefault("warnings", []) if isinstance(data, dict) else []
    async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
        for post_index, post in enumerate(posts[:25]):
            if not isinstance(post, dict) or not isinstance(post.get("media"), list):
                continue
            for media_index, item in enumerate(post["media"][:10]):
                if not isinstance(item, dict):
                    continue
                url = _allowed_media_url(item.get("url"))
                if not url:
                    warnings.append(f"media {post_index}:{media_index} rejected by host policy")
                    continue
                try:
                    async with client.stream("GET", url) as response:
                        if response.is_redirect or response.status_code >= 400:
                            raise ValueError("redirect or HTTP error")
                        content_type = (response.headers.get("content-type") or "").split(";", 1)[0].lower()
                        is_video = item.get("type") == "video"
                        expected_type = "video/" if is_video else "image/"
                        if not content_type.startswith(expected_type):
                            raise ValueError(f"media is not a {expected_type[:-1]}")
                        content_length = int(response.headers.get("content-length") or 0)
                        max_bytes = MAX_VIDEO_BYTES if is_video else MAX_IMAGE_BYTES
                        if content_length > max_bytes:
                            raise ValueError("media exceeds size limit")
                        chunks = []
                        received = 0
                        async for chunk in response.aiter_bytes():
                            received += len(chunk)
                            if received > max_bytes or total_bytes + received > MAX_TOTAL_BYTES:
                                raise ValueError("media cache size limit exceeded")
                            chunks.append(chunk)
                        body = b"".join(chunks)
                    extension = _video_extension(body) if is_video else _image_extension(body)
                    if not extension:
                        raise ValueError("media content does not match its declared type")
                    path = (root / f"page-clone-{task_id[:12]}-{post_index}-{media_index}{extension}").resolve()
                    path.relative_to(root)
                    path.write_bytes(body)
                    total_bytes += len(body)
                    item["local_path"] = str(path)
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    warnings.append(f"media {post_index}:{media_index} skipped: {exc}")
    return result


def cleanup_page_clone_media(task_id: str) -> int:
    """Remove only this task's bounded cache files after cancellation/failure."""
    safe_task_id = re.sub(r"[^A-Za-z0-9_-]", "", str(task_id))[:12]
    if not safe_task_id:
        return 0
    root = Path(MEDIA_DIR).resolve()
    removed = 0
    for path in root.glob(f"page-clone-{safe_task_id}-*"):
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
            if resolved.is_file():
                resolved.unlink()
                removed += 1
        except OSError:
            continue
    return removed
