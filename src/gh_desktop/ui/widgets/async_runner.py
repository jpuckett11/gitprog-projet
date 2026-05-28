"""Run async coroutines from Qt code without blocking the GUI.

Each `run_async` call spins up a short-lived QThread that drives the coroutine in
its own asyncio event loop. The success/failure signals are delivered back on
the main thread.

For long-lived async work (like the polling engine), use PollingEngine instead.
"""

from __future__ import annotations

import asyncio

from PySide6.QtCore import QObject, QThread, Signal


class _AsyncWorker(QThread):
    success = Signal(object)
    failure = Signal(object)

    def __init__(self, coro_factory, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._coro_factory = coro_factory

    def run(self) -> None:
        try:
            result = asyncio.run(self._coro_factory())
        except Exception as exc:
            self.failure.emit(exc)
            return
        self.success.emit(result)


def run_async(
    parent: QObject,
    coro_factory,
    *,
    on_success=None,
    on_failure=None,
) -> _AsyncWorker:
    """Run `coro_factory()` (a 0-arg callable returning a coroutine) in a thread.

    Returns the worker so the caller can hold a ref (Qt will GC it otherwise).
    Pass a *factory* (zero-arg callable) — not an awaitable — so the coroutine
    is constructed inside the worker thread.
    """
    worker = _AsyncWorker(coro_factory, parent)
    if on_success is not None:
        worker.success.connect(on_success)
    if on_failure is not None:
        worker.failure.connect(on_failure)
    worker.start()
    return worker
