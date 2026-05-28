"""CLI entry point for the webhook receiver: `gitget-receiver`."""

from __future__ import annotations

import argparse
import secrets
import sys

import structlog
import uvicorn

from gitget.receiver.server import ReceiverSettings, build_app

log = structlog.get_logger(__name__)


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
    )


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="gitget-receiver")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--db", default=None, help="SQLite event-log path")
    parser.add_argument(
        "--gen-secrets",
        action="store_true",
        help="Print fresh webhook + subscriber secrets and exit (for first-time setup)",
    )
    args = parser.parse_args()

    if args.gen_secrets:
        print("# Add these to your systemd unit or shell env:")
        print(f"GITGET_RECEIVER_WEBHOOK_SECRET={secrets.token_hex(32)}")
        print(f"GITGET_RECEIVER_SUBSCRIBER_TOKEN={secrets.token_urlsafe(32)}")
        return

    cfg = ReceiverSettings()
    if args.host:
        cfg.host = args.host
    if args.port:
        cfg.port = args.port
    if args.db:
        from pathlib import Path
        cfg.db_path = Path(args.db)

    if not cfg.webhook_secret or not cfg.subscriber_token:
        sys.stderr.write(
            "WARNING: webhook_secret and/or subscriber_token are unset. "
            "Run with --gen-secrets and put them in your env before starting.\n"
        )

    app = build_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_config=None)


if __name__ == "__main__":
    main()
