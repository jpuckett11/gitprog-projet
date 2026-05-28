"""Cloudflare Tunnel via the `cloudflared` quick-tunnel mode.

We spawn `cloudflared tunnel --url http://127.0.0.1:<port>` as a child process.
cloudflared prints the public trycloudflare.com URL to stderr; we parse it,
expose it as a Qt signal, and keep the process alive (restart on crash).

No CF account required for quick-tunnels — they're ephemeral and random.
For production, swap this out for a named tunnel via `cloudflared tunnel run`.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import threading
from time import sleep

import structlog
from PySide6.QtCore import QObject, Signal

log = structlog.get_logger(__name__)

_URL_RE = re.compile(r"https://[a-zA-Z0-9.\-]+\.trycloudflare\.com")


class CloudflareTunnel(QObject):
    url_ready = Signal(str)          # public URL string
    state_changed = Signal(str)      # "starting" | "running" | "exited" | "error:<msg>"

    def __init__(
        self,
        local_port: int,
        *,
        cloudflared_path: str = "cloudflared",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._local_port = local_port
        self._bin = cloudflared_path
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._current_url: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._supervise, name="cloudflared", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                with contextlib.suppress(ProcessLookupError):
                    self._proc.kill()
        self._proc = None
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    @property
    def current_url(self) -> str | None:
        return self._current_url

    # ---------- internal ----------

    def _supervise(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            self.state_changed.emit("starting")
            try:
                self._run_once()
                backoff = 1.0
            except FileNotFoundError:
                self.state_changed.emit(
                    f"error:cloudflared binary not found at {self._bin!r} — install it from "
                    "https://github.com/cloudflare/cloudflared/releases"
                )
                return
            except Exception as exc:
                log.warning("cloudflared_crashed", error=str(exc))
                self.state_changed.emit(f"error:{exc}")

            if self._stop.is_set():
                break
            sleep(min(backoff, 30.0))
            backoff *= 2

        self.state_changed.emit("exited")

    def _run_once(self) -> None:
        cmd = [
            self._bin,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{self._local_port}",
            "--no-autoupdate",
        ]
        log.info("starting_cloudflared", cmd=cmd)
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert self._proc.stdout is not None
        self.state_changed.emit("running")
        for line in self._proc.stdout:
            if self._stop.is_set():
                break
            match = _URL_RE.search(line)
            if match and match.group(0) != self._current_url:
                self._current_url = match.group(0)
                log.info("cloudflared_url", url=self._current_url)
                self.url_ready.emit(self._current_url)
        rc = self._proc.wait()
        log.info("cloudflared_exited", rc=rc)
        self._current_url = None
