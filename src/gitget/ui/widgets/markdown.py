"""Markdown viewer using Qt's built-in CommonMark renderer."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import QTextBrowser, QWidget


class MarkdownView(QTextBrowser):
    """Read-only markdown view; opens links in the user's browser."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._open_external)
        self.document().setDocumentMargin(12)

    def set_markdown(self, text: str | None) -> None:
        if not text:
            self.clear()
            return
        self.document().setMarkdown(text, QTextDocument.MarkdownDialectGitHub)

    @staticmethod
    def _open_external(url: QUrl) -> None:
        if url.scheme() in {"http", "https", "mailto"}:
            QDesktopServices.openUrl(url)
