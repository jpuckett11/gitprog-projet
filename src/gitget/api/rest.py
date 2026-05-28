"""Async REST client for GitHub.

Features:
  - ETag-based conditional requests via SQLite cache (cuts rate-limit usage)
  - Automatic retry on 429/5xx with Retry-After + backoff
  - Pagination helper that yields items across pages
  - Pluggable auth: either user OAuth token or GitHub App installation token
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

import httpx
import structlog

from gitget.api import cache, ratelimit
from gitget.config import Settings

log = structlog.get_logger(__name__)

USER_AGENT = "gitget/0.1 (+https://obsidianwatch.org)"
ACCEPT = "application/vnd.github+json"
API_VERSION = "2022-11-28"


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, body: Any, url: str) -> None:
        super().__init__(f"GitHub API {status} for {url}: {body}")
        self.status = status
        self.body = body
        self.url = url


TokenProvider = Callable[[], "str | None"] | Callable[[], "Any"]
"""Callable returning a bearer token string (sync) — may be awaited if it returns a coroutine."""


class RestClient:
    """Async HTTP client for GitHub REST API."""

    def __init__(
        self,
        settings: Settings,
        token_provider: TokenProvider,
        *,
        timeout: float = 30.0,
    ) -> None:
        self._settings = settings
        self._token_provider = token_provider
        self._timeout = timeout
        # httpx.AsyncClient binds to whichever event loop first uses it, so when
        # the polling engine's loop and a worker-thread loop share one client
        # the second loop silently fails. Maintain one client per loop.
        self._clients: dict[int, tuple[asyncio.AbstractEventLoop, httpx.AsyncClient]] = {}
        self.rate_limit = ratelimit.RateLimitState()

    def _client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        # Purge entries whose loop has closed
        for key in list(self._clients):
            stored_loop, _ = self._clients[key]
            if stored_loop.is_closed():
                del self._clients[key]
        key = id(loop)
        if key not in self._clients:
            self._clients[key] = (
                loop,
                httpx.AsyncClient(
                    base_url=self._settings.api_base,
                    timeout=self._timeout,
                    http2=True,
                    headers={"User-Agent": USER_AGENT},
                ),
            )
        return self._clients[key][1]

    async def aclose(self) -> None:
        for _, client in list(self._clients.values()):
            await client.aclose()
        self._clients.clear()

    async def __aenter__(self) -> RestClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ---------- core request ----------

    async def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        token = self._token_provider()
        if hasattr(token, "__await__"):
            token = await token  # type: ignore[misc]
        h = {
            "Accept": ACCEPT,
            "X-GitHub-Api-Version": API_VERSION,
        }
        if token:
            h["Authorization"] = f"Bearer {token}"
        if extra:
            h.update(extra)
        return h

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        use_cache: bool = True,
        max_attempts: int = 5,
    ) -> Any:
        cache_key = cache.make_key(method, path, params)

        for attempt in range(max_attempts):
            headers = await self._headers()
            entry: cache.CacheEntry | None = None
            if method.upper() == "GET" and use_cache:
                entry = cache.get(cache_key)
                if entry is not None:
                    headers["If-None-Match"] = entry.etag

            r = await self._client().request(
                method, path, params=params, json=json_body, headers=headers
            )
            self.rate_limit = ratelimit.RateLimitState.from_response(r)

            if r.status_code == 304 and entry is not None:
                return entry.body

            if r.status_code == 200 and method.upper() == "GET" and use_cache:
                etag = r.headers.get("ETag")
                body = r.json()
                if etag:
                    cache.put(cache_key, etag, body)
                return body

            if 200 <= r.status_code < 300:
                if r.status_code in {204, 205} or not r.content:
                    return None
                return r.json()

            if ratelimit.is_retryable_status(r.status_code):
                if await ratelimit.handle_retry_after(r):
                    continue
                if self.rate_limit.exhausted:
                    await ratelimit.sleep_until_reset(self.rate_limit)
                    continue
                await ratelimit.backoff_sleep(attempt)
                continue

            # non-retryable error
            body: Any
            try:
                body = r.json()
            except ValueError:
                body = r.text
            raise GitHubAPIError(r.status_code, body, str(r.request.url))

        raise GitHubAPIError(0, "max attempts exceeded", path)

    # ---------- convenience wrappers ----------

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, json_body: Any = None, **kw: Any) -> Any:
        return await self.request("POST", path, json_body=json_body, use_cache=False, **kw)

    async def patch(self, path: str, json_body: Any = None, **kw: Any) -> Any:
        return await self.request("PATCH", path, json_body=json_body, use_cache=False, **kw)

    async def put(self, path: str, json_body: Any = None, **kw: Any) -> Any:
        return await self.request("PUT", path, json_body=json_body, use_cache=False, **kw)

    async def delete(self, path: str, **kw: Any) -> Any:
        return await self.request("DELETE", path, use_cache=False, **kw)

    async def paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int | None = None,
    ) -> AsyncIterator[Any]:
        """Yield items across paginated REST endpoints.

        Uses page= numeric pagination (most reliable across endpoints). For
        endpoints that return a wrapper object (e.g. /actions/runs), callers
        should iterate at the wrapper level instead of using this helper.
        """
        page = 1
        while True:
            p = dict(params or {})
            p["per_page"] = per_page
            p["page"] = page
            body = await self.request("GET", path, params=p)
            if not isinstance(body, list):
                # Endpoint returned a wrapper — yield it and stop
                yield body
                return
            if not body:
                return
            for item in body:
                yield item
            if len(body) < per_page:
                return
            page += 1
            if max_pages is not None and page > max_pages:
                return


