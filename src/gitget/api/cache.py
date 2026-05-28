"""ETag-aware response cache.

GitHub returns ETag on most GET responses. Sending If-None-Match returns 304 (no
content) without consuming rate-limit budget. We persist ETag + body in SQLite so
polling stays cheap across app restarts.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from gitget.config import ETAG_CACHE_DB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS etag_cache (
    cache_key   TEXT PRIMARY KEY,
    etag        TEXT NOT NULL,
    body        TEXT NOT NULL,
    fetched_at  REAL NOT NULL
);
"""


@dataclass(slots=True)
class CacheEntry:
    etag: str
    body: Any
    fetched_at: float


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(ETAG_CACHE_DB)
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def make_key(method: str, url: str, params: dict | None = None) -> str:
    suffix = (
        "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else ""
    )
    return f"{method.upper()} {url}{suffix}"


def get(cache_key: str) -> CacheEntry | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT etag, body, fetched_at FROM etag_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    if row is None:
        return None
    etag, body, fetched_at = row
    return CacheEntry(etag=etag, body=json.loads(body), fetched_at=fetched_at)


def put(cache_key: str, etag: str, body: Any) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO etag_cache (cache_key, etag, body, fetched_at) "
            "VALUES (?, ?, ?, ?)",
            (cache_key, etag, json.dumps(body), time.time()),
        )


def clear() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM etag_cache")
