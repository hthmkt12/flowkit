"""FBKit — Strategy & Trace API endpoints.

Exposes learned automation strategies and execution traces
for dashboard visualization and manual management.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agent.db import crud

router = APIRouter(tags=["strategies"])


# ─── Request Models ──────────────────────────────────────────

class StrategyUpsert(BaseModel):
    task_type: str
    url_pattern: str = "*"
    selectors: dict | None = None
    wait_strategies: list | None = None
    workarounds: list | None = None
    notes: str | None = None


# ─── Strategy Endpoints ─────────────────────────────────────

@router.get("/strategies")
async def list_strategies(task_type: str | None = None):
    """List learned strategies, optionally filtered by task_type."""
    return await crud.list_strategies(task_type)


@router.get("/strategies/{task_type}")
async def get_strategy(task_type: str, url_pattern: str = "*"):
    """Get the best matching strategy for a task type."""
    strategy = await crud.get_strategy(task_type, url_pattern)
    if not strategy:
        raise HTTPException(status_code=404, detail="No strategy found")
    return strategy


@router.put("/strategies")
async def upsert_strategy(body: StrategyUpsert):
    """Create or update a strategy (merges with existing data)."""
    return await crud.upsert_strategy(
        task_type=body.task_type,
        url_pattern=body.url_pattern,
        selectors=body.selectors,
        wait_strategies=body.wait_strategies,
        workarounds=body.workarounds,
        notes=body.notes,
    )


# ─── Trace Endpoints ────────────────────────────────────────

@router.get("/traces")
async def list_traces(
    task_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
):
    """List execution traces with optional filters."""
    return await crud.list_traces(task_type=task_type, status=status, limit=limit)
