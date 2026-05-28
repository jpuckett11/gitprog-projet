"""High-level service wrappers built on top of RestClient / GraphQLClient."""

from gh_desktop.api.services.actions import ActionsService
from gh_desktop.api.services.discussions import DiscussionsService
from gh_desktop.api.services.issues import IssuesService
from gh_desktop.api.services.members import MembersService
from gh_desktop.api.services.notifications import NotificationsService
from gh_desktop.api.services.orgs import OrgsService
from gh_desktop.api.services.repos import ReposService
from gh_desktop.api.services.secrets import SecretsService
from gh_desktop.api.services.webhooks import WebhooksService

__all__ = [
    "ActionsService",
    "DiscussionsService",
    "IssuesService",
    "MembersService",
    "NotificationsService",
    "OrgsService",
    "ReposService",
    "SecretsService",
    "WebhooksService",
]
