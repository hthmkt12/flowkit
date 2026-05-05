"""Unit tests for seed_campaign and spy_target CRUD operations."""
import json
import pytest
from agent.db import crud


@pytest.mark.asyncio
class TestSeedCampaignCrud:

    async def test_create_and_get(self, db_ready):
        config = {"accounts": ["acc1"], "targets": ["https://fb.com/post/123"]}
        row = await crud.create_seed_campaign(name="Test Campaign", config=config)
        assert row["id"]
        assert row["name"] == "Test Campaign"
        assert row["status"] == "ACTIVE"
        stats = json.loads(row["stats"])
        assert stats["total"] == 0

        fetched = await crud.get_seed_campaign(row["id"])
        assert fetched["id"] == row["id"]

    async def test_list_campaigns(self, db_ready):
        await crud.create_seed_campaign(name="Camp A", config={})
        await crud.create_seed_campaign(name="Camp B", config={})
        rows = await crud.list_seed_campaigns()
        assert len(rows) >= 2

    async def test_list_by_status(self, db_ready):
        row = await crud.create_seed_campaign(name="Active Camp", config={})
        await crud.update_seed_campaign(row["id"], status="PAUSED")

        active = await crud.list_seed_campaigns(status="ACTIVE")
        paused = await crud.list_seed_campaigns(status="PAUSED")

        ids_active = [r["id"] for r in active]
        ids_paused = [r["id"] for r in paused]
        assert row["id"] not in ids_active
        assert row["id"] in ids_paused

    async def test_update_stats(self, db_ready):
        row = await crud.create_seed_campaign(name="Stats Test", config={})
        new_stats = {"total": 10, "success": 8, "failed": 2}
        updated = await crud.update_seed_campaign(row["id"], stats=json.dumps(new_stats))
        stored = json.loads(updated["stats"])
        assert stored["total"] == 10
        assert stored["success"] == 8

    async def test_delete(self, db_ready):
        row = await crud.create_seed_campaign(name="Delete Me", config={})
        ok = await crud.delete_seed_campaign(row["id"])
        assert ok is True
        assert await crud.get_seed_campaign(row["id"]) is None

    async def test_delete_nonexistent(self, db_ready):
        ok = await crud.delete_seed_campaign("00000000-0000-0000-0000-000000000000")
        assert ok is False


@pytest.mark.asyncio
class TestSpyTargetCrud:

    async def test_create_and_get(self, db_ready):
        row = await crud.create_spy_target(
            page_name="Nike Vietnam",
            page_id="123456789",
            page_url="https://fb.com/nikevn",
            check_interval=1800,
        )
        assert row["id"]
        assert row["page_name"] == "Nike Vietnam"
        assert row["page_id"] == "123456789"
        assert row["check_interval"] == 1800
        assert row["status"] == "ACTIVE"
        assert row["ads_found"] == 0

        fetched = await crud.get_spy_target(row["id"])
        assert fetched["id"] == row["id"]

    async def test_list_targets(self, db_ready):
        await crud.create_spy_target(page_name="Brand A", page_id="111")
        await crud.create_spy_target(page_name="Brand B", page_id="222")
        rows = await crud.list_spy_targets()
        assert len(rows) >= 2

    async def test_update_last_checked(self, db_ready):
        row = await crud.create_spy_target(page_name="Check Test", page_id="999")
        ts = "2026-01-01T12:00:00"
        updated = await crud.update_spy_target(row["id"], last_checked=ts)
        assert updated["last_checked"] == ts

    async def test_update_ads_found(self, db_ready):
        row = await crud.create_spy_target(page_name="Ads Test", page_id="777")
        updated = await crud.update_spy_target(row["id"], ads_found=5)
        assert updated["ads_found"] == 5

    async def test_delete(self, db_ready):
        row = await crud.create_spy_target(page_name="To Delete", page_id="del1")
        ok = await crud.delete_spy_target(row["id"])
        assert ok is True
        assert await crud.get_spy_target(row["id"]) is None

    async def test_delete_nonexistent(self, db_ready):
        ok = await crud.delete_spy_target("00000000-0000-0000-0000-000000000000")
        assert ok is False

    async def test_list_by_status(self, db_ready):
        row = await crud.create_spy_target(page_name="Pause Me", page_id="ppp")
        await crud.update_spy_target(row["id"], status="PAUSED")

        active = await crud.list_spy_targets(status="ACTIVE")
        paused = await crud.list_spy_targets(status="PAUSED")

        assert row["id"] not in [r["id"] for r in active]
        assert row["id"] in [r["id"] for r in paused]
