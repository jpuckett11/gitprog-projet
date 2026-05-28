"""GitHub Search API wrappers.

The search endpoints have a stricter rate limit (30 req/min for authenticated
users) than the rest of the REST API, so callers should debounce in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from gh_desktop.api.rest import RestClient

SearchKind = Literal["issues", "prs", "repos", "code", "users", "discussions"]


@dataclass(slots=True)
class SearchResult:
    kind: SearchKind
    title: str
    url: str  # html_url
    subtitle: str  # repo + meta line
    raw: dict[str, Any]


def _build_query(kind: SearchKind, q: str) -> str:
    # /search/issues takes both issues and PRs; we add the filter ourselves
    if kind == "issues":
        return f"{q} is:issue"
    if kind == "prs":
        return f"{q} is:pr"
    return q


def _endpoint(kind: SearchKind) -> str:
    return {
        "issues": "/search/issues",
        "prs": "/search/issues",
        "repos": "/search/repositories",
        "code": "/search/code",
        "users": "/search/users",
        "discussions": "/search/discussions",  # NOTE: REST has no public discussion search
    }[kind]


class SearchService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def search(
        self,
        kind: SearchKind,
        query: str,
        *,
        per_page: int = 30,
        page: int = 1,
        sort: str | None = None,
    ) -> list[SearchResult]:
        if not query.strip():
            return []
        params: dict[str, Any] = {
            "q": _build_query(kind, query),
            "per_page": per_page,
            "page": page,
        }
        if sort:
            params["sort"] = sort

        endpoint = _endpoint(kind)
        data = await self._rest.get(endpoint, params=params)
        items = data.get("items", []) if isinstance(data, dict) else []
        return [_to_result(kind, it) for it in items]


def _to_result(kind: SearchKind, raw: dict) -> SearchResult:
    if kind in ("issues", "prs"):
        repo = (raw.get("repository_url") or "").rsplit("/", 2)
        repo_name = "/".join(repo[-2:]) if len(repo) >= 2 else "?"
        state = raw.get("state", "")
        labels = ", ".join(lbl["name"] for lbl in raw.get("labels", []) if isinstance(lbl, dict))
        meta = f"{repo_name} · #{raw.get('number','?')} · {state}"
        if labels:
            meta += f" · {labels}"
        return SearchResult(
            kind=kind,
            title=raw.get("title", "(no title)"),
            url=raw.get("html_url", ""),
            subtitle=meta,
            raw=raw,
        )
    if kind == "repos":
        desc = raw.get("description") or ""
        meta = f"⭐ {raw.get('stargazers_count', 0)}"
        if raw.get("language"):
            meta += f" · {raw['language']}"
        if raw.get("updated_at"):
            meta += f" · updated {raw['updated_at'][:10]}"
        return SearchResult(
            kind=kind,
            title=raw.get("full_name", "(no name)"),
            url=raw.get("html_url", ""),
            subtitle=f"{meta} — {desc}",
            raw=raw,
        )
    if kind == "code":
        repo = (raw.get("repository") or {}).get("full_name", "?")
        return SearchResult(
            kind=kind,
            title=raw.get("path", "(no path)"),
            url=raw.get("html_url", ""),
            subtitle=repo,
            raw=raw,
        )
    if kind == "users":
        return SearchResult(
            kind=kind,
            title=raw.get("login", "(no login)"),
            url=raw.get("html_url", ""),
            subtitle=raw.get("type", "User"),
            raw=raw,
        )
    return SearchResult(
        kind=kind,
        title=str(raw)[:80],
        url=raw.get("html_url", ""),
        subtitle="",
        raw=raw,
    )
