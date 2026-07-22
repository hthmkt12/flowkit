import pytest

from agent.services.page_clone_contract import (
    MAX_CANDIDATES,
    MAX_MEDIA_PER_POST,
    MAX_POSTS,
    canonicalize_page_url,
    normalize_page_clone_request,
    redact_page_clone_result,
    redact_page_clone_task_payload,
)


def test_canonicalizes_supported_facebook_page_url():
    assert canonicalize_page_url("https://facebook.com/pages/Acme/123456789") == (
        "https://www.facebook.com/pages/Acme/123456789"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://facebook.com/groups/123",
        "https://facebook.com/watch/?v=123",
        "http://facebook.com/acme",
        "https://evil.example/acme",
        "https://facebook.com/profile.php",
    ],
)
def test_rejects_non_page_or_unsafe_urls(url):
    with pytest.raises(ValueError):
        canonicalize_page_url(url)


def test_request_applies_safe_bounds_and_rejects_unknown_fields():
    request = normalize_page_clone_request({"source_url": "https://www.facebook.com/acme"})
    assert request["source_url"] == "https://www.facebook.com/acme"
    assert request["max_posts"] == MAX_POSTS
    assert request["candidate_limit"] == MAX_CANDIDATES
    assert request["max_media_per_post"] == MAX_MEDIA_PER_POST

    with pytest.raises(ValueError, match="max_posts must be between"):
        normalize_page_clone_request({"source_url": "https://facebook.com/acme", "max_posts": 9999})

    with pytest.raises(ValueError):
        normalize_page_clone_request({"source_url": "https://facebook.com/acme", "token": "secret"})


def test_redacts_ids_urls_and_tokens_from_durable_result():
    result = redact_page_clone_result(
        {
            "source_url": "https://www.facebook.com/acme",
            "profile": {"id": "123", "name": "Acme"},
            "posts": [
                {
                    "id": "456",
                    "permalink": "https://www.facebook.com/acme/posts/456",
                    "message": "hello",
                    "media": [{"url": "https://scontent.example/x.jpg", "type": "image"}],
                }
            ],
            "access_token": "secret-token",
        }
    )
    assert result["source_ref"].startswith("sha256:")
    assert result["profile"]["id_hash"].startswith("sha256:")
    assert result["posts"][0]["id_hash"].startswith("sha256:")
    assert "source_url" not in result
    assert "permalink" not in result["posts"][0]
    assert "access_token" not in str(result)
    assert result["posts"][0]["media"][0]["host"] == "scontent.example"


def test_redacts_urls_from_persisted_page_clone_warnings():
    result = redact_page_clone_result({
        "source_url": "https://www.facebook.com/acme",
        "warnings": ["media skipped: https://scontent.xx.fbcdn.net/photo.jpg?token=secret"],
        "posts": [],
    })

    assert result["warnings"] == ["media skipped: [redacted URL]"]
    assert "scontent" not in str(result)
    assert "token=secret" not in str(result)


def test_redaction_uses_configured_media_dir_for_cached_media(tmp_path, monkeypatch):
    from agent.services import page_clone_contract

    monkeypatch.setattr(page_clone_contract, "MEDIA_DIR", str(tmp_path))
    cached = tmp_path / "page-clone-task-0-0.jpg"
    cached.write_bytes(b"image")

    result = redact_page_clone_result({
        "source_url": "https://www.facebook.com/acme",
        "posts": [{"media": [{
            "url": "https://scontent.xx.fbcdn.net/image.jpg",
            "local_path": str(cached),
        }]}],
    })

    assert result["posts"][0]["media"][0]["media_path"] == str(cached.resolve())


def test_redacts_terminal_task_payload_source_url():
    redacted = redact_page_clone_task_payload({
        "sourceUrl": "https://www.facebook.com/acme",
        "maxPosts": 3,
    })

    assert redacted["sourceRef"].startswith("sha256:")
    assert "sourceUrl" not in redacted
    assert "facebook.com/acme" not in str(redacted)


def test_download_media_is_strict_boolean_opt_in():
    request = normalize_page_clone_request({
        "source_url": "https://facebook.com/acme",
        "download_media": True,
    })
    assert request["download_media"] is True
    with pytest.raises(ValueError, match="download_media must be a boolean"):
        normalize_page_clone_request({
            "source_url": "https://facebook.com/acme",
            "download_media": "true",
        })
