"""Unified-diff viewer with color-coded add/remove lines.

Parses a unified-diff patch (the kind GitHub returns in /pulls/N/files) and
renders it into a QTextBrowser with green/red line backgrounds.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextBrowser, QWidget


class DiffView(QTextBrowser):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setOpenLinks(False)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
        self.setStyleSheet("QTextBrowser { background-color: #1b1b1b; color: #ddd; }")

    def set_patch(self, patch: str | None) -> None:
        self.clear()
        if not patch:
            self.setPlainText("(no patch — file is binary, renamed, or unchanged)")
            return

        cursor = self.textCursor()
        for line in patch.splitlines():
            fmt = QTextCharFormat()
            if line.startswith("@@"):
                fmt.setForeground(_color("#6cd"))
                fmt.setBackground(_color("#22323a"))
            elif line.startswith("+++") or line.startswith("---"):
                fmt.setForeground(_color("#aaa"))
                fmt.setBackground(_color("#222"))
            elif line.startswith("+"):
                fmt.setForeground(_color("#cdf5cd"))
                fmt.setBackground(_color("#1f3a25"))
            elif line.startswith("-"):
                fmt.setForeground(_color("#ffd0d0"))
                fmt.setBackground(_color("#3a1f1f"))
            elif line.startswith("diff "):
                fmt.setForeground(_color("#ccc"))
                fmt.setBackground(_color("#2a2a2a"))
            else:
                fmt.setForeground(_color("#bbb"))
            cursor.insertText(line + "\n", fmt)
        self.moveCursor(QTextCursor.MoveOperation.Start)


def _color(hex_str: str):
    from PySide6.QtGui import QColor
    return QColor(hex_str)
