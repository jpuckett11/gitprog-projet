"""GitHub App JWT signing and installation token exchange.

Flow:
  1. Sign a short-lived (10 min) JWT with the App's private key.
  2. POST /app/installations/{id}/access_tokens with that JWT to receive a 1-hour
     installation access token used for repo-scoped API calls.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import jwt

from gh_desktop.auth import storage
from gh_desktop.config import Settings


class AppAuthError(RuntimeError):
    pass


@dataclass(slots=True)
class InstallationToken:
    token: str
    expires_at: float  # epoch seconds


def make_jwt(app_id: int, private_key_pem: str, *, ttl_seconds: int = 540) -> str:
    """Mint a JWT for the GitHub App. Max 10 min; we use 9 to be safe."""
    now = int(time.time())
    payload = {
        "iat": now - 60,  # 60s clock skew buffer
        "exp": now + ttl_seconds,
        "iss": str(app_id),
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


async def get_installation_token(
    settings: Settings,
    installation_id: int,
    *,
    force_refresh: bool = False,
) -> InstallationToken:
    """Return a valid installation token, refreshing if needed."""
    if not force_refresh:
        cached = storage.load_installation_token(installation_id)
        if cached and not cached.expired and cached.expires_at is not None:
            return InstallationToken(token=cached.value, expires_at=cached.expires_at)

    if settings.github_app_id is None:
        raise AppAuthError("github_app_id is not configured")
    private_key = storage.load_app_private_key()
    if private_key is None:
        raise AppAuthError("GitHub App private key not found in keyring")

    app_jwt = make_jwt(settings.github_app_id, private_key)
    url = f"{settings.api_base}/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        r.raise_for_status()
        body = r.json()

    expires_at = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    epoch = expires_at.replace(tzinfo=UTC).timestamp()
    storage.save_installation_token(installation_id, body["token"], epoch)
    return InstallationToken(token=body["token"], expires_at=epoch)


async def list_installations(settings: Settings) -> list[dict]:
    """Return all installations of the configured App."""
    if settings.github_app_id is None:
        raise AppAuthError("github_app_id is not configured")
    private_key = storage.load_app_private_key()
    if private_key is None:
        raise AppAuthError("GitHub App private key not found in keyring")

    app_jwt = make_jwt(settings.github_app_id, private_key)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{settings.api_base}/app/installations",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        r.raise_for_status()
        return r.json()
