"""Regression coverage for upgrading existing task tables."""
import sqlite3

import pytest


@pytest.mark.asyncio
async def test_init_db_upgrades_legacy_task_check_constraint(tmp_path, monkeypatch):
    """Existing queue records survive while SCRAPE_PAGE_CLONE becomes valid."""
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import agent.db.schema as schema_mod

    legacy_schema = schema_mod.SCHEMA.replace("'SCRAPE_PAGE_CLONE',", "")
    connection = sqlite3.connect(db_path)
    connection.executescript(legacy_schema)
    connection.execute("INSERT INTO account (id, name) VALUES ('a1', 'Legacy account')")
    connection.execute(
        "INSERT INTO task (id, account_id, task_type, payload) VALUES (?, ?, ?, ?)",
        ("legacy-task", "a1", "SCRAPE_PROFILE", "{}"),
    )
    connection.execute(
        "INSERT INTO task_trace (task_id, task_type, status) VALUES (?, ?, ?)",
        ("legacy-task", "SCRAPE_PROFILE", "SUCCESS"),
    )
    connection.commit()
    connection.close()

    schema_mod._db = None
    schema_mod.DB_PATH = str(db_path)
    await schema_mod.init_db()
    db = await schema_mod.get_db()

    row = await (await db.execute("SELECT task_type FROM task WHERE id = 'legacy-task'")).fetchone()
    assert row["task_type"] == "SCRAPE_PROFILE"
    trace = await (await db.execute(
        "SELECT task_id FROM task_trace WHERE task_id = 'legacy-task'"
    )).fetchone()
    assert trace["task_id"] == "legacy-task"

    await db.execute(
        "INSERT INTO task (id, account_id, task_type, payload) VALUES (?, ?, ?, ?)",
        ("page-clone-task", "a1", "SCRAPE_PAGE_CLONE", "{}"),
    )
    await db.commit()

    task_sql = (await (await db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'task'"
    )).fetchone())["sql"]
    assert "SCRAPE_PAGE_CLONE" in task_sql

    await schema_mod.close_db()
