"""GitHub-style label chip."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gitget.models import Label


def _contrast_text_color(hex_color: str) -> str:
    """Pick black or white text based on the label's bg color luminance."""
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except (ValueError, IndexError):
        return "#fff"
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000" if luminance > 0.6 else "#fff"


class LabelChip(QLabel):
    def __init__(self, label: Label, parent: QWidget | None = None) -> None:
        super().__init__(label.name, parent)
        bg = label.color or "888888"
        fg = _contrast_text_color(bg)
        self.setStyleSheet(
            f"background-color: #{bg}; color: {fg}; "
            "padding: 2px 8px; border-radius: 10px; font-size: 9pt;"
        )
        if label.description:
            self.setToolTip(label.description)


class LabelChipRow(QWidget):
    def __init__(self, labels: list[Label], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for label in labels:
            layout.addWidget(LabelChip(label))
        layout.addStretch(1)
