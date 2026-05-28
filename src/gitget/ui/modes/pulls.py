"""Pull Requests mode — list, view files + diffs, submit reviews."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gitget.api.services import PullsService
from gitget.ui.widgets import DiffView, MarkdownView, StatusBanner, humanize, run_async
from gitget.workspace import Workspace


class PullsMode(QWidget):
    def __init__(self, workspace: Workspace, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._svc = PullsService(workspace.rest)
        self._scope: tuple[str, str] | None = None
        self._workers: list[Any] = []
        self._prs: list[dict[str, Any]] = []
        self._current_pr: dict[str, Any] | None = None
        self._current_files: list[dict[str, Any]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.addWidget(QLabel("Repo:"))
        self._repo_input = QLineEdit()
        self._repo_input.setPlaceholderText("owner/repo")
        self._repo_input.returnPressed.connect(self._on_scope_changed)
        toolbar.addWidget(self._repo_input, 1)
        toolbar.addWidget(QLabel("State:"))
        self._state_combo = QComboBox()
        self._state_combo.addItems(["open", "closed", "all"])
        self._state_combo.currentTextChanged.connect(self._on_state_changed)
        toolbar.addWidget(self._state_combo)
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._load_prs)
        toolbar.addWidget(self._refresh_btn)
        outer.addLayout(toolbar)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._pr_list = QListWidget()
        self._pr_list.itemSelectionChanged.connect(self._on_pr_selected)
        splitter.addWidget(self._pr_list)

        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(8, 8, 8, 8)
        self._pr_header = QLabel("Select a PR.")
        self._pr_header.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self._pr_header.setWordWrap(True)
        cl.addWidget(self._pr_header)
        self._pr_meta = QLabel("")
        self._pr_meta.setStyleSheet("color: #888;")
        cl.addWidget(self._pr_meta)
        self._pr_body = MarkdownView()
        self._pr_body.setMaximumHeight(160)
        cl.addWidget(self._pr_body)

        center_split = QSplitter(Qt.Orientation.Vertical)
        self._files_list = QListWidget()
        self._files_list.itemSelectionChanged.connect(self._on_file_selected)
        center_split.addWidget(self._files_list)

        self._diff = DiffView()
        center_split.addWidget(self._diff)
        center_split.setStretchFactor(0, 1)
        center_split.setStretchFactor(1, 3)
        cl.addWidget(center_split, 1)
        splitter.addWidget(center)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.addWidget(QLabel("Review"))
        self._review_body = QTextEdit()
        self._review_body.setPlaceholderText("Optional review summary (markdown).")
        rl.addWidget(self._review_body, 1)

        btn_row = QHBoxLayout()
        self._approve_btn = QPushButton("Approve")
        self._approve_btn.clicked.connect(lambda: self._submit_review("APPROVE"))
        btn_row.addWidget(self._approve_btn)
        self._reqchg_btn = QPushButton("Request changes")
        self._reqchg_btn.clicked.connect(lambda: self._submit_review("REQUEST_CHANGES"))
        btn_row.addWidget(self._reqchg_btn)
        self._comment_btn = QPushButton("Comment")
        self._comment_btn.clicked.connect(lambda: self._submit_review("COMMENT"))
        btn_row.addWidget(self._comment_btn)
        rl.addLayout(btn_row)

        merge_row = QHBoxLayout()
        merge_row.addWidget(QLabel("Merge method:"))
        self._merge_method = QComboBox()
        self._merge_method.addItems(["squash", "merge", "rebase"])
        merge_row.addWidget(self._merge_method)
        self._merge_btn = QPushButton("Merge")
        self._merge_btn.clicked.connect(self._do_merge)
        merge_row.addWidget(self._merge_btn)
        rl.addLayout(merge_row)

        self._open_btn = QPushButton("Open in browser")
        self._open_btn.clicked.connect(self._open_current)
        rl.addWidget(self._open_btn)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 6)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([280, 800, 320])
        outer.addWidget(splitter, 1)

    def set_scope(self, owner_repo: str) -> None:
        if "/" not in owner_repo:
            return
        self._repo_input.setText(owner_repo)
        self._on_scope_changed()

    def _on_scope_changed(self) -> None:
        text = self._repo_input.text().strip()
        if "/" not in text:
            self._banner.show_error("Enter scope as owner/repo.")
            return
        owner, repo = text.split("/", 1)
        self._scope = (owner, repo)
        self._load_prs()

    def _on_state_changed(self, _state: str) -> None:
        if self._scope is not None:
            self._load_prs()

    def _load_prs(self) -> None:
        if self._scope is None:
            return
        owner, repo = self._scope
        state = self._state_combo.currentText()
        svc = self._svc
        self._banner.show_busy(f"Loading {state} PRs…")

        async def fetch():
            return await svc.list_for_repo(owner, repo, state=state, max_pages=3)

        def on_done(prs):
            self._prs = prs
            self._pr_list.clear()
            for p in prs:
                head = (p.get("head") or {}).get("ref", "?")
                base = (p.get("base") or {}).get("ref", "?")
                label = (
                    f"#{p['number']}  {p['title']}\n"
                    f"    {p.get('user',{}).get('login','?')} · {head} → {base} · "
                    f"updated {humanize(p.get('updated_at'))}"
                )
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, p)
                self._pr_list.addItem(item)
            self._banner.setVisible(False)
            if not prs:
                self._banner.show_info(f"No {state} pull requests.")

        self._workers.append(
            run_async(self, fetch, on_success=on_done, on_failure=self._on_error)
        )

    def _on_pr_selected(self) -> None:
        items = self._pr_list.selectedItems()
        if not items or self._scope is None:
            return
        pr: dict[str, Any] = items[0].data(Qt.ItemDataRole.UserRole)
        self._current_pr = pr
        head = (pr.get("head") or {}).get("ref", "?")
        base = (pr.get("base") or {}).get("ref", "?")
        self._pr_header.setText(f"#{pr['number']}  {pr['title']}")
        author = (pr.get("user") or {}).get("login", "?")
        self._pr_meta.setText(
            f"@{author} · {head} → {base} · state: {pr.get('state','?')} · "
            f"draft: {pr.get('draft', False)} · updated {humanize(pr.get('updated_at'))}"
        )
        self._pr_body.set_markdown(pr.get("body") or "_(empty description)_")

        owner, repo = self._scope
        number = pr["number"]
        svc = self._svc

        async def fetch_files():
            return await svc.list_files(owner, repo, number)

        def on_files(files: list[dict[str, Any]]):
            self._current_files = files
            self._files_list.clear()
            for f in files:
                status = f.get("status", "")
                adds = f.get("additions", 0)
                dels = f.get("deletions", 0)
                label = f"[{status}]  {f.get('filename','?')}    +{adds} -{dels}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, f)
                self._files_list.addItem(item)
            self._diff.set_patch(None)

        self._workers.append(
            run_async(self, fetch_files, on_success=on_files, on_failure=self._on_error)
        )

    def _on_file_selected(self) -> None:
        items = self._files_list.selectedItems()
        if not items:
            return
        f: dict[str, Any] = items[0].data(Qt.ItemDataRole.UserRole)
        self._diff.set_patch(f.get("patch"))

    def _submit_review(self, event: str) -> None:
        if self._current_pr is None or self._scope is None:
            self._banner.show_error("Select a PR first.")
            return
        owner, repo = self._scope
        number = self._current_pr["number"]
        body = self._review_body.toPlainText().strip()
        if event == "REQUEST_CHANGES" and not body:
            self._banner.show_error(
                "GitHub requires a body when requesting changes."
            )
            return
        svc = self._svc

        async def do():
            return await svc.create_review(
                owner, repo, number, event=event, body=body  # type: ignore[arg-type]
            )

        def on_done(_):
            self._review_body.clear()
            self._banner.show_info(f"Review submitted: {event}")

        self._workers.append(
            run_async(self, do, on_success=on_done, on_failure=self._on_error)
        )

    def _do_merge(self) -> None:
        if self._current_pr is None or self._scope is None:
            return
        owner, repo = self._scope
        number = self._current_pr["number"]
        method = self._merge_method.currentText()
        confirm = QMessageBox.question(
            self, "Merge PR",
            f"Merge #{number} with method '{method}'?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        svc = self._svc

        async def do():
            return await svc.merge(owner, repo, number, method=method)  # type: ignore[arg-type]

        def on_done(_):
            self._banner.show_info(f"#{number} merged ({method}).")
            self._load_prs()

        self._workers.append(
            run_async(self, do, on_success=on_done, on_failure=self._on_error)
        )

    def _open_current(self) -> None:
        if self._current_pr is None:
            return
        url = self._current_pr.get("html_url")
        if not url:
            return
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _on_error(self, exc: Exception) -> None:
        self._banner.show_error(f"{exc}")
