"""Unified-diff viewer with color-coded add/remove lines.

Tracks a line map alongside the rendered text so callers can ask
`current_line_info()` to know which file-line the cursor is on — used by the
PR review UI to attach inline comments to specific lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextBrowser, QWidget

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(slots=True)
class LineInfo:
    """Per-text-block info derived from a unified diff."""

    file_line_new: int  # 0 if not applicable
    file_line_old: int  # 0 if not applicable
    side: str  # "RIGHT" (added/context), "LEFT" (removed), or "" (header/blank)


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
        self._line_map: list[LineInfo] = []

    def set_patch(self, patch: str | None) -> None:
        self.clear()
        self._line_map = []
        if not patch:
            self.setPlainText("(no patch — file is binary, renamed, or unchanged)")
            return

        cursor = self.textCursor()
        new_line = 0
        old_line = 0
        for line in patch.splitlines():
            fmt = QTextCharFormat()
            info = LineInfo(0, 0, "")
            if line.startswith("@@"):
                fmt.setForeground(QColor("#6cd"))
                fmt.setBackground(QColor("#22323a"))
                m = _HUNK_RE.match(line)
                if m:
                    old_line = int(m.group(1)) - 1
                    new_line = int(m.group(2)) - 1
            elif line.startswith("+++") or line.startswith("---"):
                fmt.setForeground(QColor("#aaa"))
                fmt.setBackground(QColor("#222"))
            elif line.startswith("+"):
                fmt.setForeground(QColor("#cdf5cd"))
                fmt.setBackground(QColor("#1f3a25"))
                new_line += 1
                info = LineInfo(new_line, 0, "RIGHT")
            elif line.startswith("-"):
                fmt.setForeground(QColor("#ffd0d0"))
                fmt.setBackground(QColor("#3a1f1f"))
                old_line += 1
                info = LineInfo(0, old_line, "LEFT")
            elif line.startswith(" "):
                fmt.setForeground(QColor("#bbb"))
                new_line += 1
                old_line += 1
                info = LineInfo(new_line, old_line, "RIGHT")
            elif line.startswith("diff "):
                fmt.setForeground(QColor("#ccc"))
                fmt.setBackground(QColor("#2a2a2a"))
            else:
                fmt.setForeground(QColor("#bbb"))
            cursor.insertText(line + "\n", fmt)
            self._line_map.append(info)

        self.moveCursor(QTextCursor.MoveOperation.Start)

    def current_line_info(self) -> LineInfo:
        cursor = self.textCursor()
        block = cursor.blockNumber()
        if 0 <= block < len(self._line_map):
            return self._line_map[block]
        return LineInfo(0, 0, "")
