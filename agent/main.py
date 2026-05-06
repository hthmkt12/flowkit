"""FBKit — FastAPI entry point + WebSocket server.

Replaces FlowKit main.py. Handles:
1. HTTP REST API on port 8100
2. WebSocket bridge on port 9222 (extension ↔ agent)
3. Dashboard WebSocket for real-time updates
4. Task worker lifecycle
"""
import asyncio
import json
import secrets
import logging
import signal
import sys

import uvicorn
import websockets
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi import status as http_status
from fastapi.middleware.cors import CORSMiddleware

from agent.config import API_HOST, API_PORT, WS_AUTH_ENABLED, WS_API_KEY, WS_HOST, WS_PORT
from agent.db.schema import init_db, close_db
from agent.services.fb_client import get_fb_client
from agent.services.event_bus import event_bus
from agent.worker.processor import get_worker_controller
from agent.services.scheduler import get_scheduler
from agent.services.auto_seed import get_auto_seeder
from agent.services.spy_ads import get_spy_ads
from agent.services.notifier import get_notifier
from agent.services.auth import require_api_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fbkit")


# ─── FastAPI Lifespan ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("FBKit Agent starting on %s:%d", API_HOST, API_PORT)

    # Seed default strategies (AutoBrowse pattern — baseline knowledge)
    from agent.db.seed_strategies import seed_default_strategies
    await seed_default_strategies()

    # Start worker
    worker = get_worker_controller()
    worker_task = asyncio.create_task(worker.start())

    # Start scheduler (handles timed posts/messages)
    scheduler = get_scheduler()
    scheduler_task = asyncio.create_task(scheduler.start())

    # Start auto-seeder (engagement campaigns)
    seeder = get_auto_seeder()
    seeder_task = asyncio.create_task(seeder.start())

    # Start spy ads monitor
    spy = get_spy_ads()
    spy_task = asyncio.create_task(spy.start())

    # Start Telegram notifier
    notifier = get_notifier()
    notifier_task = asyncio.create_task(notifier.start())

    # Start WebSocket server for extension
    ws_server = await websockets.serve(
        _handle_extension_ws, WS_HOST, WS_PORT,
        ping_interval=30, ping_timeout=10,
    )
    logger.info("Extension WebSocket server on ws://%s:%d", WS_HOST, WS_PORT)

    yield

    # Shutdown
    logger.info("Shutting down...")
    spy.request_shutdown()
    seeder.request_shutdown()
    scheduler.request_shutdown()
    worker.request_shutdown()
    await worker.drain()
    ws_server.close()
    await ws_server.wait_closed()
    await close_db()
    logger.info("FBKit Agent stopped")


# ─── Extension WebSocket Handler ─────────────────────────────

async def _handle_extension_ws(ws, path=None):
    """Handle WebSocket connection from Chrome extension."""
    if WS_AUTH_ENABLED:
        request_path = path or getattr(ws, "path", "") or ""
        query = request_path.split("?", 1)[1] if "?" in request_path else ""
        params = {}
        for pair in query.split("&"):
            if not pair:
                continue
            k, _, v = pair.partition("=")
            params[k] = v

        ws_key = params.get("api_key") or params.get("token")
        if not ws_key or not secrets.compare_digest(ws_key, WS_API_KEY):
            logger.warning("Extension WS unauthorized from %s", ws.remote_address)
            await ws.close(code=4401, reason="Unauthorized")
            return

    client = get_fb_client()
    # Register session (fb_uid filled in after extension_ready)
    client.set_extension(ws)
    await event_bus.emit("extension_connected", client.ws_stats)
    logger.info("Extension WebSocket connected from %s", ws.remote_address)

    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
                # Pass ws so handle_message can look up the right session
                await client.handle_message(ws, data)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from extension: %s", raw[:100])
    except websockets.ConnectionClosed:
        pass
    finally:
        client.clear_extension(ws)
        await event_bus.emit("extension_disconnected", client.ws_stats)
        logger.info("Extension WebSocket disconnected")


# ─── FastAPI App ──────────────────────────────────────────────

app = FastAPI(
    title="FBKit Agent",
    description="Facebook Automation Agent — tương tác như người dùng thật",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Import & Register Routers ──────────────────────────────

from agent.api.accounts import router as accounts_router
from agent.api.tasks import router as tasks_router
from agent.api.posts import router as posts_router
from agent.api.messages import router as messages_router
from agent.api.groups import router as groups_router
from agent.api.seeding import router as seeding_router
from agent.api.spy import router as spy_router
from agent.api.strategies import router as strategies_router

api_dependencies = [Depends(require_api_key)]

app.include_router(accounts_router, prefix="/api", dependencies=api_dependencies)
app.include_router(tasks_router, prefix="/api", dependencies=api_dependencies)
app.include_router(posts_router, prefix="/api", dependencies=api_dependencies)
app.include_router(messages_router, prefix="/api", dependencies=api_dependencies)
app.include_router(groups_router, prefix="/api", dependencies=api_dependencies)
app.include_router(seeding_router, prefix="/api", dependencies=api_dependencies)
app.include_router(spy_router, prefix="/api", dependencies=api_dependencies)
app.include_router(strategies_router, prefix="/api", dependencies=api_dependencies)


# ─── Root & Status ───────────────────────────────────────────

@app.get("/")
async def root():
    client = get_fb_client()
    worker = get_worker_controller()
    return {
        "name": "FBKit Agent",
        "version": "1.0.0",
        "extension": client.ws_stats,
        "worker": {
            "active_tasks": worker.active_count,
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/status")
async def get_status(_: None = Depends(require_api_key)):
    client = get_fb_client()
    worker = get_worker_controller()
    scheduler = get_scheduler()
    seeder = get_auto_seeder()
    spy = get_spy_ads()
    notifier = get_notifier()
    from agent.services.human_delay import get_session_manager
    session = get_session_manager()
    from agent.db import crud
    task_stats = await crud.get_task_stats()
    return {
        "extension": client.ws_stats,
        "worker": {"active_tasks": worker.active_count},
        "scheduler": scheduler.stats,
        "seeder": seeder.stats,
        "spy_ads": spy.stats,
        "notifier": notifier.stats,
        "session": session.session_info,
        "tasks": task_stats,
    }


# ─── Dashboard WebSocket ────────────────────────────────────

@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    """Real-time updates for dashboard UI."""
    if WS_AUTH_ENABLED:
        token = ws.query_params.get("api_key") or ws.query_params.get("token")
        if not token or not secrets.compare_digest(token, WS_API_KEY):
            await ws.close(code=http_status.WS_1008_POLICY_VIOLATION)
            return

    await ws.accept()
    queue = event_bus.subscribe()
    try:
        while True:
            msg = await queue.get()
            await ws.send_text(msg)
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)


# ─── Entrypoint ──────────────────────────────────────────────

def main():
    uvicorn.run(
        "agent.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
