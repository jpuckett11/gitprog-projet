"""Org member endpoints."""

from __future__ import annotations

from gh_desktop.api.rest import RestClient
from gh_desktop.models import User


class MembersService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_org_members(
        self, org: str, *, role: str = "all", max_pages: int | None = None
    ) -> list[User]:
        params = {"role": role}
        out: list[User] = []
        async for raw in self._rest.paginate(
            f"/orgs/{org}/members", params=params, max_pages=max_pages
        ):
            out.append(User.model_validate(raw))
        return out

    async def get_membership(self, org: str, username: str) -> dict:
        return await self._rest.get(f"/orgs/{org}/memberships/{username}")
