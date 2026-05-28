"""Webhook endpoints (repo + org)."""

from __future__ import annotations

from typing import Any

from gh_desktop.api.rest import RestClient


class WebhooksService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_repo_hooks(self, owner: str, repo: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        async for raw in self._rest.paginate(f"/repos/{owner}/{repo}/hooks"):
            out.append(raw)
        return out

    async def create_repo_hook(
        self,
        owner: str,
        repo: str,
        *,
        url: str,
        events: list[str],
        secret: str | None = None,
        content_type: str = "json",
        active: bool = True,
    ) -> dict[str, Any]:
        config: dict[str, Any] = {"url": url, "content_type": content_type}
        if secret is not None:
            config["secret"] = secret
        return await self._rest.post(
            f"/repos/{owner}/{repo}/hooks",
            json_body={"name": "web", "events": events, "active": active, "config": config},
        )

    async def delete_repo_hook(self, owner: str, repo: str, hook_id: int) -> None:
        await self._rest.delete(f"/repos/{owner}/{repo}/hooks/{hook_id}")

    async def list_org_hooks(self, org: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        async for raw in self._rest.paginate(f"/orgs/{org}/hooks"):
            out.append(raw)
        return out

    async def create_org_hook(
        self,
        org: str,
        *,
        url: str,
        events: list[str],
        secret: str | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        config: dict[str, Any] = {"url": url, "content_type": "json"}
        if secret is not None:
            config["secret"] = secret
        return await self._rest.post(
            f"/orgs/{org}/hooks",
            json_body={"name": "web", "events": events, "active": active, "config": config},
        )

    async def delete_org_hook(self, org: str, hook_id: int) -> None:
        await self._rest.delete(f"/orgs/{org}/hooks/{hook_id}")
