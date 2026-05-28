"""Pydantic models for GitHub entities.

Only the fields we actually use are modelled — GitHub responses include far more.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _GHBase(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class User(_GHBase):
    id: int
    login: str
    name: str | None = None
    avatar_url: str | None = None
    type: str | None = None


class Repository(_GHBase):
    id: int
    name: str
    full_name: str
    private: bool
    owner: User
    description: str | None = None
    default_branch: str | None = None
    archived: bool = False
    fork: bool = False
    has_discussions: bool = False
    has_issues: bool = True
    pushed_at: datetime | None = None


class Organization(_GHBase):
    id: int
    login: str
    description: str | None = None
    avatar_url: str | None = None


class Label(_GHBase):
    id: int
    name: str
    color: str
    description: str | None = None


class Issue(_GHBase):
    id: int
    number: int
    title: str
    state: Literal["open", "closed"]
    user: User
    body: str | None = None
    labels: list[Label] = Field(default_factory=list)
    assignees: list[User] = Field(default_factory=list)
    comments: int = 0
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    html_url: str
    repository_url: str | None = None
    pull_request: dict | None = None  # presence indicates this issue is actually a PR


class PullRequest(_GHBase):
    id: int
    number: int
    title: str
    state: Literal["open", "closed"]
    draft: bool = False
    merged: bool = False
    user: User
    body: str | None = None
    labels: list[Label] = Field(default_factory=list)
    requested_reviewers: list[User] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    html_url: str
    head_ref: str | None = Field(default=None, alias="head.ref")
    base_ref: str | None = Field(default=None, alias="base.ref")


class NotificationSubject(_GHBase):
    title: str
    url: str | None = None
    latest_comment_url: str | None = None
    type: str  # Issue, PullRequest, Discussion, Commit, Release, ...


class NotificationRepo(_GHBase):
    id: int
    name: str
    full_name: str
    private: bool
    owner: User


class Notification(_GHBase):
    id: str
    unread: bool
    reason: str
    updated_at: datetime
    last_read_at: datetime | None = None
    subject: NotificationSubject
    repository: NotificationRepo
    url: str
    subscription_url: str | None = None


class Discussion(_GHBase):
    """GraphQL-sourced; field names match the GraphQL schema."""

    id: str  # node ID
    number: int
    title: str
    body: str | None = None
    url: str
    category_name: str | None = None
    answer_chosen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    comments_count: int = 0
    author_login: str | None = None
    locked: bool = False
