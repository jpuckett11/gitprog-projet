"""Organization endpoints."""

from __future__ import annotations

from gitget.api.rest import RestClient
from gitget.models import Organization


class OrgsService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_for_authenticated_user(self) -> list[Organization]:
        out: list[Organization] = []
        async for raw in self._rest.paginate("/user/orgs"):
            out.append(Organization.model_validate(raw))
        return out

    async def get(self, org: str) -> Organization:
        raw = await self._rest.get(f"/orgs/{org}")
        return Organization.model_validate(raw)
