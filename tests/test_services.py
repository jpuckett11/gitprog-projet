"""Unit tests for API service classes using pytest-httpx."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from gh_desktop.api.rest import RestClient
from gh_desktop.api.services import (
    ActionsService,
    IssuesService,
    NotificationsService,
    OrgsService,
    ReposService,
    SecretsService,
    WebhooksService,
)
from gh_desktop.config import Settings


@pytest.fixture
def client() -> RestClient:
    return RestClient(Settings(), token_provider=lambda: "test-token")


# ---------- Notifications ----------

@pytest.mark.asyncio
async def test_notifications_list(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/notifications?per_page=100&page=1",
        json=[
            {
                "id": "1",
                "unread": True,
                "reason": "mention",
                "updated_at": "2025-05-01T00:00:00Z",
                "subject": {"title": "PR title", "url": "x", "type": "PullRequest"},
                "repository": {
                    "id": 99,
                    "name": "foo",
                    "full_name": "octo/foo",
                    "private": False,
                    "owner": {"id": 1, "login": "octo"},
                },
                "url": "u",
            }
        ],
    )
    svc = NotificationsService(client)
    out = await svc.list(max_pages=1)
    assert len(out) == 1
    assert out[0].subject.type == "PullRequest"
    assert out[0].repository.full_name == "octo/foo"


@pytest.mark.asyncio
async def test_notifications_mark_thread_read(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/notifications/threads/123",
        method="PATCH",
        status_code=205,
    )
    await NotificationsService(client).mark_thread_read("123")


@pytest.mark.asyncio
async def test_notifications_mark_all_read(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/notifications",
        method="PUT",
        status_code=205,
    )
    await NotificationsService(client).mark_all_read()


# ---------- Repos ----------

@pytest.mark.asyncio
async def test_repos_list_for_user(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/user/repos?affiliation=owner%2Ccollaborator%2Corganization_member&sort=updated&per_page=100&page=1",
        json=[
            {
                "id": 1,
                "name": "alpha",
                "full_name": "u/alpha",
                "private": False,
                "owner": {"id": 1, "login": "u"},
            }
        ],
    )
    out = await ReposService(client).list_for_authenticated_user(max_pages=1)
    assert out[0].full_name == "u/alpha"


# ---------- Orgs ----------

@pytest.mark.asyncio
async def test_orgs_list(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/user/orgs?per_page=100&page=1",
        json=[{"id": 5, "login": "acme"}],
    )
    out = await OrgsService(client).list_for_authenticated_user()
    assert out[0].login == "acme"


# ---------- Issues ----------

@pytest.mark.asyncio
async def test_issues_list_filters_prs(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/issues?state=open&per_page=100&page=1",
        json=[
            {
                "id": 1, "number": 1, "title": "issue", "state": "open",
                "user": {"id": 1, "login": "a"},
                "created_at": "2025-05-01T00:00:00Z",
                "updated_at": "2025-05-01T00:00:00Z",
                "html_url": "h",
            },
            {
                "id": 2, "number": 2, "title": "pr", "state": "open",
                "user": {"id": 1, "login": "a"},
                "created_at": "2025-05-01T00:00:00Z",
                "updated_at": "2025-05-01T00:00:00Z",
                "html_url": "h",
                "pull_request": {"url": "x"},  # marks this as a PR
            },
        ],
    )
    out = await IssuesService(client).list_for_repo("o", "r", max_pages=1)
    assert len(out) == 1
    assert out[0].title == "issue"


# ---------- Secrets ----------

@pytest.mark.asyncio
async def test_secrets_list_repo(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/actions/secrets",
        json={"total_count": 1, "secrets": [{"name": "DEPLOY_KEY", "updated_at": "2025-05-01T00:00:00Z"}]},
    )
    out = await SecretsService(client).list_repo_secrets("o", "r")
    assert out[0]["name"] == "DEPLOY_KEY"


@pytest.mark.asyncio
async def test_secrets_put_repo(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/actions/secrets/X",
        method="PUT",
        status_code=204,
    )
    await SecretsService(client).put_repo_secret(
        "o", "r", "X", encrypted_value="abc", key_id="k1"
    )


# ---------- Webhooks ----------

@pytest.mark.asyncio
async def test_webhooks_list_repo(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/hooks?per_page=100&page=1",
        json=[{"id": 7, "events": ["push"], "active": True, "config": {"url": "https://x"}}],
    )
    out = await WebhooksService(client).list_repo_hooks("o", "r")
    assert out[0]["id"] == 7


@pytest.mark.asyncio
async def test_webhooks_create_repo(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/hooks",
        method="POST",
        json={"id": 42},
    )
    out = await WebhooksService(client).create_repo_hook(
        "o", "r", url="https://x", events=["push"]
    )
    assert out["id"] == 42


# ---------- Actions ----------

@pytest.mark.asyncio
async def test_actions_list_runs(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/actions/runs?per_page=100&page=1",
        json={
            "total_count": 1,
            "workflow_runs": [
                {"id": 1, "name": "CI", "run_number": 5, "status": "completed",
                 "conclusion": "success", "updated_at": "2025-05-01T00:00:00Z",
                 "html_url": "https://x"}
            ],
        },
    )
    out = await ActionsService(client).list_workflow_runs("o", "r", max_pages=1)
    assert len(out) == 1
    assert out[0]["name"] == "CI"


# ---------- Rate-limit handling ----------

@pytest.mark.asyncio
async def test_rest_retries_on_5xx(httpx_mock: HTTPXMock, client: RestClient) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/user/orgs?per_page=100&page=1",
        status_code=502,
    )
    httpx_mock.add_response(
        url="https://api.github.com/user/orgs?per_page=100&page=1",
        json=[{"id": 1, "login": "a"}],
    )
    out = await OrgsService(client).list_for_authenticated_user()
    assert out[0].login == "a"
