"""Repo + org secret endpoints.

Note: creating/updating secrets requires libsodium-style encryption with the
repo's public key. We expose `get_public_key` so the caller can encrypt before
calling `put_secret`. Encryption helper lives here.
"""

from __future__ import annotations

import base64

from nacl import encoding, public

from gh_desktop.api.rest import RestClient


def encrypt_secret(public_key_b64: str, value: str) -> str:
    """libsodium sealed box encryption used by GitHub's Actions secrets API."""
    pk = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


class SecretsService:
    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    # ---- repo ----

    async def list_repo_secrets(self, owner: str, repo: str) -> list[dict]:
        data = await self._rest.get(f"/repos/{owner}/{repo}/actions/secrets")
        return data.get("secrets", [])

    async def get_repo_public_key(self, owner: str, repo: str) -> dict:
        return await self._rest.get(f"/repos/{owner}/{repo}/actions/secrets/public-key")

    async def put_repo_secret(
        self, owner: str, repo: str, name: str, *, encrypted_value: str, key_id: str
    ) -> None:
        await self._rest.put(
            f"/repos/{owner}/{repo}/actions/secrets/{name}",
            json_body={"encrypted_value": encrypted_value, "key_id": key_id},
        )

    async def delete_repo_secret(self, owner: str, repo: str, name: str) -> None:
        await self._rest.delete(f"/repos/{owner}/{repo}/actions/secrets/{name}")

    # ---- org ----

    async def list_org_secrets(self, org: str) -> list[dict]:
        data = await self._rest.get(f"/orgs/{org}/actions/secrets")
        return data.get("secrets", [])

    async def get_org_public_key(self, org: str) -> dict:
        return await self._rest.get(f"/orgs/{org}/actions/secrets/public-key")

    async def put_org_secret(
        self,
        org: str,
        name: str,
        *,
        encrypted_value: str,
        key_id: str,
        visibility: str = "all",
    ) -> None:
        await self._rest.put(
            f"/orgs/{org}/actions/secrets/{name}",
            json_body={
                "encrypted_value": encrypted_value,
                "key_id": key_id,
                "visibility": visibility,
            },
        )

    async def delete_org_secret(self, org: str, name: str) -> None:
        await self._rest.delete(f"/orgs/{org}/actions/secrets/{name}")
