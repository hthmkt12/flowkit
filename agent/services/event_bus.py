"""FBKit — Simple in-process event bus for dashboard updates."""
import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """Pub/sub event bus for broadcasting updates to dashboard clients."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers = [s for s in self._subscribers if s is not q]

    async def emit(self, event_type: str, data: Any = None):
        msg = json.dumps({"type": event_type, "data": data})
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers = [s for s in self._subscribers if s is not q]


event_bus = EventBus()
