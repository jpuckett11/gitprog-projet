# Changelog

## 0.1.0 — 2026-05-28

First release. A complete Linux desktop GitHub client built around five
workflow modes:

### Workflow modes
- **Triage** — notification inbox with per-reason / per-type filters, mark-read,
  unsubscribe, live updates via webhooks.
- **Investigation** — GitHub Discussions as case threads with linked Issues as
  evidence items; markdown editor with live preview.
- **Pull Requests** — list, view files + colored unified diff, submit reviews
  (Approve / Request changes / Comment), add inline comments on diff lines,
  squash/merge/rebase from the GUI.
- **Admin** — org/repo dashboard: members, secrets (libsodium sealed-box
  encryption), Actions runs, webhooks.
- **Contents** — lazy-loaded file tree with markdown / code / image / hex
  previews; empty-repo aware.
- **Search** — cross-repo search across issues, PRs, repositories, code, and
  users with saved-search persistence.

### Infrastructure
- **Webhook receiver** (`gitget-receiver`) — FastAPI service with HMAC-verified
  webhook ingestion, SQLite event log, async fan-out via WebSocket. Bundled
  systemd unit + Caddyfile + env template for self-hosted deployments.
- **Cloudflare Tunnel** — built-in supervisor for `cloudflared` (named or
  quick-tunnel modes); auto-restart, URL emission via Qt signal.
- **WebSocket bridge** — desktop client replays events on reconnect.

### UI
- PySide6, dark purple theme, custom QSS, app icon (SVG + 8 PNG sizes).
- Embedded PTY terminal (vim/htop/ssh-capable) via `pty.fork()` + pyte.
- Dockable terminal panel (Ctrl+`), View menu, About dialog.
- System tray icon with unread-count badge and quick actions.
- Markdown editor with toggleable live preview.

### Auth & state
- OAuth (web flow + PKCE; device flow); GitHub App JWT + installation tokens.
- libsecret keyring storage with one-shot migration from prior `gh-desktop`
  install.
- Per-loop httpx clients so the polling engine and worker threads can share
  a `RestClient` without binding to a single asyncio loop.

### Packaging
- `.deb`, AppImage, and Flatpak manifests with proper hicolor icon install.
- `packaging/render_pngs.py` rasterizes the SVG to 8 sizes via PySide6's own
  QSvgRenderer (no extra system deps).

### Tests
- 49 passing tests, ruff-clean: API services, OAuth PKCE, JWT roundtrip,
  webhook signature verification, event-store dedup + purge, all UI modes
  construct.
