"""Operator review converts approved Page Clone evidence into local drafts only."""
import json
from pathlib import Path

import pytest

from agent.api import tasks as tasks_api
from agent.db import crud


@pytest.fixture
async def page_clone_draft_account(db_ready):
    return await crud.create_account("Page Clone Draft Account")


@pytest.mark.asyncio
async def test_page_clone_evidence_creates_selected_local_page_drafts(page_clone_draft_account):
    source_task = await crud.create_task(
        page_clone_draft_account["id"],
        "SCRAPE_PAGE_CLONE",
        status="COMPLETED",
        result=json.dumps({
            "success": True,
            "data": {
                "posts": [
                    {"message": "First cloned draft"},
                    {"message": "Second cloned draft"},
                ],
            },
        }),
    )

    drafts = await tasks_api.create_page_clone_drafts(
        source_task["id"],
        tasks_api.PageCloneDraftCreate(
            account_id=page_clone_draft_account["id"],
            target_id="destination-page",
            selected_post_indexes=[1],
        ),
    )

    assert drafts["source_task_id"] == source_task["id"]
    assert len(drafts["drafts"]) == 1
    draft = drafts["drafts"][0]
    assert draft["status"] == "DRAFT"
    assert draft["target_type"] == "PAGE"
    assert draft["target_id"] == "destination-page"
    assert draft["content"] == "Second cloned draft"


@pytest.mark.asyncio
async def test_page_clone_drafts_reject_non_completed_or_cross_account_source(page_clone_draft_account):
    source_task = await crud.create_task(
        page_clone_draft_account["id"],
        "SCRAPE_PAGE_CLONE", result=json.dumps({"data": {"posts": []}}),
    )

    with pytest.raises(Exception) as exc_info:
        await tasks_api.create_page_clone_drafts(
            source_task["id"],
            tasks_api.PageCloneDraftCreate(
                account_id=page_clone_draft_account["id"],
                target_id="destination-page",
                selected_post_indexes=[0],
            ),
        )

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_page_clone_drafts_only_attach_cached_media_inside_media_dir(
    page_clone_draft_account, tmp_path, monkeypatch
):
    from agent.api import tasks as tasks_module

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    cached_image = media_dir / "cached.jpg"
    cached_image.write_bytes(b"image")
    monkeypatch.setattr(tasks_module, "MEDIA_DIR", str(media_dir))

    source_task = await crud.create_task(
        page_clone_draft_account["id"],
        "SCRAPE_PAGE_CLONE",
        status="COMPLETED",
        result=json.dumps({"data": {"posts": [{
            "message": "Image draft",
            "media": [
                {"media_path": str(cached_image)},
                {"media_path": str(tmp_path / "outside.jpg")},
            ],
        }]}}),
    )

    response = await tasks_api.create_page_clone_drafts(
        source_task["id"],
        tasks_api.PageCloneDraftCreate(
            account_id=page_clone_draft_account["id"],
            target_id="destination-page",
            selected_post_indexes=[0],
        ),
    )

    draft = response["drafts"][0]
    assert draft["post_type"] == "IMAGE"
    assert json.loads(draft["media_paths"]) == [str(cached_image.resolve())]


@pytest.mark.asyncio
async def test_page_clone_drafts_allow_image_only_post(page_clone_draft_account, tmp_path, monkeypatch):
    from agent.api import tasks as tasks_module

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    cached_image = media_dir / "image.jpg"
    cached_image.write_bytes(b"image")
    monkeypatch.setattr(tasks_module, "MEDIA_DIR", str(media_dir))
    source_task = await crud.create_task(
        page_clone_draft_account["id"],
        "SCRAPE_PAGE_CLONE",
        status="COMPLETED",
        result=json.dumps({"data": {"posts": [{
            "message": "",
            "media": [{"media_path": str(cached_image)}],
        }]}}),
    )

    response = await tasks_api.create_page_clone_drafts(
        source_task["id"],
        tasks_api.PageCloneDraftCreate(
            account_id=page_clone_draft_account["id"],
            target_id="destination-page",
            selected_post_indexes=[0],
        ),
    )

    assert response["drafts"][0]["post_type"] == "IMAGE"
    assert response["drafts"][0]["content"] == ""


@pytest.mark.asyncio
async def test_page_clone_drafts_create_video_post_for_cached_video(page_clone_draft_account, tmp_path, monkeypatch):
    from agent.api import tasks as tasks_module

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    cached_video = media_dir / "video.mp4"
    cached_video.write_bytes(b"video")
    monkeypatch.setattr(tasks_module, "MEDIA_DIR", str(media_dir))
    source_task = await crud.create_task(
        page_clone_draft_account["id"],
        "SCRAPE_PAGE_CLONE",
        status="COMPLETED",
        result=json.dumps({"data": {"posts": [{
            "message": "Video draft",
            "media": [{"media_path": str(cached_video), "type": "video"}],
        }]}}),
    )

    response = await tasks_api.create_page_clone_drafts(
        source_task["id"],
        tasks_api.PageCloneDraftCreate(
            account_id=page_clone_draft_account["id"],
            target_id="destination-page",
            selected_post_indexes=[0],
        ),
    )

    assert response["drafts"][0]["post_type"] == "VIDEO"
