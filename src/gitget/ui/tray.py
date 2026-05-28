"""System tray icon with unread badge and quick actions.

Sits in the user's notification area. Left-click toggles main window visibility;
right-click opens menu with: Show/Hide, Refresh notifications, Settings, Quit.

The icon is overlaid with the unread-notification count when > 0.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QPainter,
)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from gitget.assets import icon_path


def _make_badged_icon(base_icon: QIcon, count: int) -> QIcon:
    """Return icon with a small red badge with `count` overlaid (no badge if 0)."""
    size = 64
    pix = base_icon.pixmap(size, size)
    if pix.isNull():
        return base_icon
    if count <= 0:
        return QIcon(pix)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # red circle background
    diameter = 28
    x = size - diameter - 2
    y = 2
    painter.setBrush(QColor("#e76f7a"))
    painter.setPen(QColor("#16101e"))
    painter.drawEllipse(x, y, diameter, diameter)

    # count text
    label = "99+" if count > 99 else str(count)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(16 if len(label) < 3 else 12)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(x, y, diameter, diameter, Qt.AlignmentFlag.AlignCenter, label)
    painter.end()
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    show_requested = Signal()
    refresh_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent_window: QWidget) -> None:
        self._base_icon = QIcon(str(icon_path()))
        super().__init__(self._base_icon, parent_window)
        self._unread = 0
        self._window = parent_window
        self.setToolTip("GitGet — 0 unread")

        menu = QMenu(parent_window)
        self._show_action = QAction("Show GitGet", parent_window)
        self._show_action.triggered.connect(self.show_requested.emit)
        menu.addAction(self._show_action)

        act_refresh = QAction("Refresh notifications", parent_window)
        act_refresh.triggered.connect(self.refresh_requested.emit)
        menu.addAction(act_refresh)

        act_settings = QAction("Settings…", parent_window)
        act_settings.triggered.connect(self.settings_requested.emit)
        menu.addAction(act_settings)

        menu.addSeparator()
        act_quit = QAction("Quit", parent_window)
        act_quit.triggered.connect(QApplication.quit)
        menu.addAction(act_quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_requested.emit()

    def set_unread(self, count: int) -> None:
        count = max(0, int(count))
        if count == self._unread:
            return
        self._unread = count
        self.setIcon(_make_badged_icon(self._base_icon, count))
        self.setToolTip(f"GitGet — {count} unread")
