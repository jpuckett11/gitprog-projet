"""WebSocket bridge: desktop GUI ↔ webhook receiver.

Runs a background asyncio loop in a worker thread that maintains a WebSocket to
the receiver's /events endpoint. Emits Qt signals on the main thread when:
  - an event arrives
  - connection state changes (connected / reconnecting / failed)

On startup, replays anything missed via /events/recent so we don't drop deliveries
that arrived while the GUI was offline.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import httpx
import structlog
import websockets
from PySide6.QtCore import QObject, Signal

log = structlog.get_logger(__name__)


class WebhookBridge(QObject):
    event = Signal(object)          # one webhook event (dict)
    state_changed = Signal(str)     # "connecting" | "connected" | "reconnecting" | "stopped" | "error:<msg>"

    def __init__(
        self,
        receiver_url: str,
        subscriber_token: str,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._receiver_url = receiver_url.rstrip("/")
        self._token = subscriber_token
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None
        self._last_id: int = 0

    # ---------- lifecycle ----------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="webhook-bridge", daemon=True)
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

    # ---------- internal ----------

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
        await self._replay_missed()

        backoff = 1.0
        ws_url = (
            self._receiver_url.replace("http://", "ws://").replace("https://", "wss://")
            + f"/events?token={self._token}"
        )
        while not self._stop_event.is_set():
            self.state_changed.emit("connecting")
            try:
                async with websockets.connect(ws_url, open_timeout=10) as ws:
                    self.state_changed.emit("connected")
                    backoff = 1.0
                    await self._consume(ws)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                log.warning("bridge_disconnected", error=str(exc))
                self.state_changed.emit(f"error:{exc}")

            if self._stop_event.is_set():
                break
            self.state_changed.emit("reconnecting")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                return  # stop signalled during backoff
            except TimeoutError:
                pass
            backoff = min(backoff * 2, 30.0)

        self.state_changed.emit("stopped")

    async def _consume(self, ws) -> None:
        assert self._stop_event is not None
        stop_task = asyncio.create_task(self._stop_event.wait())
        try:
            while not self._stop_event.is_set():
                recv_task = asyncio.create_task(ws.recv())
                done, _ = await asyncio.wait(
                    {recv_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if stop_task in done:
                    recv_task.cancel()
                    return
                msg = recv_task.result()
                try:
                    event = json.loads(msg) if isinstance(msg, (str, bytes)) else msg
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    self._track_id(event)
                    self.event.emit(event)
        finally:
            stop_task.cancel()

    async def _replay_missed(self) -> None:
        url = f"{self._receiver_url}/events/recent"
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    url,
                    params={"after_id": self._last_id, "limit": 500},
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                if r.status_code != 200:
                    log.warning("replay_failed", status=r.status_code)
                    return
                for event in r.json().get("events", []):
                    self._track_id(event)
                    self.event.emit(event)
        except Exception as exc:
            log.warning("replay_error", error=str(exc))

    def _track_id(self, event: dict[str, Any]) -> None:
        eid = event.get("id")
        if isinstance(eid, int) and eid > self._last_id:
            self._last_id = eid
