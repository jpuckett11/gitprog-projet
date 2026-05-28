# Deploying gitget-receiver on a rack server

Self-hosted webhook receiver for gitget. Caddy terminates TLS and proxies
to the FastAPI service running on 127.0.0.1:8765.

## One-time setup

1. Install dependencies on the server:
   ```bash
   sudo apt install python3-venv caddy
   sudo useradd -r -s /usr/sbin/nologin ghd-recv
   sudo mkdir -p /opt/gitget-receiver /etc/gitget-receiver
   sudo chown ghd-recv:ghd-recv /opt/gitget-receiver
   ```

2. Deploy the code (e.g. via `git clone` or `rsync` from your workstation):
   ```bash
   sudo -u ghd-recv git clone <repo> /opt/gitget-receiver
   cd /opt/gitget-receiver
   sudo -u ghd-recv /home/obsidian/.local/bin/uv sync
   ```

3. Generate secrets:
   ```bash
   sudo -u ghd-recv /opt/gitget-receiver/.venv/bin/gitget-receiver --gen-secrets
   ```
   Copy the output into `/etc/gitget-receiver/env` (see env.example).
   `chmod 600` that file.

4. Install the systemd unit + Caddy config:
   ```bash
   sudo cp deploy/gitget-receiver.service /etc/systemd/system/
   sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile  # edit hostname first
   sudo systemctl daemon-reload
   sudo systemctl enable --now gitget-receiver caddy
   ```

5. Add the webhook in GitHub:
   - Repo → Settings → Webhooks → Add webhook
   - Payload URL: `https://your-host/webhook`
   - Content type: `application/json`
   - Secret: paste `GITGET_RECEIVER_WEBHOOK_SECRET`
   - Events: pick what you care about (issues, pull_request, discussion, push, etc.)

6. Point gitget at the receiver:
   - Settings → webhook_mode = `remote`
   - webhook_remote_url = `https://your-host`
   - Paste `GITGET_RECEIVER_SUBSCRIBER_TOKEN` when prompted (stored in libsecret).

## Troubleshooting

- `journalctl -u gitget-receiver -f` — live logs
- `curl https://your-host/healthz` — should return `{"ok": true, "subscribers": N}`
- Bad signature → check that `GITGET_RECEIVER_WEBHOOK_SECRET` matches the secret you set in GitHub
- 401 on WebSocket → check `GITGET_RECEIVER_SUBSCRIBER_TOKEN` matches the token saved in the desktop client
