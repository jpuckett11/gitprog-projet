"""Rate-limit and retry helpers shared by REST and GraphQL clients.

Honours:
  - X-RateLimit-Remaining / X-RateLimit-Reset (primary rate limit)
  - Retry-After header (secondary / abuse rate limits)
  - 5xx transient errors with exponential backoff
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class RateLimitState:
    remaining: int = 5000
    reset_at: float = 0.0  # epoch seconds
    resource: str = "core"

    @classmethod
    def from_response(cls, r: httpx.Response, resource: str = "core") -> RateLimitState:
        remaining = int(r.headers.get("X-RateLimit-Remaining", "5000"))
        reset_at = float(r.headers.get("X-RateLimit-Reset", "0"))
        return cls(remaining=remaining, reset_at=reset_at, resource=resource)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0 and self.reset_at > time.time()


async def sleep_until_reset(state: RateLimitState) -> None:
    delay = max(0.0, state.reset_at - time.time()) + 1.0
    log.warning("rate_limited", resource=state.resource, sleep_seconds=delay)
    await asyncio.sleep(delay)


async def backoff_sleep(attempt: int, *, base: float = 1.0, cap: float = 30.0) -> None:
    """Exponential backoff with full jitter."""
    delay = min(cap, base * (2**attempt))
    await asyncio.sleep(random.uniform(0, delay))


def is_retryable_status(status: int) -> bool:
    return status in {429, 502, 503, 504}


async def handle_retry_after(r: httpx.Response) -> bool:
    """If response carries Retry-After, sleep accordingly. Returns True if waited."""
    ra = r.headers.get("Retry-After")
    if not ra:
        return False
    try:
        delay = float(ra)
    except ValueError:
        return False
    log.warning("retry_after", seconds=delay, url=str(r.request.url))
    await asyncio.sleep(delay)
    return True
