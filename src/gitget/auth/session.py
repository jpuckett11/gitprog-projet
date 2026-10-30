
from __future__ import annotations

from collections.abc import Awaitable, Callable

from gitget.auth import github_app, storage
from gitget.config import Settings

SyncTokenProvider = Callable[[], "str | None"]
AsyncTokenProvider = Callable[[], Awaitable["str | None"]]


class AuthSession:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings

    def has_user_token(self) -> bool:
        return storage.load_user_token() is not None

    def user_token_provider(self) -> SyncTokenProvider:
        def provider() -> str | None:
            return storage.load_user_token()

        return provider

    def installation_token_provider(self, installation_id: int) -> AsyncTokenProvider:
        settings = self._settings

        async def provider() -> str | None:
            tok = await github_app.get_installation_token(settings, installation_id)
            return tok.token

        return provider
