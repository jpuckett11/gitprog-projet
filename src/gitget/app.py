"""QApplication setup and run loop."""

from __future__ import annotations

import sys

import structlog
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gitget.assets import icon_path
from gitget.config import LOG_DIR, Settings
from gitget.ui import MainWindow
from gitget.ui.theme import APP_NAME, apply_theme

log = structlog.get_logger(__name__)


def _configure_logging() -> None:
    log_file = LOG_DIR / "gitget.log"
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
    from gitget.config import migrate_legacy_state

    migrated = migrate_legacy_state()
    if migrated:
        log.info("legacy_state_migrated", steps=migrated)
    settings = Settings.load()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Obsidian Watch Group")
    app.setOrganizationDomain("obsidianwatch.org")
    app.setWindowIcon(QIcon(str(icon_path())))
    apply_theme(app)

    window = MainWindow(settings)
    window.show()
    log.info("app_started")
    return app.exec()
