"""Investigation mode — case management via Discussions.

Layout:
  Repo selector + new-case button (top)
  Left:   Discussion (case) list
  Center: Thread body + comments + reply box
  Right:  Linked evidence (Issues with a configurable label, default 'evidence')
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gh_desktop.api.services import DiscussionsService, IssuesService
from gh_desktop.models import Discussion, Issue
from gh_desktop.ui.widgets import MarkdownView, StatusBanner, humanize, run_async
from gh_desktop.workspace import Workspace

DEFAULT_EVIDENCE_LABEL = "evidence"


class InvestigationMode(QWidget):
    def __init__(self, workspace: Workspace, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._scope: tuple[str, str] | None = None  # (owner, repo)
        self._discussions: list[Discussion] = []
        self._current: dict[str, Any] | None = None
        self._worker = None

        self._d_svc = DiscussionsService(workspace.graphql)
        self._i_svc = IssuesService(workspace.rest)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.addWidget(QLabel("Repo:"))
        self._repo_input = QLineEdit()
        self._repo_input.setPlaceholderText("owner/repo")
        self._repo_input.returnPressed.connect(self._on_scope_changed)
        toolbar.addWidget(self._repo_input, 1)
        self._load_btn = QPushButton("Load")
        self._load_btn.clicked.connect(self._on_scope_changed)
        toolbar.addWidget(self._load_btn)

        toolbar.addWidget(QLabel("Evidence label:"))
        self._evidence_label_edit = QLineEdit(DEFAULT_EVIDENCE_LABEL)
        self._evidence_label_edit.setMaximumWidth(140)
        toolbar.addWidget(self._evidence_label_edit)

        outer.addLayout(toolbar)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        # three-pane
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # left: case list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Cases (Discussions)"))
        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_select)
        ll.addWidget(self._list, 1)
        splitter.addWidget(left)

        # center: thread
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(8, 8, 8, 8)
        self._thread_header = QLabel("")
        self._thread_header.setStyleSheet("font-size: 13pt; font-weight: 600;")
        self._thread_header.setWordWrap(True)
        cl.addWidget(self._thread_header)
        self._thread_meta = QLabel("")
        self._thread_meta.setStyleSheet("color: #888;")
        cl.addWidget(self._thread_meta)
        self._thread_body = MarkdownView()
        cl.addWidget(self._thread_body, 1)

        # reply box
        cl.addWidget(QLabel("Reply"))
        self._reply_edit = QTextEdit()
        self._reply_edit.setMaximumHeight(120)
        self._reply_edit.setPlaceholderText("Markdown supported. Submit posts to the discussion.")
        cl.addWidget(self._reply_edit)
        reply_row = QHBoxLayout()
        reply_row.addStretch(1)
        self._open_btn = QPushButton("Open in browser")
        self._open_btn.clicked.connect(self._open_current)
        reply_row.addWidget(self._open_btn)
        self._submit_btn = QPushButton("Submit reply")
        self._submit_btn.clicked.connect(self._submit_reply)
        reply_row.addWidget(self._submit_btn)
        cl.addLayout(reply_row)
        splitter.addWidget(center)

        # right: linked evidence
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.addWidget(QLabel("Linked evidence (Issues)"))
        self._evidence_list = QListWidget()
        self._evidence_list.itemDoubleClicked.connect(self._open_evidence)
        rl.addWidget(self._evidence_list, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([280, 700, 320])
        outer.addWidget(splitter, 1)

    # ---------- scope changes ----------

    def set_scope(self, owner_repo: str) -> None:
        """Called by MainWindow when the repo picker selection changes."""
        if "/" not in owner_repo:
            return
        self._repo_input.setText(owner_repo)
        self._on_scope_changed()

    def _on_scope_changed(self) -> None:
        text = self._repo_input.text().strip()
        if "/" not in text:
            self._banner.show_error("Enter a scope as owner/repo.")
            return
        owner, repo = text.split("/", 1)
        self._scope = (owner, repo)
        self._load_discussions()
        self._load_evidence()

    def _load_discussions(self) -> None:
        if self._scope is None:
            return
        self._banner.show_busy("Loading discussions…")
        owner, repo = self._scope
        svc = self._d_svc

        async def fetch() -> list[Discussion]:
            return await svc.list_for_repo(owner, repo)

        self._worker = run_async(
            self, fetch, on_success=self._set_discussions, on_failure=self._on_error
        )

    def _load_evidence(self) -> None:
        if self._scope is None:
            return
        owner, repo = self._scope
        label = self._evidence_label_edit.text().strip() or DEFAULT_EVIDENCE_LABEL
        svc = self._i_svc

        async def fetch() -> list[Issue]:
            return await svc.list_for_repo(owner, repo, state="open", labels=[label])

        run_async(self, fetch, on_success=self._set_evidence, on_failure=self._on_error)

    # ---------- data callbacks ----------

    def _set_discussions(self, items: list[Discussion]) -> None:
        self._discussions = items
        self._list.clear()
        for d in items:
            cat = d.category_name or "—"
            text = (
                f"#{d.number}  {d.title}\n"
                f"    {cat} · {d.comments_count} comments · "
                f"updated {humanize(d.updated_at)}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, d)
            self._list.addItem(item)
        self._banner.setVisible(False)

    def _set_evidence(self, items: list[Issue]) -> None:
        self._evidence_list.clear()
        for issue in items:
            li = QListWidgetItem(f"#{issue.number}  {issue.title}")
            li.setData(Qt.ItemDataRole.UserRole, issue)
            li.setToolTip(issue.body or "")
            self._evidence_list.addItem(li)

    def _on_error(self, exc: Exception) -> None:
        self._banner.show_error(f"Couldn't load: {exc}")

    # ---------- selection ----------

    def _on_select(self) -> None:
        items = self._list.selectedItems()
        if not items or self._scope is None:
            return
        d: Discussion = items[0].data(Qt.ItemDataRole.UserRole)
        self._thread_header.setText(d.title)
        self._thread_meta.setText(
            f"#{d.number} · {d.category_name or '—'} · @{d.author_login or '?'} · "
            f"updated {humanize(d.updated_at)}"
        )
        self._thread_body.set_markdown(d.body or "_(empty body)_")
        self._fetch_full_discussion(d)

    def _fetch_full_discussion(self, d: Discussion) -> None:
        if self._scope is None:
            return
        owner, repo = self._scope
        svc = self._d_svc

        async def fetch() -> dict[str, Any]:
            return await svc.get(owner, repo, d.number)

        def on_done(payload: dict[str, Any]) -> None:
            self._current = payload
            body_md = payload.get("body") or ""
            comments = (payload.get("comments") or {}).get("nodes", [])
            chunks = [body_md or "_(empty body)_", "\n\n---\n"]
            for c in comments:
                author = (c.get("author") or {}).get("login") or "?"
                chunks.append(f"### @{author} — {humanize(c.get('createdAt'))}\n\n{c.get('body', '')}\n")
            self._thread_body.set_markdown("\n".join(chunks))

        self._worker = run_async(self, fetch, on_success=on_done, on_failure=self._on_error)

    # ---------- actions ----------

    def _open_current(self) -> None:
        if self._current is None:
            return
        url = self._current.get("url")
        if not url:
            return
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _open_evidence(self, item: QListWidgetItem) -> None:
        issue: Issue = item.data(Qt.ItemDataRole.UserRole)
        if issue.html_url:
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(issue.html_url))

    def _submit_reply(self) -> None:
        if self._current is None:
            self._banner.show_error("Select a case first.")
            return
        body = self._reply_edit.toPlainText().strip()
        if not body:
            return
        discussion_id = self._current["id"]
        svc = self._d_svc

        async def do() -> dict:
            return await svc.add_comment(discussion_id, body)

        def on_done(_: object) -> None:
            self._reply_edit.clear()
            self._banner.show_info("Reply posted.")
            # Refresh the thread to show the new comment
            items = self._list.selectedItems()
            if items:
                d: Discussion = items[0].data(Qt.ItemDataRole.UserRole)
                self._fetch_full_discussion(d)

        self._worker = run_async(self, do, on_success=on_done, on_failure=self._on_error)
