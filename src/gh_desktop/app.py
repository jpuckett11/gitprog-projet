"""QApplication setup and run loop."""

from __future__ import annotations

import sys

import structlog
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from gh_desktop.config import LOG_DIR, Settings
from gh_desktop.ui import MainWindow

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


def _apply_theme(app: QApplication, theme: str) -> None:
    if theme != "dark":
        return
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(30, 30, 32))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Base, QColor(22, 22, 24))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(34, 34, 36))
    pal.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Button, QColor(40, 40, 44))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))
    pal.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(pal)


def run() -> int:
    _configure_logging()
    settings = Settings.load()

    app = QApplication(sys.argv)
    app.setApplicationName("gh-desktop")
    app.setOrganizationName("Obsidian Watch Group")
    app.setOrganizationDomain("obsidianwatch.org")
    _apply_theme(app, settings.theme)

    window = MainWindow(settings)
    window.show()
    log.info("app_started")
    return app.exec()
