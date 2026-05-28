"""Repository endpoints."""

from __future__ import annotations

from gh_desktop.api.rest import RestClient
from gh_desktop.models import Repository


class ReposService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_for_authenticated_user(
        self,
        *,
        affiliation: str = "owner,collaborator,organization_member",
        sort: str = "updated",
        max_pages: int | None = None,
    ) -> list[Repository]:
        params = {"affiliation": affiliation, "sort": sort}
        out: list[Repository] = []
        async for raw in self._rest.paginate("/user/repos", params=params, max_pages=max_pages):
            out.append(Repository.model_validate(raw))
        return out

    async def list_for_org(self, org: str, *, max_pages: int | None = None) -> list[Repository]:
        out: list[Repository] = []
        async for raw in self._rest.paginate(f"/orgs/{org}/repos", max_pages=max_pages):
            out.append(Repository.model_validate(raw))
        return out

    async def get(self, owner: str, repo: str) -> Repository:
        raw = await self._rest.get(f"/repos/{owner}/{repo}")
        return Repository.model_validate(raw)
