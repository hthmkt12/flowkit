"""Bounded Page Clone media cache tests use an in-process HTTP transport."""
import httpx
import pytest

from agent.services import page_clone_media


@pytest.mark.asyncio
async def test_media_cache_accepts_allowlisted_image_and_stays_under_media_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(page_clone_media, "MEDIA_DIR", str(tmp_path))

    def handler(request):
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"\xff\xd8\xffjpeg-bytes")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        page_clone_media.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await page_clone_media.cache_page_clone_media(
        {"data": {"posts": [{"media": [{"url": "https://scontent.xx.fbcdn.net/image.jpg"}]}]}},
        "task-media",
    )

    path = result["data"]["posts"][0]["media"][0]["local_path"]
    assert path.startswith(str(tmp_path))
    assert open(path, "rb").read() == b"\xff\xd8\xffjpeg-bytes"


@pytest.mark.asyncio
async def test_media_cache_rejects_redirects_and_untrusted_hosts(tmp_path, monkeypatch):
    monkeypatch.setattr(page_clone_media, "MEDIA_DIR", str(tmp_path))

    def handler(request):
        return httpx.Response(302, headers={"location": "https://evil.example/x"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        page_clone_media.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await page_clone_media.cache_page_clone_media(
        {"data": {"posts": [{"media": [
            {"url": "https://scontent.xx.fbcdn.net/image.jpg"},
            {"url": "https://evil.example/image.jpg"},
        ]}]}},
        "task-media",
    )

    assert "local_path" not in result["data"]["posts"][0]["media"][0]
    assert "local_path" not in result["data"]["posts"][0]["media"][1]
    assert len(result["data"]["warnings"]) == 2


@pytest.mark.asyncio
async def test_media_cache_rejects_fake_image_content_type(tmp_path, monkeypatch):
    monkeypatch.setattr(page_clone_media, "MEDIA_DIR", str(tmp_path))

    def handler(request):
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"not-an-image")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        page_clone_media.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await page_clone_media.cache_page_clone_media(
        {"data": {"posts": [{"media": [{"url": "https://scontent.xx.fbcdn.net/image.jpg"}]}]}},
        "task-media",
    )

    assert "local_path" not in result["data"]["posts"][0]["media"][0]
    assert "does not match" in result["data"]["warnings"][0]


@pytest.mark.asyncio
async def test_media_cache_accepts_allowlisted_mp4(tmp_path, monkeypatch):
    monkeypatch.setattr(page_clone_media, "MEDIA_DIR", str(tmp_path))

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "video/mp4"},
            content=b"\x00\x00\x00\x18ftypisomvideo-bytes",
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        page_clone_media.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await page_clone_media.cache_page_clone_media(
        {"data": {"posts": [{"media": [{
            "url": "https://scontent.xx.fbcdn.net/video.mp4", "type": "video"
        }]}]}},
        "task-video",
    )

    assert result["data"]["posts"][0]["media"][0]["local_path"].endswith(".mp4")


def test_media_cleanup_removes_only_matching_task_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(page_clone_media, "MEDIA_DIR", str(tmp_path))
    matching = tmp_path / "page-clone-task-media-0-0.jpg"
    other = tmp_path / "page-clone-other-task-0-0.jpg"
    matching.write_bytes(b"x")
    other.write_bytes(b"x")

    assert page_clone_media.cleanup_page_clone_media("task-media") == 1
    assert not matching.exists()
    assert other.exists()
