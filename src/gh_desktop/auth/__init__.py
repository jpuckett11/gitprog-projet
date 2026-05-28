"""Authentication: OAuth user flows, GitHub App JWT, and secret storage."""

from gh_desktop.auth import github_app, oauth, storage
from gh_desktop.auth.github_app import (
    AppAuthError,
    InstallationToken,
    get_installation_token,
    list_installations,
    make_jwt,
)
from gh_desktop.auth.oauth import OAuthError, TokenResponse, device_flow, web_flow

__all__ = [
    "AppAuthError",
    "InstallationToken",
    "OAuthError",
    "TokenResponse",
    "device_flow",
    "get_installation_token",
    "github_app",
    "list_installations",
    "make_jwt",
    "oauth",
    "storage",
    "web_flow",
]
