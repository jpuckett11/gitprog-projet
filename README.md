# gh-desktop

Linux GitHub desktop app with three primary modes:

- **Triage** — inbox-style notification triage across all subscribed repos
- **Investigation** — case management using Discussions as case threads, Issues as evidence items
- **Admin** — org/repo admin dashboard (settings, members, secrets, Actions, webhooks)

Built on PySide6. Supports both OAuth (user) and GitHub App (installation) auth. Webhook delivery via hybrid model: polling fallback + Cloudflare Tunnel + self-hosted receiver.

## Status

Phase 1 (foundation) — in progress.

## Quickstart

```bash
uv sync
uv run gh-desktop
```

## Layout

```
src/gh_desktop/
├── app.py              # QApplication bootstrap
├── __main__.py         # CLI entry
├── config.py           # Settings, paths
├── models.py           # Pydantic models for GitHub entities
├── auth/               # OAuth + GitHub App JWT + token storage
├── api/                # REST + GraphQL clients, rate limit, cache
├── polling/            # Background polling engine
└── ui/                 # PySide6 views
    ├── main_window.py
    ├── login.py
    ├── settings.py
    ├── repo_picker.py
    └── modes/
        ├── triage.py
        ├── investigation.py
        └── admin.py
```
