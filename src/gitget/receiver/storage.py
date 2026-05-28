"""SQLite event log for the webhook receiver.

Each accepted webhook is persisted so the GUI can replay missed events on
reconnect. Schema is minimal — we keep the raw JSON body and a few index keys.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id   TEXT UNIQUE,
    event_type    TEXT NOT NULL,
    action        TEXT,
    repo          TEXT,
    received_at   REAL NOT NULL,
    payload       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS events_repo_idx ON events(repo);
CREATE INDEX IF NOT EXISTS events_received_at_idx ON events(received_at);
"""


@dataclass(slots=True)
class StoredEvent:
    id: int
    delivery_id: str | None
    event_type: str
    action: str | None
    repo: str | None
    received_at: float
    payload: dict


class EventStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    async def insert(
        self,
        *,
        delivery_id: str | None,
        event_type: str,
        action: str | None,
        repo: str | None,
        received_at: float,
        payload: dict,
    ) -> int:
        async with aiosqlite.connect(self._path) as db:
            try:
                cur = await db.execute(
                    "INSERT INTO events(delivery_id, event_type, action, repo, received_at, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (delivery_id, event_type, action, repo, received_at, json.dumps(payload)),
                )
            except aiosqlite.IntegrityError:
                # duplicate delivery_id (GitHub retries the same event) — ignore
                return -1
            await db.commit()
            return cur.lastrowid or 0

    async def list_recent(
        self, *, after_id: int = 0, limit: int = 500
    ) -> list[StoredEvent]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, delivery_id, event_type, action, repo, received_at, payload "
                "FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
                (after_id, limit),
            )
            rows = await cur.fetchall()
            return [_row_to_event(r) for r in rows]

    async def purge_older_than(self, cutoff_epoch: float) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "DELETE FROM events WHERE received_at < ?", (cutoff_epoch,)
            )
            await db.commit()
            return cur.rowcount


def _row_to_event(row: Iterable) -> StoredEvent:
    r = dict(row)
    return StoredEvent(
        id=r["id"],
        delivery_id=r["delivery_id"],
        event_type=r["event_type"],
        action=r["action"],
        repo=r["repo"],
        received_at=r["received_at"],
        payload=json.loads(r["payload"]),
    )
