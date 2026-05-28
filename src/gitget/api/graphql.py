"""Async GraphQL client for GitHub.

GitHub Discussions, Projects v2, and many newer features are GraphQL-only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import structlog

from gitget.api import ratelimit
from gitget.api.rest import ACCEPT, API_VERSION, USER_AGENT, GitHubAPIError
from gitget.config import Settings

log = structlog.get_logger(__name__)

TokenProvider = Callable[[], "str | None"]


class GraphQLClient:
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
        self._clients: dict[int, tuple[asyncio.AbstractEventLoop, httpx.AsyncClient]] = {}
        self.rate_limit = ratelimit.RateLimitState(resource="graphql")

    def _client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        for key in list(self._clients):
            stored_loop, _ = self._clients[key]
            if stored_loop.is_closed():
                del self._clients[key]
        key = id(loop)
        if key not in self._clients:
            self._clients[key] = (
                loop,
                httpx.AsyncClient(
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

    async def __aenter__(self) -> GraphQLClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        max_attempts: int = 5,
    ) -> dict[str, Any]:
        token = self._token_provider()
        if hasattr(token, "__await__"):
            token = await token  # type: ignore[misc]

        headers = {
            "Accept": ACCEPT,
            "X-GitHub-Api-Version": API_VERSION,
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        body = {"query": query, "variables": variables or {}}

        for attempt in range(max_attempts):
            r = await self._client().post(
                self._settings.graphql_url, json=body, headers=headers
            )
            self.rate_limit = ratelimit.RateLimitState.from_response(r, resource="graphql")

            if r.status_code == 200:
                data = r.json()
                if "errors" in data:
                    # GitHub returns 200 even on GraphQL errors; surface them
                    raise GitHubAPIError(200, data["errors"], self._settings.graphql_url)
                return data["data"]

            if ratelimit.is_retryable_status(r.status_code):
                if await ratelimit.handle_retry_after(r):
                    continue
                if self.rate_limit.exhausted:
                    await ratelimit.sleep_until_reset(self.rate_limit)
                    continue
                await ratelimit.backoff_sleep(attempt)
                continue

            try:
                err_body: Any = r.json()
            except ValueError:
                err_body = r.text
            raise GitHubAPIError(r.status_code, err_body, self._settings.graphql_url)

        raise GitHubAPIError(0, "max attempts exceeded", self._settings.graphql_url)
