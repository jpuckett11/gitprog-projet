"""User-facing OAuth flows.

Two flows supported:
  - Device flow: for headless/CLI bootstrap. User pastes a code at github.com/login/device.
  - Web flow (loopback): GUI app opens browser to /authorize, captures the callback on
    http://127.0.0.1:<random-port>/callback. PKCE used; no client_secret needed for the
    PKCE path if the OAuth app is configured as "public", otherwise client_secret is loaded
    from the keyring.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import http.server
import secrets
import socket
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from gh_desktop.auth import storage
from gh_desktop.config import Settings


class OAuthError(RuntimeError):
    pass


@dataclass(slots=True)
class TokenResponse:
    access_token: str
    token_type: str
    scope: str
    refresh_token: str | None = None
    expires_in: int | None = None


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------- Device flow ----------


async def device_flow(settings: Settings, scopes: list[str]) -> TokenResponse:
    """Run the device flow. Yields a verification URL/code to print; polls until granted.

    Caller is responsible for displaying user_code and verification_uri to the user
    (we print to stdout here for the CLI bootstrap case).
    """
    if not settings.oauth_client_id:
        raise OAuthError("oauth_client_id is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            settings.device_code_url,
            data={"client_id": settings.oauth_client_id, "scope": " ".join(scopes)},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        body = r.json()

        device_code = body["device_code"]
        user_code = body["user_code"]
        verification_uri = body["verification_uri"]
        interval = int(body.get("interval", 5))
        expires_in = int(body.get("expires_in", 900))

        print(f"\n  Open: {verification_uri}")
        print(f"  Code: {user_code}\n")

        deadline = asyncio.get_event_loop().time() + expires_in
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval)
            poll = await client.post(
                settings.device_token_url,
                data={
                    "client_id": settings.oauth_client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
            )
            data = poll.json()
            if "access_token" in data:
                return _build_token_response(data)
            err = data.get("error")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            if err in {"expired_token", "access_denied"}:
                raise OAuthError(f"device flow failed: {err}")
            # unknown error
            raise OAuthError(f"device flow error: {data}")

        raise OAuthError("device flow timed out")


# ---------- Web (loopback) flow with PKCE ----------


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """One-shot handler that captures the OAuth callback query params."""

    result: ClassVar[dict[str, str]] = {}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = dict(urllib.parse.parse_qsl(parsed.query))
        _CallbackHandler.result.update(params)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body style='font-family:sans-serif;padding:2em'>"
            b"<h2>Authentication complete.</h2>"
            b"<p>You can close this window and return to gh-desktop.</p>"
            b"</body></html>"
        )

    def log_message(self, format: str, *args: Any) -> None:
        pass  # silence default request logging


async def web_flow(settings: Settings, scopes: list[str]) -> TokenResponse:
    """Open browser to /authorize, capture callback, exchange code for token."""
    if not settings.oauth_client_id:
        raise OAuthError("oauth_client_id is not configured")

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    port = _pick_free_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    _CallbackHandler.result = {}
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        params = {
            "client_id": settings.oauth_client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{settings.oauth_authorize_url}?{urllib.parse.urlencode(params)}"
        webbrowser.open(auth_url, new=2)

        # wait up to 5 minutes for the browser callback
        for _ in range(600):
            if "code" in _CallbackHandler.result or "error" in _CallbackHandler.result:
                break
            await asyncio.sleep(0.5)

        if "error" in _CallbackHandler.result:
            raise OAuthError(f"authorize error: {_CallbackHandler.result.get('error')}")
        if "code" not in _CallbackHandler.result:
            raise OAuthError("authorize timed out")
        if _CallbackHandler.result.get("state") != state:
            raise OAuthError("state mismatch (possible CSRF)")

        code = _CallbackHandler.result["code"]
    finally:
        server.shutdown()

    client_secret = storage.load_oauth_client_secret()
    payload = {
        "client_id": settings.oauth_client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    if client_secret:
        payload["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            settings.oauth_token_url,
            data=payload,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        if "access_token" not in data:
            raise OAuthError(f"token exchange failed: {data}")
        return _build_token_response(data)


def _build_token_response(data: dict[str, Any]) -> TokenResponse:
    return TokenResponse(
        access_token=data["access_token"],
        token_type=data.get("token_type", "bearer"),
        scope=data.get("scope", ""),
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
    )
