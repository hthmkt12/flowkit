"""Tests for CRUD operations with real in-memory SQLite."""
import json
import pytest


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """Provide a fresh, initialized database for each test."""
    db_path = str(tmp_path / "crud_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import agent.db.schema as schema_mod
    schema_mod._db = None
    schema_mod.DB_PATH = db_path
    await schema_mod.init_db()
    yield
    await schema_mod.close_db()


class TestAccountCrud:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db):
        from agent.db import crud
        acc = await crud.create_account("Test User", fb_uid="12345")
        assert acc is not None
        assert acc["name"] == "Test User"
        assert acc["fb_uid"] == "12345"
        assert acc["id"]  # UUID assigned

        fetched = await crud.get_account(acc["id"])
        assert fetched["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_list_accounts(self, db):
        from agent.db import crud
        await crud.create_account("User A")
        await crud.create_account("User B", status="PAUSED")

        all_accs = await crud.list_accounts()
        assert len(all_accs) == 2

        active = await crud.list_accounts(status="ACTIVE")
        assert len(active) == 1
        assert active[0]["name"] == "User A"

    @pytest.mark.asyncio
    async def test_update_account(self, db):
        from agent.db import crud
        acc = await crud.create_account("Original")
        updated = await crud.update_account(acc["id"], name="Updated", status="PAUSED")
        assert updated["name"] == "Updated"
        assert updated["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_delete_account(self, db):
        from agent.db import crud
        acc = await crud.create_account("ToDelete")
        assert await crud.delete_account(acc["id"]) is True
        assert await crud.get_account(acc["id"]) is None


    @pytest.mark.asyncio
    async def test_encrypted_cookies(self, db):
        from agent.db import crud
        cookies = [{"name": "c_user", "value": "123456"}]
        acc = await crud.create_account(
            "Encrypted User",
            cookies_data=cookies
        )
        # Fetched data should be decrypted back to the original
        fetched = await crud.get_account(acc["id"])
        assert json.loads(fetched["cookies_data"]) == cookies

        # Verify DB stores encrypted data (not plaintext)
        from agent.db.schema import get_db
        raw_db = await get_db()
        cur = await raw_db.execute(
            "SELECT cookies_data FROM account WHERE id = ?", (acc["id"],)
        )
        raw_row = await cur.fetchone()
        raw_value = raw_row[0]
        assert raw_value != json.dumps(cookies)  # Should be encrypted

    @pytest.mark.asyncio
    async def test_update_encrypted_field(self, db):
        from agent.db import crud
        acc = await crud.create_account("User", cookies_data="old-cookie")
        updated = await crud.update_account(
            acc["id"], cookies_data="new-cookie"
        )
        assert updated["cookies_data"] == "new-cookie"


class TestMetricsSyncCrud:
    @pytest.mark.asyncio
    async def test_lists_only_bounded_due_completed_zoopost_tasks(self, db):
        from agent.db import crud

        account = await crud.create_account("Metrics Account", fb_uid="123")
        for index in range(3):
            await crud.create_task(
                account["id"],
                "POST_TEXT",
                ref_id=f"zoopost:dispatch-{index}",
                status="COMPLETED",
                result=json.dumps({"externalPostId": f"post-{index}"}),
            )
        await crud.create_task(
            account["id"],
            "POST_TEXT",
            ref_id="local-task",
            status="COMPLETED",
            result=json.dumps({"externalPostId": "local-post"}),
        )

        candidates = await crud.list_due_metrics_tasks(limit=2, refresh_seconds=3600, max_age_days=30)

        assert len(candidates) == 2
        assert all(task["ref_id"].startswith("zoopost:") for task in candidates)

    @pytest.mark.asyncio
    async def test_marked_metrics_task_is_not_immediately_due_again(self, db):
        from agent.db import crud

        account = await crud.create_account("Metrics Account", fb_uid="123")
        task = await crud.create_task(
            account["id"],
            "POST_TEXT",
            ref_id="zoopost:dispatch-synced",
            status="COMPLETED",
            result=json.dumps({"externalPostId": "post-synced"}),
        )

        await crud.mark_task_metrics_synced(task["id"])

        assert await crud.list_due_metrics_tasks(limit=10, refresh_seconds=3600, max_age_days=30) == []


class TestTaskCrud:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db):
        from agent.db import crud
        acc = await crud.create_account("TaskUser")
        task = await crud.create_task(
            acc["id"], "POST_TEXT",
            payload='{"content":"Hello"}',
            priority=5
        )
        assert task["task_type"] == "POST_TEXT"
        assert task["priority"] == 5
        assert task["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_get_next_pending(self, db):
        from agent.db import crud
        acc = await crud.create_account("Worker")
        await crud.create_task(acc["id"], "POST_TEXT", priority=1)
        await crud.create_task(acc["id"], "LIKE_POST", priority=10)

        next_task = await crud.get_next_pending_task()
        assert next_task is not None
        assert next_task["task_type"] == "LIKE_POST"  # Higher priority

    @pytest.mark.asyncio
    async def test_update_task_status(self, db):
        from agent.db import crud
        acc = await crud.create_account("Worker2")
        task = await crud.create_task(acc["id"], "SEND_MESSAGE")
        updated = await crud.update_task(task["id"], status="COMPLETED")
        assert updated["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_cancel_task(self, db):
        from agent.db import crud
        acc = await crud.create_account("Worker3")
        task = await crud.create_task(acc["id"], "ADD_FRIEND")
        cancelled = await crud.cancel_task(task["id"])
        assert cancelled["status"] == "CANCELLED"


class TestPostCrud:
    @pytest.mark.asyncio
    async def test_create_and_list(self, db):
        from agent.db import crud
        acc = await crud.create_account("Poster")
        await crud.create_post(acc["id"], "TEXT", content="Hello World")
        await crud.create_post(acc["id"], "IMAGE", content="Photo post")

        posts = await crud.list_posts(account_id=acc["id"])
        assert len(posts) == 2

    @pytest.mark.asyncio
    async def test_update_and_delete(self, db):
        from agent.db import crud
        acc = await crud.create_account("Poster2")
        post = await crud.create_post(acc["id"], content="Draft")
        updated = await crud.update_post(post["id"], status="POSTED")
        assert updated["status"] == "POSTED"
        assert await crud.delete_post(post["id"]) is True


class TestMessageCrud:
    @pytest.mark.asyncio
    async def test_create_and_list(self, db):
        from agent.db import crud
        acc = await crud.create_account("Messenger")
        await crud.create_message(acc["id"], "John", "Hi there!")
        messages = await crud.list_messages(account_id=acc["id"])
        assert len(messages) == 1
        assert messages[0]["content"] == "Hi there!"


class TestActivityLog:
    @pytest.mark.asyncio
    async def test_log_and_list(self, db):
        from agent.db import crud
        acc = await crud.create_account("Logger")
        await crud.log_activity(acc["id"], "POST_TEXT", "Posted successfully")
        logs = await crud.list_activities(account_id=acc["id"])
        assert len(logs) == 1
        assert logs[0]["action"] == "POST_TEXT"


class TestDailyCounters:
    @pytest.mark.asyncio
    async def test_increment_and_reset(self, db):
        from agent.db import crud
        acc = await crud.create_account("Counter")
        await crud.increment_daily_counter(acc["id"], "daily_posts")
        await crud.increment_daily_counter(acc["id"], "daily_posts")
        updated = await crud.get_account(acc["id"])
        assert updated["daily_posts"] == 2

        await crud.reset_daily_counters(acc["id"])
        reset = await crud.get_account(acc["id"])
        assert reset["daily_posts"] == 0
