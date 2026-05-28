"""Tests for the FastAPI webhook receiver and HMAC signature."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gh_desktop.receiver import signature
from gh_desktop.receiver.bus import EventBus
from gh_desktop.receiver.server import ReceiverSettings, build_app
from gh_desktop.receiver.storage import EventStore

# ---------- signature ----------

def test_signature_matches() -> None:
    body = b'{"x": 1}'
    sig = signature.expected_signature("secret", body)
    assert signature.verify("secret", body, sig)


def test_signature_rejects_tamper() -> None:
    body = b'{"x": 1}'
    sig = signature.expected_signature("secret", body)
    assert not signature.verify("secret", b'{"x":2}', sig)


def test_signature_rejects_wrong_secret() -> None:
    body = b'{"x": 1}'
    sig = signature.expected_signature("secret", body)
    assert not signature.verify("other", body, sig)


def test_signature_rejects_missing_header() -> None:
    assert not signature.verify("secret", b"{}", None)


# ---------- FastAPI app ----------

@pytest.fixture
def cfg(tmp_path: Path) -> ReceiverSettings:
    return ReceiverSettings(
        webhook_secret="ws-secret",
        subscriber_token="sub-token",
        db_path=tmp_path / "events.db",
    )


@pytest.fixture
def client(cfg: ReceiverSettings):
    app = build_app(cfg)
    with TestClient(app) as c:
        yield c


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_webhook_accepts_valid_signature(client: TestClient, cfg: ReceiverSettings) -> None:
    body = json.dumps({"action": "opened", "repository": {"full_name": "o/r"}}).encode()
    sig = signature.expected_signature(cfg.webhook_secret, body)
    r = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "abc-123",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200
    assert r.json()["accepted"] is True


def test_webhook_rejects_bad_signature(client: TestClient) -> None:
    r = client.post(
        "/webhook",
        content=b"{}",
        headers={
            "X-Hub-Signature-256": "sha256=deadbeef",
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401


def test_events_recent_requires_auth(client: TestClient, cfg: ReceiverSettings) -> None:
    # no auth → 401
    assert client.get("/events/recent").status_code == 401

    # write an event so there's something to read back
    body = json.dumps({"action": "opened", "repository": {"full_name": "o/r"}}).encode()
    sig = signature.expected_signature(cfg.webhook_secret, body)
    client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "d1",
            "Content-Type": "application/json",
        },
    )

    r = client.get(
        "/events/recent",
        headers={"Authorization": f"Bearer {cfg.subscriber_token}"},
    )
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) == 1
    assert events[0]["event_type"] == "issues"
    assert events[0]["repo"] == "o/r"


# ---------- EventStore ----------

@pytest.mark.asyncio
async def test_event_store_dedup_on_delivery_id(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.db")
    await store.init()
    eid1 = await store.insert(
        delivery_id="x", event_type="issues", action="opened",
        repo="o/r", received_at=time.time(), payload={"a": 1},
    )
    eid2 = await store.insert(
        delivery_id="x", event_type="issues", action="opened",
        repo="o/r", received_at=time.time(), payload={"a": 1},
    )
    assert eid1 > 0
    assert eid2 == -1  # duplicate ignored


@pytest.mark.asyncio
async def test_event_store_purge(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.db")
    await store.init()
    old_ts = time.time() - 86400 * 30
    new_ts = time.time()
    await store.insert(
        delivery_id="old", event_type="issues", action=None, repo=None,
        received_at=old_ts, payload={},
    )
    await store.insert(
        delivery_id="new", event_type="issues", action=None, repo=None,
        received_at=new_ts, payload={},
    )
    removed = await store.purge_older_than(time.time() - 86400 * 7)
    assert removed == 1
    remaining = await store.list_recent()
    assert len(remaining) == 1
    assert remaining[0].delivery_id == "new"


# ---------- EventBus ----------

@pytest.mark.asyncio
async def test_event_bus_fanout() -> None:
    bus = EventBus()

    received_a: list[dict] = []
    received_b: list[dict] = []

    async def consumer(sink: list[dict]) -> None:
        async for ev in bus.subscribe():
            sink.append(ev)
            if len(sink) >= 2:
                return

    task_a = asyncio.create_task(consumer(received_a))
    task_b = asyncio.create_task(consumer(received_b))
    await asyncio.sleep(0.05)  # let subscribers register

    await bus.publish({"id": 1})
    await bus.publish({"id": 2})

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=2)
    assert [e["id"] for e in received_a] == [1, 2]
    assert [e["id"] for e in received_b] == [1, 2]
