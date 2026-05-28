"""Markdown editor with side-by-side live preview.

Top toolbar toggles preview pane. Left = QPlainTextEdit source (monospace),
right = MarkdownView rendering. Source emits textChanged → preview updates
on a 150ms debounce timer to keep typing snappy.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gitget.ui.widgets.markdown import MarkdownView


class MarkdownEditor(QWidget):
    """Edit markdown with toggleable live preview.

    API:
      - toPlainText() / setPlainText() / clear() — source text
      - setPlaceholderText(text)
      - text_changed signal (mirrors QPlainTextEdit.textChanged)
    """

    text_changed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        preview_visible: bool = True,
        placeholder: str = "Write markdown…",
    ) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(2, 0, 2, 0)
        toolbar.addWidget(QLabel("Markdown"))
        toolbar.addStretch(1)
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("Preview")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(preview_visible)
        self._toggle_btn.toggled.connect(self._on_toggle_preview)
        toolbar.addWidget(self._toggle_btn)
        outer.addLayout(toolbar)

        # splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._source = QPlainTextEdit()
        self._source.setPlaceholderText(placeholder)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self._source.setFont(font)
        self._source.textChanged.connect(self._schedule_render)
        self._source.textChanged.connect(self.text_changed)
        self._splitter.addWidget(self._source)

        self._preview = MarkdownView()
        self._splitter.addWidget(self._preview)
        self._splitter.setSizes([400, 400])

        outer.addWidget(self._splitter, 1)

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(150)
        self._render_timer.timeout.connect(self._render_preview)

        self._preview.setVisible(preview_visible)

    # ---------- API ----------

    def toPlainText(self) -> str:  # noqa: N802 (Qt convention)
        return self._source.toPlainText()

    def setPlainText(self, text: str) -> None:  # noqa: N802
        self._source.setPlainText(text)
        self._render_preview()

    def clear(self) -> None:
        self._source.clear()

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802
        self._source.setPlaceholderText(text)

    # ---------- internal ----------

    def _on_toggle_preview(self, checked: bool) -> None:
        self._preview.setVisible(checked)
        if checked:
            self._render_preview()

    def _schedule_render(self) -> None:
        if self._preview.isVisible():
            self._render_timer.start()

    def _render_preview(self) -> None:
        self._preview.set_markdown(self._source.toPlainText())
