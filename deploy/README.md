# Deploying gh-desktop-receiver on a rack server

Self-hosted webhook receiver for gh-desktop. Caddy terminates TLS and proxies
to the FastAPI service running on 127.0.0.1:8765.

## One-time setup

1. Install dependencies on the server:
   ```bash
   sudo apt install python3-venv caddy
   sudo useradd -r -s /usr/sbin/nologin ghd-recv
   sudo mkdir -p /opt/gh-desktop-receiver /etc/gh-desktop-receiver
   sudo chown ghd-recv:ghd-recv /opt/gh-desktop-receiver
   ```

2. Deploy the code (e.g. via `git clone` or `rsync` from your workstation):
   ```bash
   sudo -u ghd-recv git clone <repo> /opt/gh-desktop-receiver
   cd /opt/gh-desktop-receiver
   sudo -u ghd-recv /home/obsidian/.local/bin/uv sync
   ```

3. Generate secrets:
   ```bash
   sudo -u ghd-recv /opt/gh-desktop-receiver/.venv/bin/gh-desktop-receiver --gen-secrets
   ```
   Copy the output into `/etc/gh-desktop-receiver/env` (see env.example).
   `chmod 600` that file.

4. Install the systemd unit + Caddy config:
   ```bash
   sudo cp deploy/gh-desktop-receiver.service /etc/systemd/system/
   sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile  # edit hostname first
   sudo systemctl daemon-reload
   sudo systemctl enable --now gh-desktop-receiver caddy
   ```

5. Add the webhook in GitHub:
   - Repo → Settings → Webhooks → Add webhook
   - Payload URL: `https://your-host/webhook`
   - Content type: `application/json`
   - Secret: paste `GH_DESKTOP_RECEIVER_WEBHOOK_SECRET`
   - Events: pick what you care about (issues, pull_request, discussion, push, etc.)

6. Point gh-desktop at the receiver:
   - Settings → webhook_mode = `remote`
   - webhook_remote_url = `https://your-host`
   - Paste `GH_DESKTOP_RECEIVER_SUBSCRIBER_TOKEN` when prompted (stored in libsecret).

## Troubleshooting

- `journalctl -u gh-desktop-receiver -f` — live logs
- `curl https://your-host/healthz` — should return `{"ok": true, "subscribers": N}`
- Bad signature → check that `GH_DESKTOP_RECEIVER_WEBHOOK_SECRET` matches the secret you set in GitHub
- 401 on WebSocket → check `GH_DESKTOP_RECEIVER_SUBSCRIBER_TOKEN` matches the token saved in the desktop client
