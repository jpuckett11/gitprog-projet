"""GitHub Notifications endpoints."""

from __future__ import annotations

from gitget.api.rest import RestClient
from gitget.models import Notification


class NotificationsService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list(
        self,
        *,
        all: bool = False,
        participating: bool = False,
        since: str | None = None,
        max_pages: int | None = None,
    ) -> list[Notification]:
        params: dict[str, str] = {}
        if all:
            params["all"] = "true"
        if participating:
            params["participating"] = "true"
        if since is not None:
            params["since"] = since
        out: list[Notification] = []
        async for raw in self._rest.paginate("/notifications", params=params, max_pages=max_pages):
            out.append(Notification.model_validate(raw))
        return out

    async def mark_thread_read(self, thread_id: str) -> None:
        await self._rest.patch(f"/notifications/threads/{thread_id}")

    async def mark_all_read(self) -> None:
        await self._rest.put("/notifications", json_body={})

    async def unsubscribe(self, thread_id: str) -> None:
        await self._rest.delete(f"/notifications/threads/{thread_id}/subscription")

    async def get_thread(self, thread_id: str) -> dict:
        return await self._rest.get(f"/notifications/threads/{thread_id}")
