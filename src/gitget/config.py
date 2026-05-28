"""Application configuration and platform paths."""

from __future__ import annotations

from pathlib import Path

from platformdirs import PlatformDirs
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DIRS = PlatformDirs("gitget", "obsidianwatch", roaming=False)
_LEGACY_DIRS = PlatformDirs("gh-desktop", "obsidianwatch", roaming=False)

CONFIG_DIR: Path = Path(_DIRS.user_config_dir)
DATA_DIR: Path = Path(_DIRS.user_data_dir)
CACHE_DIR: Path = Path(_DIRS.user_cache_dir)
LOG_DIR: Path = Path(_DIRS.user_log_dir)

for _d in (CONFIG_DIR, DATA_DIR, CACHE_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CONFIG_FILE: Path = CONFIG_DIR / "config.toml"
ETAG_CACHE_DB: Path = CACHE_DIR / "etag_cache.db"

KEYRING_SERVICE = "gitget"
_LEGACY_KEYRING_SERVICE = "gh-desktop"


def migrate_legacy_state() -> list[str]:
    """One-shot migration from gh-desktop names to gitget.

    Idempotent and safe to call at every startup. Returns a list of human-readable
    migration steps that ran (empty if nothing migrated).
    """
    import shutil

    actions: list[str] = []

    # config.toml
    legacy_config = Path(_LEGACY_DIRS.user_config_dir) / "config.toml"
    if legacy_config.exists() and not CONFIG_FILE.exists():
        shutil.copy2(legacy_config, CONFIG_FILE)
        actions.append(f"copied config.toml from {legacy_config} → {CONFIG_FILE}")

    # keyring entries (best-effort; ignore missing backend)
    try:
        import keyring

        known_keys = (
            "user-oauth",
            "user-oauth-refresh",
            "oauth-client-secret",
            "github-app-private-key",
            "receiver-subscriber-token",
        )
        for key in known_keys:
            try:
                legacy_val = keyring.get_password(_LEGACY_KEYRING_SERVICE, key)
            except Exception:
                continue
            if legacy_val is None:
                continue
            try:
                existing = keyring.get_password(KEYRING_SERVICE, key)
            except Exception:
                existing = None
            if existing is None:
                try:
                    keyring.set_password(KEYRING_SERVICE, key, legacy_val)
                    actions.append(f"migrated keyring entry: {key}")
                except Exception:
                    pass
    except ImportError:
        pass

    return actions

# GitHub API endpoints (overridable for GHES)
DEFAULT_API_BASE = "https://api.github.com"
DEFAULT_GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
DEFAULT_OAUTH_TOKEN = "https://github.com/login/oauth/access_token"
DEFAULT_DEVICE_CODE = "https://github.com/login/device/code"
DEFAULT_DEVICE_TOKEN = "https://github.com/login/oauth/access_token"


class Settings(BaseSettings):
    """User-editable application settings.

    Loaded from CONFIG_FILE (TOML) with env-var overrides prefixed GITGET_.
    """

    model_config = SettingsConfigDict(
        env_prefix="GITGET_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # GitHub endpoints (override for GitHub Enterprise Server)
    api_base: str = DEFAULT_API_BASE
    graphql_url: str = DEFAULT_GRAPHQL_URL
    oauth_authorize_url: str = DEFAULT_OAUTH_AUTHORIZE
    oauth_token_url: str = DEFAULT_OAUTH_TOKEN
    device_code_url: str = DEFAULT_DEVICE_CODE
    device_token_url: str = DEFAULT_DEVICE_TOKEN

    # OAuth / App credentials (client_id is non-secret; client_secret stored in keyring)
    oauth_client_id: str | None = None
    github_app_id: int | None = None
    github_app_slug: str | None = None

    # Polling intervals (seconds)
    poll_notifications_seconds: int = 60
    poll_issues_seconds: int = 300
    poll_discussions_seconds: int = 300
    poll_actions_seconds: int = 120

    # Webhook receiver mode: "polling" | "tunnel" | "remote"
    webhook_mode: str = Field(default="polling")
    webhook_remote_url: str | None = None
    cloudflared_path: str = "cloudflared"

    # UI
    theme: str = "dark"
    start_minimized_to_tray: bool = False

    @classmethod
    def load(cls) -> Settings:
        """Load from CONFIG_FILE if present, else return defaults."""
        if CONFIG_FILE.exists():
            import tomllib

            with CONFIG_FILE.open("rb") as f:
                data = tomllib.load(f)
            return cls(**data)
        return cls()

    def save(self) -> None:
        """Persist settings to CONFIG_FILE."""
        import tomli_w

        with CONFIG_FILE.open("wb") as f:
            tomli_w.dump(self.model_dump(exclude_none=True), f)
