"""Busy and error banners — dismissable inline status messages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class StatusBanner(QWidget):
    """A thin horizontal banner with an icon hint, message, and dismiss button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._label = QLabel("")
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._label, 1)

        self._dismiss = QPushButton("x")
        self._dismiss.setFixedWidth(24)
        self._dismiss.setFlat(True)
        self._dismiss.clicked.connect(self.hide)
        layout.addWidget(self._dismiss)

    def show_info(self, message: str) -> None:
        self.setStyleSheet("background-color: #2b3a4a; color: #cfe;")
        self._label.setText(message)
        self.setVisible(True)

    def show_error(self, message: str) -> None:
        self.setStyleSheet("background-color: #4a2b2b; color: #fbb;")
        self._label.setText(message)
        self.setVisible(True)

    def show_busy(self, message: str = "Loading…") -> None:
        self.setStyleSheet("background-color: #2b3a4a; color: #aab;")
        self._label.setText(message)
        self.setVisible(True)
