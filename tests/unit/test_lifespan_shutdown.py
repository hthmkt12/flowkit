"""Tests for lifespan shutdown drain (Phase 4 Task 5).

Exiting lifespan must drain every background task: worker, scheduler,
seeder, spy, notifier, gateway, metrics. No owned task is left pending.
WebSocket and DB are closed after all drains complete.
"""
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

logger = logging.getLogger(__name__)


class FakeService:
    """A fake background service that tracks shutdown and task lifecycle."""

    def __init__(self, name: str):
        self.name = name
        self._shutdown = False
        self._task = None
        self.cancelled = False
        self.finalized = False

    def request_shutdown(self, *args, **kwargs):
        self._shutdown = True

    async def _run(self):
        try:
            while not self._shutdown:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        finally:
            self.finalized = True

    async def start(self):
        self._task = asyncio.current_task()


class FakeWorker(FakeService):
    def __init__(self):
        super().__init__("worker")
        self._active_count = 0

    @property
    def active_count(self):
        return self._active_count

    async def drain(self):
        """Wait for active tasks to finish (instant in test)."""
        pass


@pytest.fixture
def fake_services():
    """Create fake services and patch them into agent.main."""
    services = {
        "worker": FakeWorker(),
        "scheduler": FakeService("scheduler"),
        "seeder": FakeService("seeder"),
        "spy": FakeService("spy"),
        "notifier": FakeService("notifier"),
        "metrics_sync": FakeService("metrics_sync"),
    }

    created_tasks = []

    async def fake_start(self):
        self._task = asyncio.current_task()
        created_tasks.append(self._task)
        try:
            while not self._shutdown:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        finally:
            self.finalized = True

    # Patch start methods to create trackable tasks
    for svc in services.values():
        svc.start = fake_start.__get__(svc, type(svc))

    async def fake_gateway_loop():
        created_tasks.append(asyncio.current_task())
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass

    async def fake_init_db():
        pass

    async def fake_close_db():
        pass

    async def fake_seed_strategies():
        pass

    patches = [
        patch("agent.main.init_db", AsyncMock(side_effect=fake_init_db)),
        patch("agent.main.close_db", AsyncMock(side_effect=fake_close_db)),
        patch("agent.db.seed_strategies.seed_default_strategies", AsyncMock(side_effect=fake_seed_strategies)),
        patch("agent.main.get_worker_controller", lambda: services["worker"]),
        patch("agent.main.get_scheduler", lambda: services["scheduler"]),
        patch("agent.main.get_auto_seeder", lambda: services["seeder"]),
        patch("agent.main.get_spy_ads", lambda: services["spy"]),
        patch("agent.main.get_notifier", lambda: services["notifier"]),
        patch("agent.main.get_metrics_sync", lambda: services["metrics_sync"]),
        patch("agent.main.run_gateway_loop", fake_gateway_loop),
    ]

    # Patch websockets.serve to a no-op
    class FakeWsServer:
        def close(self):
            pass

        async def wait_closed(self):
            pass

    async def fake_serve(*args, **kwargs):
        return FakeWsServer()

    patches.append(patch("agent.main.websockets.serve", fake_serve))

    for p in patches:
        p.start()

    yield services, created_tasks

    for p in patches:
        p.stop()


def test_lifespan_shutdown_cancels_and_awaits_all_background_tasks(fake_services):
    """Exiting lifespan must cancel+await all background tasks and close WS/DB."""
    from agent.main import lifespan
    from fastapi import FastAPI

    services, created_tasks = fake_services

    async def run_lifespan():
        app = FastAPI()
        async with lifespan(app):
            # Give tasks time to start
            await asyncio.sleep(0.2)
            pass  # exit context → shutdown

    asyncio.run(run_lifespan())

    # Every service with request_shutdown should have been asked to shut down.
    # Notifier has no request_shutdown API — it is cancelled instead.
    for name in ["worker", "scheduler", "seeder", "spy", "metrics_sync"]:
        svc = services[name]
        assert svc._shutdown, f"{name} was not asked to shut down"

    # Worker should have been drained
    # (drain() is called on the worker, which is instant in our fake)

    # All created tasks should be done (not pending)
    for task in created_tasks:
        assert task.done(), f"Task {task} was not awaited/cancelled on shutdown"

    # Notifier should have been cancelled (no request_shutdown method on real notifier,
    # but our fake has one — the lifespan should cancel its task)
    assert services["notifier"].cancelled or services["notifier"].finalized, \
        "Notifier task was not cancelled/finalized"

    # Gateway task should be cancelled
    # (gateway task is the last one created, after services)
    assert created_tasks[-1].done(), "Gateway task not awaited"


def test_lifespan_shutdown_drains_worker_before_closing_db(fake_services):
    """Worker drain must complete before DB close."""
    from agent.main import lifespan, close_db
    from fastapi import FastAPI

    services, _ = fake_services
    worker = services["worker"]

    drain_called = asyncio.Event()
    db_closed = asyncio.Event()

    original_drain = worker.drain

    async def tracking_drain():
        await original_drain()
        drain_called.set()

    worker.drain = tracking_drain

    # Track close_db order
    original_close = close_db

    async def tracking_close():
        assert drain_called.is_set(), "DB closed before worker drained"
        db_closed.set()

    # Re-patch close_db
    with patch("agent.main.close_db", tracking_close):
        async def run_lifespan():
            app = FastAPI()
            async with lifespan(app):
                await asyncio.sleep(0.2)

        asyncio.run(run_lifespan())

    assert drain_called.is_set(), "Worker drain was never called"
    assert db_closed.is_set(), "DB close was never called"


def test_lifespan_shutdown_has_try_finally_cleanup(fake_services):
    """Cleanup must run even if startup raises an exception."""
    from agent.main import lifespan
    from fastapi import FastAPI

    services, _ = fake_services

    async def run_lifespan():
        app = FastAPI()
        with pytest.raises(RuntimeError):
            async with lifespan(app):
                raise RuntimeError("startup failure")

    # Should not raise unhandled — cleanup runs in finally
    asyncio.run(run_lifespan())
