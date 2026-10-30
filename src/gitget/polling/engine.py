
from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog
from PySide6.QtCore import QObject, Signal

log = structlog.get_logger(__name__)

FetchFn = Callable[[], Awaitable[Any]]


@dataclass(slots=True)
class _Resource:
    name: str
    interval: float
    fetch: FetchFn
    last_value: Any = None
    task: asyncio.Task | None = field(default=None, repr=False)


class PollingEngine(QObject):

    changed = Signal(str, object)
    error = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._resources: dict[str, _Resource] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None

    def add_resource(self, name: str, *, interval: float, fetch: FetchFn) -> None:
        if name in self._resources:
            raise ValueError(f"resource {name!r} already registered")
        self._resources[name] = _Resource(name=name, interval=interval, fetch=fetch)

    def set_interval(self, name: str, interval: float) -> None:
        if name in self._resources:
            self._resources[name].interval = interval

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="polling-engine", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if self._loop is None or self._stop_event is None:
            return
        self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
        self._loop = None
        self._stop_event = None

    def trigger_now(self, name: str) -> None:
        if self._loop is None:
            return
        res = self._resources.get(name)
        if res is None:
            return
        asyncio.run_coroutine_threadsafe(self._fetch_once(res), self._loop)


    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    async def _main(self) -> None:
        assert self._stop_event is not None
        tasks = [asyncio.create_task(self._poll_loop(r)) for r in self._resources.values()]
        await self._stop_event.wait()
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await t

    async def _poll_loop(self, res: _Resource) -> None:
        await self._fetch_once(res)
        while True:
            try:
                await asyncio.sleep(res.interval)
            except asyncio.CancelledError:
                return
            await self._fetch_once(res)

    async def _fetch_once(self, res: _Resource) -> None:
        try:
            value = await res.fetch()
        except Exception as exc:
            log.exception("poll_failed", resource=res.name)
            self.error.emit(res.name, exc)
            return
        if value != res.last_value:
            res.last_value = value
            self.changed.emit(res.name, value)
