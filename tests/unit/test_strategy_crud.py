"""Tests for task_strategy and task_trace CRUD operations."""
import pytest
import json
from agent.db import crud


class TestStrategyCrud:
    """Verify strategy create/read/update/merge logic."""

    @pytest.fixture(autouse=True)
    async def _setup(self, db_ready):
        pass

    @pytest.mark.asyncio
    async def test_create_strategy(self):
        result = await crud.upsert_strategy(
            task_type="LIKE_POST",
            selectors={"likeBtn": 'div[aria-label="Like"]'},
            notes="Initial strategy",
        )
        assert result["task_type"] == "LIKE_POST"
        assert result["url_pattern"] == "*"
        assert result["selectors"]["likeBtn"] == 'div[aria-label="Like"]'
        assert result["success_count"] == 0
        assert result["fail_count"] == 0

    @pytest.mark.asyncio
    async def test_get_strategy_exact_match(self):
        await crud.upsert_strategy(
            task_type="COMMENT_POST",
            url_pattern="https://facebook.com/groups/*",
            selectors={"commentBox": 'div[role="textbox"]'},
        )
        result = await crud.get_strategy("COMMENT_POST", "https://facebook.com/groups/*")
        assert result is not None
        assert result["selectors"]["commentBox"] == 'div[role="textbox"]'

    @pytest.mark.asyncio
    async def test_get_strategy_matches_specific_url_pattern_before_wildcard(self):
        await crud.upsert_strategy(
            task_type="COMMENT_POST",
            url_pattern="*",
            selectors={"commentBox": "wildcard-selector"},
        )
        group_strategy = await crud.upsert_strategy(
            task_type="COMMENT_POST",
            url_pattern="https://facebook.com/groups/*",
            selectors={"commentBox": "group-selector"},
        )

        result = await crud.get_strategy(
            "COMMENT_POST",
            "https://facebook.com/groups/1/posts/2",
        )

        assert result is not None
        assert result["id"] == group_strategy["id"]
        assert result["selectors"]["commentBox"] == "group-selector"

    @pytest.mark.asyncio
    async def test_get_strategy_wildcard_fallback(self):
        await crud.upsert_strategy(
            task_type="SHARE_POST",
            url_pattern="*",
            selectors={"shareBtn": 'div[aria-label="Share"]'},
        )
        # Request a specific URL, should fall back to wildcard
        result = await crud.get_strategy("SHARE_POST", "https://facebook.com/some/page")
        assert result is not None
        assert result["selectors"]["shareBtn"] == 'div[aria-label="Share"]'

    @pytest.mark.asyncio
    async def test_upsert_specific_strategy_does_not_overwrite_wildcard(self):
        await crud.upsert_strategy(
            task_type="COMMENT_POST",
            url_pattern="*",
            selectors={"commentBox": "wildcard-selector"},
        )
        exact = await crud.upsert_strategy(
            task_type="COMMENT_POST",
            url_pattern="https://facebook.com/groups/1/posts/2",
            selectors={"commentBox": "exact-selector"},
        )

        wildcard = await crud.get_strategy("COMMENT_POST", "*")
        matched = await crud.get_strategy(
            "COMMENT_POST",
            "https://facebook.com/groups/1/posts/2",
        )

        assert exact["url_pattern"] == "https://facebook.com/groups/1/posts/2"
        assert wildcard["selectors"]["commentBox"] == "wildcard-selector"
        assert matched["id"] == exact["id"]
        assert matched["selectors"]["commentBox"] == "exact-selector"

    @pytest.mark.asyncio
    async def test_get_strategy_not_found(self):
        result = await crud.get_strategy("NONEXISTENT_TYPE")
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_merge_selectors(self):
        """Second upsert should merge selectors, not replace."""
        await crud.upsert_strategy(
            task_type="LIKE_POST",
            selectors={"likeBtn": 'div[aria-label="Like"]'},
        )
        await crud.upsert_strategy(
            task_type="LIKE_POST",
            selectors={"likeBtnVi": 'div[aria-label="Thích"]'},
        )
        result = await crud.get_strategy("LIKE_POST")
        assert "likeBtn" in result["selectors"]
        assert "likeBtnVi" in result["selectors"]

    @pytest.mark.asyncio
    async def test_upsert_merge_workarounds(self):
        """Workarounds should be deduplicated on merge."""
        wa1 = {"error": "timeout", "fix": "increase wait"}
        wa2 = {"error": "element not found", "fix": "retry"}
        await crud.upsert_strategy(task_type="POST_TEXT", workarounds=[wa1])
        await crud.upsert_strategy(task_type="POST_TEXT", workarounds=[wa2])
        # Duplicate: same wa1 again
        await crud.upsert_strategy(task_type="POST_TEXT", workarounds=[wa1])

        result = await crud.get_strategy("POST_TEXT")
        assert len(result["workarounds"]) == 2  # deduped

    @pytest.mark.asyncio
    async def test_record_outcome_success(self):
        await crud.upsert_strategy(task_type="ADD_FRIEND")
        await crud.record_strategy_outcome("ADD_FRIEND", success=True)
        await crud.record_strategy_outcome("ADD_FRIEND", success=True)
        await crud.record_strategy_outcome("ADD_FRIEND", success=False)

        result = await crud.get_strategy("ADD_FRIEND")
        assert result["success_count"] == 2
        assert result["fail_count"] == 1
        assert result["last_success"] is not None
        assert result["last_failure"] is not None

    @pytest.mark.asyncio
    async def test_list_strategies(self):
        await crud.upsert_strategy(task_type="LIKE_POST", notes="like")
        await crud.upsert_strategy(task_type="COMMENT_POST", notes="comment")
        await crud.upsert_strategy(task_type="SHARE_POST", notes="share")

        all_strats = await crud.list_strategies()
        assert len(all_strats) == 3

        like_only = await crud.list_strategies(task_type="LIKE_POST")
        assert len(like_only) == 1
        assert like_only[0]["task_type"] == "LIKE_POST"


class TestTraceCrud:
    """Verify execution trace recording and querying."""

    @pytest.fixture(autouse=True)
    async def _setup(self, db_ready):
        # Create a test account + task to reference
        self.account = await crud.create_account("TraceTestUser", fb_uid="trace123")
        self.task = await crud.create_task(
            self.account["id"],
            task_type="LIKE_POST",
            payload='{"postUrl": "https://facebook.com/post/123"}',
        )

    @pytest.mark.asyncio
    async def test_create_trace_success(self):
        trace = await crud.create_trace(
            task_id=self.task["id"],
            task_type="LIKE_POST",
            status="SUCCESS",
            duration_ms=1250,
        )
        assert trace["task_id"] == self.task["id"]
        assert trace["status"] == "SUCCESS"
        assert trace["duration_ms"] == 1250

    @pytest.mark.asyncio
    async def test_create_trace_failure(self):
        trace = await crud.create_trace(
            task_id=self.task["id"],
            task_type="LIKE_POST",
            status="FAILURE",
            error_detail="Could not find Like button",
            duration_ms=8500,
        )
        assert trace["status"] == "FAILURE"
        assert "Like button" in trace["error_detail"]

    @pytest.mark.asyncio
    async def test_list_traces_filter_by_status(self):
        await crud.create_trace(
            task_id=self.task["id"], task_type="LIKE_POST", status="SUCCESS",
        )
        task2 = await crud.create_task(self.account["id"], task_type="COMMENT_POST", payload="{}")
        await crud.create_trace(
            task_id=task2["id"], task_type="COMMENT_POST", status="FAILURE",
            error_detail="timeout",
        )

        successes = await crud.list_traces(status="SUCCESS")
        assert len(successes) == 1
        assert successes[0]["status"] == "SUCCESS"

        failures = await crud.list_traces(status="FAILURE")
        assert len(failures) == 1

    @pytest.mark.asyncio
    async def test_list_traces_filter_by_type(self):
        await crud.create_trace(
            task_id=self.task["id"], task_type="LIKE_POST", status="SUCCESS",
        )
        task2 = await crud.create_task(self.account["id"], task_type="SHARE_POST", payload="{}")
        await crud.create_trace(
            task_id=task2["id"], task_type="SHARE_POST", status="SUCCESS",
        )

        like_traces = await crud.list_traces(task_type="LIKE_POST")
        assert len(like_traces) == 1

        all_traces = await crud.list_traces()
        assert len(all_traces) == 2

    @pytest.mark.asyncio
    async def test_trace_with_strategy_link(self):
        strategy = await crud.upsert_strategy(task_type="LIKE_POST")
        trace = await crud.create_trace(
            task_id=self.task["id"],
            task_type="LIKE_POST",
            status="SUCCESS",
            strategy_id=strategy["id"],
        )
        assert trace["strategy_id"] == strategy["id"]


class TestMergeHelpers:
    """Test internal merge functions."""

    def test_merge_dicts(self):
        base = {"a": 1, "b": 2}
        update = {"b": 3, "c": 4}
        result = crud._merge_dicts(base, update)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_lists_dedup(self):
        base = [{"error": "timeout"}, "retry"]
        update = [{"error": "timeout"}, "new_fix"]
        result = crud._merge_lists(base, update)
        assert len(result) == 3  # timeout (deduped), retry, new_fix

    def test_merge_lists_preserves_order(self):
        result = crud._merge_lists(["a", "b"], ["c", "a"])
        assert result == ["a", "b", "c"]
