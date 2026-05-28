"""Authentication: OAuth user flows, GitHub App JWT, and secret storage."""

from gitget.auth import github_app, oauth, storage
from gitget.auth.github_app import (
    AppAuthError,
    InstallationToken,
    get_installation_token,
    list_installations,
    make_jwt,
)
from gitget.auth.oauth import OAuthError, TokenResponse, device_flow, web_flow

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
