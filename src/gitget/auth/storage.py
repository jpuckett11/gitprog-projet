"""Secret storage via libsecret (through python-keyring).

Stores:
  - user OAuth access token + refresh token (per host)
  - GitHub App private key (PEM)
  - cached installation tokens (with expiry encoded in value)
"""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass

import keyring

from gitget.config import KEYRING_SERVICE

_USER_TOKEN_KEY = "user-oauth"
_USER_REFRESH_KEY = "user-oauth-refresh"
_APP_PRIVATE_KEY = "github-app-private-key"
_OAUTH_CLIENT_SECRET = "oauth-client-secret"
_INSTALLATION_TOKEN_PREFIX = "installation-token:"
_SUBSCRIBER_TOKEN_KEY = "receiver-subscriber-token"


@dataclass(slots=True)
class StoredToken:
    value: str
    expires_at: float | None = None  # epoch seconds; None means no expiry

    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - 30  # 30s safety margin


def _set(name: str, value: str) -> None:
    keyring.set_password(KEYRING_SERVICE, name, value)


def _get(name: str) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, name)


def _delete(name: str) -> None:
    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(KEYRING_SERVICE, name)


def save_user_token(token: str, refresh_token: str | None = None) -> None:
    _set(_USER_TOKEN_KEY, token)
    if refresh_token is not None:
        _set(_USER_REFRESH_KEY, refresh_token)


def load_user_token() -> str | None:
    return _get(_USER_TOKEN_KEY)


def load_user_refresh_token() -> str | None:
    return _get(_USER_REFRESH_KEY)


def clear_user_token() -> None:
    _delete(_USER_TOKEN_KEY)
    _delete(_USER_REFRESH_KEY)


def save_oauth_client_secret(secret: str) -> None:
    _set(_OAUTH_CLIENT_SECRET, secret)


def load_oauth_client_secret() -> str | None:
    return _get(_OAUTH_CLIENT_SECRET)


def save_app_private_key(pem: str) -> None:
    _set(_APP_PRIVATE_KEY, pem)


def load_app_private_key() -> str | None:
    return _get(_APP_PRIVATE_KEY)


def save_subscriber_token(token: str) -> None:
    _set(_SUBSCRIBER_TOKEN_KEY, token)


def load_subscriber_token() -> str | None:
    return _get(_SUBSCRIBER_TOKEN_KEY)


def save_installation_token(installation_id: int, token: str, expires_at: float) -> None:
    payload = json.dumps({"token": token, "expires_at": expires_at})
    _set(f"{_INSTALLATION_TOKEN_PREFIX}{installation_id}", payload)


def load_installation_token(installation_id: int) -> StoredToken | None:
    raw = _get(f"{_INSTALLATION_TOKEN_PREFIX}{installation_id}")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return StoredToken(value=data["token"], expires_at=data.get("expires_at"))
