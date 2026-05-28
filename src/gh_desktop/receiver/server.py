"""FastAPI webhook receiver.

Endpoints:
  - GET  /healthz        → liveness
  - POST /webhook        → GitHub webhook target (HMAC-verified)
  - GET  /events/recent  → poll-style event log (auth: bearer token)
  - WS   /events         → live event stream (auth: ?token=)

The receiver holds two shared secrets:
  - GITHUB_WEBHOOK_SECRET  used by GitHub to sign payloads (HMAC-SHA256)
  - SUBSCRIBER_TOKEN       used by the desktop client to authenticate to /events

Both come from env vars (so they can be set in the systemd unit) or from a
config file passed via --config.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

from gh_desktop.receiver import signature
from gh_desktop.receiver.bus import EventBus
from gh_desktop.receiver.storage import EventStore

log = structlog.get_logger(__name__)


class ReceiverSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GH_DESKTOP_RECEIVER_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8765
    webhook_secret: str = ""        # GITHUB_WEBHOOK_SECRET
    subscriber_token: str = ""      # SUBSCRIBER_TOKEN
    db_path: Path = Path("/var/lib/gh-desktop-receiver/events.db")
    retention_days: int = 14


def build_app(settings: ReceiverSettings | None = None) -> FastAPI:
    cfg = settings or ReceiverSettings()
    store = EventStore(cfg.db_path)
    bus = EventBus()

    async def _janitor() -> None:
        while True:
            cutoff = time.time() - cfg.retention_days * 86400
            purged = await store.purge_older_than(cutoff)
            if purged:
                log.info("purged_old_events", count=purged)
            await asyncio.sleep(3600)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await store.init()
        log.info("receiver_started", host=cfg.host, port=cfg.port, db=str(cfg.db_path))
        task = asyncio.create_task(_janitor())
        try:
            yield
        finally:
            task.cancel()

    app = FastAPI(title="gh-desktop-receiver", version="0.1.0", lifespan=lifespan)

    # ---------- liveness ----------

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "subscribers": await bus.subscriber_count()}

    # ---------- GitHub webhook ----------

    @app.post("/webhook")
    async def webhook(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None),
        x_github_event: str = Header(...),
        x_github_delivery: str | None = Header(default=None),
    ) -> JSONResponse:
        body = await request.body()

        if not cfg.webhook_secret:
            log.error("webhook_secret_unset")
            raise HTTPException(503, "receiver not configured (webhook_secret unset)")

        if not signature.verify(cfg.webhook_secret, body, x_hub_signature_256):
            log.warning("bad_signature", delivery=x_github_delivery, event_type=x_github_event)
            raise HTTPException(401, "invalid signature")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise HTTPException(400, "invalid JSON body") from e

        repo = (payload.get("repository") or {}).get("full_name")
        action = payload.get("action")

        await store.insert(
            delivery_id=x_github_delivery,
            event_type=x_github_event,
            action=action,
            repo=repo,
            received_at=time.time(),
            payload=payload,
        )

        envelope = {
            "delivery_id": x_github_delivery,
            "event_type": x_github_event,
            "action": action,
            "repo": repo,
            "received_at": time.time(),
            "payload": payload,
        }
        await bus.publish(envelope)
        log.info(
            "webhook_accepted",
            delivery=x_github_delivery,
            event_type=x_github_event,
            action=action,
            repo=repo,
        )
        return JSONResponse({"accepted": True})

    # ---------- event replay ----------

    @app.get("/events/recent")
    async def events_recent(
        after_id: int = 0, limit: int = 500, authorization: str = Header(default="")
    ) -> dict:
        _require_subscriber(cfg, authorization)
        items = await store.list_recent(after_id=after_id, limit=limit)
        return {
            "events": [
                {
                    "id": e.id,
                    "delivery_id": e.delivery_id,
                    "event_type": e.event_type,
                    "action": e.action,
                    "repo": e.repo,
                    "received_at": e.received_at,
                    "payload": e.payload,
                }
                for e in items
            ]
        }

    # ---------- live WS ----------

    @app.websocket("/events")
    async def events_ws(ws: WebSocket, token: str = Query(default="")) -> None:
        if not cfg.subscriber_token or token != cfg.subscriber_token:
            await ws.close(code=4401)
            return
        await ws.accept()
        try:
            async for event in bus.subscribe():
                await ws.send_json(event)
        except WebSocketDisconnect:
            return

    return app


def _require_subscriber(cfg: ReceiverSettings, header: str) -> None:
    if not cfg.subscriber_token:
        raise HTTPException(503, "subscriber_token not configured")
    expected = f"Bearer {cfg.subscriber_token}"
    if header != expected:
        raise HTTPException(401, "invalid subscriber token")
