"""Issue endpoints."""

from __future__ import annotations

from typing import Any

from gh_desktop.api.rest import RestClient
from gh_desktop.models import Issue


class IssuesService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_for_repo(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "open",
        labels: list[str] | None = None,
        max_pages: int | None = None,
    ) -> list[Issue]:
        params: dict[str, Any] = {"state": state}
        if labels:
            params["labels"] = ",".join(labels)
        out: list[Issue] = []
        async for raw in self._rest.paginate(
            f"/repos/{owner}/{repo}/issues", params=params, max_pages=max_pages
        ):
            # GitHub returns PRs alongside issues; filter them out
            if raw.get("pull_request"):
                continue
            out.append(Issue.model_validate(raw))
        return out

    async def get(self, owner: str, repo: str, number: int) -> Issue:
        raw = await self._rest.get(f"/repos/{owner}/{repo}/issues/{number}")
        return Issue.model_validate(raw)

    async def list_comments(self, owner: str, repo: str, number: int) -> list[dict]:
        out: list[dict] = []
        async for raw in self._rest.paginate(
            f"/repos/{owner}/{repo}/issues/{number}/comments"
        ):
            out.append(raw)
        return out

    async def add_comment(self, owner: str, repo: str, number: int, body: str) -> dict:
        return await self._rest.post(
            f"/repos/{owner}/{repo}/issues/{number}/comments", json_body={"body": body}
        )

    async def set_state(self, owner: str, repo: str, number: int, state: str) -> Issue:
        raw = await self._rest.patch(
            f"/repos/{owner}/{repo}/issues/{number}", json_body={"state": state}
        )
        return Issue.model_validate(raw)
