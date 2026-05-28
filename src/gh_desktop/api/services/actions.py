"""Actions / workflow run endpoints."""

from __future__ import annotations

from typing import Any

from gh_desktop.api.rest import RestClient


class ActionsService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        *,
        status: str | None = None,
        max_pages: int = 3,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        out: list[dict[str, Any]] = []
        async for raw in self._rest.paginate(
            f"/repos/{owner}/{repo}/actions/runs", params=params, max_pages=max_pages
        ):
            # paginated workflow_runs returns the wrapper {total_count, workflow_runs: [...]}
            # but per_page filtering goes via params; httpx returns whatever GitHub returns.
            # The /runs endpoint paginates inside the wrapper object, so we handle it specially.
            if isinstance(raw, dict) and "workflow_runs" in raw:
                out.extend(raw["workflow_runs"])
            else:
                out.append(raw)
        return out

    async def list_workflows(self, owner: str, repo: str) -> list[dict[str, Any]]:
        data = await self._rest.get(f"/repos/{owner}/{repo}/actions/workflows")
        return data.get("workflows", [])

    async def cancel_run(self, owner: str, repo: str, run_id: int) -> None:
        await self._rest.post(f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel")

    async def rerun(self, owner: str, repo: str, run_id: int) -> None:
        await self._rest.post(f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun")
