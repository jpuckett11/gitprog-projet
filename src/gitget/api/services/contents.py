"""Repository contents endpoints (file tree + raw content)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Literal

from gitget.api.rest import GitHubAPIError, RestClient


@dataclass(slots=True)
class ContentEntry:
    """One entry returned by /repos/{owner}/{repo}/contents/{path}."""

    name: str
    path: str
    type: Literal["file", "dir", "symlink", "submodule"]
    size: int
    sha: str
    html_url: str | None = None
    download_url: str | None = None


@dataclass(slots=True)
class FileBlob:
    path: str
    sha: str
    size: int
    encoding: str  # "base64" or "none"
    content_b64: str | None = None  # set when encoding == "base64"

    def decode_bytes(self) -> bytes | None:
        if self.encoding != "base64" or self.content_b64 is None:
            return None
        # GitHub wraps base64 with newlines; b64decode tolerates them
        return base64.b64decode(self.content_b64)


class ContentsService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    async def list_dir(
        self, owner: str, repo: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        """List a directory. path='' returns the repo root.

        Returns [] for empty repos (GitHub returns 404 with "This repository is empty").
        """
        params: dict[str, str] = {}
        if ref:
            params["ref"] = ref
        try:
            raw = await self._rest.get(
                f"/repos/{owner}/{repo}/contents/{path}".rstrip("/"),
                params=params or None,
            )
        except GitHubAPIError as exc:
            if exc.status == 404 and _is_empty_repo(exc.body):
                return []
            raise
        # If `path` points at a file, /contents returns an object, not a list.
        if isinstance(raw, dict):
            return [_entry(raw)]
        return [_entry(e) for e in raw]

    async def get_file(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> FileBlob:
        """Fetch a single file's metadata + base64 content."""
        params: dict[str, str] = {}
        if ref:
            params["ref"] = ref
        raw = await self._rest.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params=params or None,
        )
        return FileBlob(
            path=raw["path"],
            sha=raw["sha"],
            size=raw.get("size", 0),
            encoding=raw.get("encoding", "none"),
            content_b64=raw.get("content"),
        )

    async def list_branches(self, owner: str, repo: str) -> list[str]:
        out: list[str] = []
        async for raw in self._rest.paginate(
            f"/repos/{owner}/{repo}/branches", max_pages=2
        ):
            out.append(raw["name"])
        return out


def _is_empty_repo(body: object) -> bool:
    if isinstance(body, dict):
        msg = body.get("message", "")
        return isinstance(msg, str) and "empty" in msg.lower()
    return False


def _entry(raw: dict) -> ContentEntry:
    return ContentEntry(
        name=raw["name"],
        path=raw["path"],
        type=raw["type"],
        size=raw.get("size", 0),
        sha=raw["sha"],
        html_url=raw.get("html_url"),
        download_url=raw.get("download_url"),
    )
