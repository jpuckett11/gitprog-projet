"""Tests for the Phase 2.5/3 services: Search, Pulls, Contents."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from gitget.api.rest import RestClient
from gitget.api.services import ContentsService, PullsService, SearchService
from gitget.config import Settings


@pytest.fixture
def client() -> RestClient:
    return RestClient(Settings(), token_provider=lambda: "test-token")


# ---------- Search ----------


@pytest.mark.asyncio
async def test_search_issues(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/search/issues?q=bug+is%3Aissue&per_page=30&page=1",
        json={
            "items": [
                {
                    "title": "Crash on load",
                    "html_url": "https://github.com/o/r/issues/1",
                    "number": 1,
                    "state": "open",
                    "labels": [{"name": "bug"}],
                    "repository_url": "https://api.github.com/repos/o/r",
                }
            ]
        },
    )
    results = await SearchService(client).search("issues", "bug")
    assert len(results) == 1
    assert results[0].title == "Crash on load"
    assert "o/r" in results[0].subtitle
    assert results[0].url.endswith("/issues/1")


@pytest.mark.asyncio
async def test_search_repos(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/search/repositories?q=octocat&per_page=30&page=1",
        json={
            "items": [
                {
                    "full_name": "octocat/Hello-World",
                    "description": "demo",
                    "html_url": "https://github.com/octocat/Hello-World",
                    "stargazers_count": 12,
                    "language": "Python",
                }
            ]
        },
    )
    results = await SearchService(client).search("repos", "octocat")
    assert results[0].title == "octocat/Hello-World"


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(client: RestClient) -> None:
    results = await SearchService(client).search("issues", "   ")
    assert results == []


# ---------- Pulls ----------


@pytest.mark.asyncio
async def test_pulls_list(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/pulls?state=open&sort=updated&direction=desc&per_page=100&page=1",
        json=[
            {
                "number": 1,
                "title": "Fix bug",
                "state": "open",
                "draft": False,
                "user": {"login": "alice"},
                "head": {"ref": "feature"},
                "base": {"ref": "main"},
                "updated_at": "2025-05-01T00:00:00Z",
                "html_url": "h",
            }
        ],
    )
    out = await PullsService(client).list_for_repo("o", "r", max_pages=1)
    assert len(out) == 1
    assert out[0]["title"] == "Fix bug"


@pytest.mark.asyncio
async def test_pulls_list_files(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/pulls/5/files?per_page=100&page=1",
        json=[
            {
                "filename": "src/foo.py",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
                "patch": "@@ -1 +1,3 @@\n-old\n+new1\n+new2",
            }
        ],
    )
    files = await PullsService(client).list_files("o", "r", 5, max_pages=1)
    assert len(files) == 1
    assert "@@" in files[0]["patch"]


@pytest.mark.asyncio
async def test_pulls_create_review(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/pulls/5/reviews",
        method="POST",
        json={"id": 99, "state": "APPROVED"},
    )
    out = await PullsService(client).create_review("o", "r", 5, event="APPROVE", body="LGTM")
    assert out["id"] == 99


@pytest.mark.asyncio
async def test_pulls_add_review_comment(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/pulls/5/comments",
        method="POST",
        json={"id": 200, "body": "nit"},
    )
    out = await PullsService(client).add_review_comment(
        "o", "r", 5, body="nit", commit_id="deadbeef", path="src/foo.py", line=2
    )
    assert out["id"] == 200


@pytest.mark.asyncio
async def test_pulls_merge(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/pulls/5/merge",
        method="PUT",
        json={"merged": True, "sha": "abc"},
    )
    out = await PullsService(client).merge("o", "r", 5, method="squash")
    assert out["merged"] is True


# ---------- Contents ----------


@pytest.mark.asyncio
async def test_contents_list_dir(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/contents",
        json=[
            {"name": "src", "path": "src", "type": "dir", "size": 0, "sha": "a1"},
            {"name": "README.md", "path": "README.md", "type": "file", "size": 100, "sha": "b2",
             "html_url": "h", "download_url": "d"},
        ],
    )
    entries = await ContentsService(client).list_dir("o", "r")
    assert len(entries) == 2
    assert entries[0].type == "dir"
    assert entries[1].size == 100


@pytest.mark.asyncio
async def test_contents_list_dir_empty_repo(httpx_mock: HTTPXMock, client: RestClient) -> None:
    """The 404 'This repository is empty' should be swallowed → []."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/contents",
        status_code=404,
        json={"message": "This repository is empty.", "documentation_url": "..."},
    )
    entries = await ContentsService(client).list_dir("o", "r")
    assert entries == []


@pytest.mark.asyncio
async def test_contents_get_file(httpx_mock: HTTPXMock, client: RestClient) -> None:
    import base64
    raw_bytes = b"hello world"
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/contents/README.md",
        json={
            "name": "README.md", "path": "README.md", "sha": "abc", "size": len(raw_bytes),
            "encoding": "base64",
            "content": base64.b64encode(raw_bytes).decode(),
        },
    )
    blob = await ContentsService(client).get_file("o", "r", "README.md")
    assert blob.decode_bytes() == raw_bytes


@pytest.mark.asyncio
async def test_contents_list_branches(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/branches?per_page=100&page=1",
        json=[{"name": "main"}, {"name": "develop"}],
    )
    out = await ContentsService(client).list_branches("o", "r")
    assert out == ["main", "develop"]
