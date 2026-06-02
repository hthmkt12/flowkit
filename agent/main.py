"""FBKit — FastAPI entry point + WebSocket server.

Handles:
1. HTTP REST API on port 8100
2. WebSocket bridge on port 9222 (extension ↔ agent)
3. Dashboard WebSocket for real-time updates
4. Task worker lifecycle
"""
import asyncio
import base64
import binascii
import json
import secrets
import logging
import signal
import sys
from urllib.parse import parse_qs, urlparse

import uvicorn
import websockets
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi import status as http_status
from fastapi.middleware.cors import CORSMiddleware

from agent import config
from agent.config import API_HOST, API_PORT, CORS_ALLOWED_ORIGINS, WS_AUTH_ENABLED, WS_API_KEY, WS_HOST, WS_PORT
from agent.db.schema import init_db, close_db
from agent.services.fb_client import get_fb_client
from agent.services.event_bus import event_bus
from agent.worker.processor import get_worker_controller
from agent.services.scheduler import get_scheduler
from agent.services.auto_seed import get_auto_seeder
from agent.services.spy_ads import get_spy_ads
from agent.services.notifier import get_notifier
from agent.services.auth import require_api_key
from agent.services.zoopost_cloud_agent import run_gateway_loop
from agent.services.metrics_sync import get_metrics_sync

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

    zoopost_gateway_task = asyncio.create_task(run_gateway_loop())

    # Start metrics sync service
    metrics_sync = get_metrics_sync()
    metrics_sync_task = asyncio.create_task(metrics_sync.start())

    # Start WebSocket server for extension
    ws_server = await websockets.serve(
        _handle_extension_ws, WS_HOST, WS_PORT,
        ping_interval=30, ping_timeout=10,
    )
    logger.info("Extension WebSocket server on ws://%s:%d", WS_HOST, WS_PORT)

    yield

    # Shutdown
    logger.info("Shutting down...")
    metrics_sync.request_shutdown()
    spy.request_shutdown()
    seeder.request_shutdown()
    scheduler.request_shutdown()
    worker.request_shutdown()
    zoopost_gateway_task.cancel()
    metrics_sync_task.cancel()
    await asyncio.gather(zoopost_gateway_task, metrics_sync_task, return_exceptions=True)
    await worker.drain()
    ws_server.close()
    await ws_server.wait_closed()
    await close_db()
    logger.info("FBKit Agent stopped")


# ─── Extension WebSocket Handler ─────────────────────────────

async def _handle_extension_ws(ws, path=None):
    """Handle WebSocket connection from Chrome extension."""
    if WS_AUTH_ENABLED:
        ws_key = _extension_ws_api_key(path or getattr(ws, "path", "") or "")
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


def _extension_ws_api_key(request_path: str) -> str | None:
    params = parse_qs(urlparse(request_path).query, keep_blank_values=True)
    values = params.get("api_key") or params.get("token") or []
    return values[0] if values else None


# ─── FastAPI App ──────────────────────────────────────────────

app = FastAPI(
    title="FBKit Agent",
    description="Facebook Automation Agent — tương tác như người dùng thật",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
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
    worker = get_worker_controller()
    return {
        "name": "FBKit Agent",
        "version": "1.0.0",
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
    active_live_arms = await crud.list_active_live_arms()
    active_live_leases = await crud.list_active_live_account_leases()
    return {
        "extension": client.ws_stats,
        "worker": {
            "active_tasks": worker.active_count,
            "node_id": worker.node_id,
            "active_live_account_ids": sorted(worker.active_live_account_ids),
            "live_account_leases": active_live_leases,
        },
        "scheduler": scheduler.stats,
        "seeder": seeder.stats,
        "spy_ads": spy.stats,
        "notifier": notifier.stats,
        "session": session.session_info,
        "safety_gate": {
            "live_actions_enabled": config.LIVE_ACTIONS_ENABLED,
            "dry_run_default": config.DRY_RUN_DEFAULT,
            "approval_required": config.APPROVAL_REQUIRED,
            "api_auth_enabled": config.API_AUTH_ENABLED,
            "ws_auth_enabled": config.WS_AUTH_ENABLED,
            "live_auth_ready": config.API_AUTH_ENABLED and config.WS_AUTH_ENABLED,
            "active_live_arms": active_live_arms,
        },
        "tasks": task_stats,
    }


# ─── Dashboard WebSocket ────────────────────────────────────

@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    """Real-time updates for dashboard UI."""
    if _has_dashboard_query_credential(ws):
        await ws.close(code=http_status.WS_1008_POLICY_VIOLATION)
        return
    if WS_AUTH_ENABLED:
        token = _dashboard_ws_api_key(ws)
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

def _dashboard_ws_api_key(ws: WebSocket) -> str | None:
    if _has_dashboard_query_credential(ws):
        return None
    protocols = ws.headers.get("sec-websocket-protocol", "")
    for protocol in [part.strip() for part in protocols.split(",") if part.strip()]:
        if protocol.startswith("bearer.b64."):
            return _decode_base64url_token(protocol.removeprefix("bearer.b64."))
        if protocol.startswith("bearer."):
            return protocol.removeprefix("bearer.")
    return None


def _has_dashboard_query_credential(ws: WebSocket) -> bool:
    return any(name in ws.query_params for name in ("token", "api_key", "credential", "authorization"))


def _decode_base64url_token(encoded: str) -> str | None:
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


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
