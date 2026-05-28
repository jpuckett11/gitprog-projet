"""Pull Request endpoints: list, get, files w/ patches, reviews, merge."""

from __future__ import annotations

from typing import Any, Literal

from gitget.api.rest import RestClient

ReviewEvent = Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"]


class PullsService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_for_repo(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "open",
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        params = {"state": state, "sort": "updated", "direction": "desc"}
        async for raw in self._rest.paginate(
            f"/repos/{owner}/{repo}/pulls", params=params, max_pages=max_pages
        ):
            out.append(raw)
        return out

    async def get(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return await self._rest.get(f"/repos/{owner}/{repo}/pulls/{number}")

    async def list_files(
        self, owner: str, repo: str, number: int, *, max_pages: int = 5
    ) -> list[dict[str, Any]]:
        """Returns one entry per changed file with a `patch` field (unified diff)."""
        out: list[dict[str, Any]] = []
        async for raw in self._rest.paginate(
            f"/repos/{owner}/{repo}/pulls/{number}/files", max_pages=max_pages
        ):
            out.append(raw)
        return out

    async def list_review_comments(
        self, owner: str, repo: str, number: int
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        async for raw in self._rest.paginate(
            f"/repos/{owner}/{repo}/pulls/{number}/comments"
        ):
            out.append(raw)
        return out

    async def create_review(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        event: ReviewEvent,
        body: str = "",
        commit_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"event": event, "body": body}
        if commit_id:
            payload["commit_id"] = commit_id
        return await self._rest.post(
            f"/repos/{owner}/{repo}/pulls/{number}/reviews", json_body=payload
        )

    async def add_review_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        body: str,
        commit_id: str,
        path: str,
        line: int,
        side: str = "RIGHT",
    ) -> dict[str, Any]:
        """Single inline comment on a file line."""
        return await self._rest.post(
            f"/repos/{owner}/{repo}/pulls/{number}/comments",
            json_body={
                "body": body,
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "side": side,
            },
        )

    async def merge(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        method: Literal["merge", "squash", "rebase"] = "merge",
        commit_title: str | None = None,
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"merge_method": method}
        if commit_title is not None:
            payload["commit_title"] = commit_title
        if commit_message is not None:
            payload["commit_message"] = commit_message
        return await self._rest.put(
            f"/repos/{owner}/{repo}/pulls/{number}/merge", json_body=payload
        )
