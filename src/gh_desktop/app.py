"""QApplication setup and run loop."""

from __future__ import annotations

import sys

import structlog
from PySide6.QtWidgets import QApplication

from gh_desktop.config import LOG_DIR, Settings
from gh_desktop.ui import MainWindow
from gh_desktop.ui.theme import APP_NAME, apply_theme

log = structlog.get_logger(__name__)


def _configure_logging() -> None:
    log_file = LOG_DIR / "gh-desktop.log"
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.WriteLoggerFactory(file=log_file.open("a", encoding="utf-8")),
    )


def run() -> int:
    _configure_logging()
    settings = Settings.load()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Obsidian Watch Group")
    app.setOrganizationDomain("obsidianwatch.org")
    apply_theme(app)

    window = MainWindow(settings)
    window.show()
    log.info("app_started")
    return app.exec()
