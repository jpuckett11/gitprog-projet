"""Relative timestamp formatting."""

from __future__ import annotations

from datetime import UTC, datetime


def humanize(ts: datetime | str | None) -> str:
    """Return a short relative string like '3m', '2h', '5d', '2025-04-01'."""
    if ts is None:
        return ""
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    now = datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    delta = now - ts
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    if seconds < 86400 * 14:
        return f"{seconds // 86400}d"
    return ts.date().isoformat()
