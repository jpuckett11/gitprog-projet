"""Async fanout bus.

When a webhook arrives we push the event to all currently connected WebSocket
subscribers. Each subscriber has its own asyncio.Queue so a slow client doesn't
block the receiver. Bounded queue size; if the queue is full we drop the oldest.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

QUEUE_MAX = 256


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> AsyncIterator[dict]:
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=QUEUE_MAX)
        async with self._lock:
            self._subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            async with self._lock:
                self._subscribers.discard(q)

    async def publish(self, event: dict) -> None:
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            await q.put(event)

    async def subscriber_count(self) -> int:
        async with self._lock:
            return len(self._subscribers)
