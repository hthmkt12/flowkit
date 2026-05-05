"""Shared pytest fixtures for FBKit tests."""

import os
import pytest
import asyncio


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    """Ensure each test uses an isolated SQLite database and clean config."""
    db_path = str(tmp_path / "test_fbkit.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("API_AUTH_ENABLED", "false")
    monkeypatch.setenv("WS_AUTH_ENABLED", "false")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "test-key-for-unit-tests-only")

    # Reset module-level singletons that cache config at import time
    import agent.db.schema as schema_mod
    schema_mod._db = None
    schema_mod.DB_PATH = db_path

    yield

    # Cleanup: close db if opened
    loop = asyncio.get_event_loop()
    if schema_mod._db is not None:
        if loop.is_running():
            pass  # Will be cleaned by next test
        else:
            loop.run_until_complete(schema_mod.close_db())


@pytest.fixture
async def db_ready():
    """Initialize the database schema for tests that need it."""
    from agent.db.schema import init_db
    await init_db()


@pytest.fixture
def sample_account_data():
    """Minimal data for creating an account."""
    return {
        "name": "Test Account",
        "fb_uid": "100001234567890",
        "email": "test@example.com",
        "status": "ACTIVE",
    }


@pytest.fixture
def sample_post_data():
    return {
        "content": "Hello from FBKit test!",
        "post_type": "TEXT",
        "target_type": "TIMELINE",
    }


@pytest.fixture
def sample_task_data():
    return {
        "task_type": "POST_TEXT",
        "payload": '{"content": "Test post content"}',
        "priority": 5,
    }
