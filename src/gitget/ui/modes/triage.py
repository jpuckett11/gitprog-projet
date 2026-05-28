"""Triage mode — notification inbox.

Three-pane layout:
  Filters (left) | Notification list (center) | Detail pane (right)

Actions:
  - Mark single thread read
  - Mark all read
  - Unsubscribe from thread
  - Open in browser

The notification list is fed by PollingEngine (resource: "notifications").
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gitget.api.services import NotificationsService
from gitget.models import Notification
from gitget.ui.widgets import MarkdownView, StatusBanner, humanize, run_async
from gitget.workspace import Workspace


class _Filters(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.show_read = QCheckBox("Show read")
        self.show_participating_only = QCheckBox("Participating only")
        self.show_read.stateChanged.connect(self.changed)
        self.show_participating_only.stateChanged.connect(self.changed)

        reason_box = QGroupBox("Reason")
        rb = QVBoxLayout(reason_box)
        self.reason_checks: dict[str, QCheckBox] = {}
        for reason in ["mention", "review_requested", "assign", "team_mention",
                       "author", "comment", "subscribed", "state_change"]:
            cb = QCheckBox(reason)
            cb.setChecked(True)
            cb.stateChanged.connect(self.changed)
            self.reason_checks[reason] = cb
            rb.addWidget(cb)

        type_box = QGroupBox("Type")
        tb = QVBoxLayout(type_box)
        self.type_checks: dict[str, QCheckBox] = {}
        for kind in ["Issue", "PullRequest", "Discussion", "Commit", "Release"]:
            cb = QCheckBox(kind)
            cb.setChecked(True)
            cb.stateChanged.connect(self.changed)
            self.type_checks[kind] = cb
            tb.addWidget(cb)

        layout.addWidget(self.show_read)
        layout.addWidget(self.show_participating_only)
        layout.addWidget(reason_box)
        layout.addWidget(type_box)
        layout.addStretch(1)

    def accepts(self, n: Notification) -> bool:
        if n.reason in self.reason_checks and not self.reason_checks[n.reason].isChecked():
            return False
        if n.subject.type in self.type_checks and not self.type_checks[n.subject.type].isChecked():
            return False
        return not (not self.show_read.isChecked() and not n.unread)


class TriageMode(QWidget):
    def __init__(self, workspace: Workspace, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._notifications: list[Notification] = []
        self._worker = None
        self._svc = NotificationsService(workspace.rest)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        self._title = QLabel("Triage — notifications")
        self._title.setStyleSheet("font-weight: 600;")
        toolbar.addWidget(self._title)
        toolbar.addStretch(1)
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_btn)
        self._mark_all_btn = QPushButton("Mark all read")
        self._mark_all_btn.clicked.connect(self._mark_all_read)
        toolbar.addWidget(self._mark_all_btn)
        outer.addLayout(toolbar)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        # three-pane splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._filters = _Filters()
        self._filters.changed.connect(self._refresh_list)
        splitter.addWidget(self._filters)

        # center: list
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemSelectionChanged.connect(self._on_select)
        cl.addWidget(self._list)
        splitter.addWidget(center)

        # right: detail
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(8, 8, 8, 8)
        self._detail_header = QLabel("")
        self._detail_header.setStyleSheet("font-size: 12pt; font-weight: 600;")
        self._detail_header.setWordWrap(True)
        dl.addWidget(self._detail_header)
        self._detail_meta = QLabel("")
        self._detail_meta.setStyleSheet("color: #888;")
        dl.addWidget(self._detail_meta)
        self._detail_body = MarkdownView()
        dl.addWidget(self._detail_body, 1)

        action_row = QHBoxLayout()
        self._open_btn = QPushButton("Open in browser")
        self._open_btn.clicked.connect(self._open_current)
        action_row.addWidget(self._open_btn)
        self._mark_read_btn = QPushButton("Mark read")
        self._mark_read_btn.clicked.connect(self._mark_current_read)
        action_row.addWidget(self._mark_read_btn)
        self._unsub_btn = QPushButton("Unsubscribe")
        self._unsub_btn.clicked.connect(self._unsubscribe_current)
        action_row.addWidget(self._unsub_btn)
        action_row.addStretch(1)
        dl.addLayout(action_row)

        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 4)
        splitter.setSizes([200, 500, 700])
        outer.addWidget(splitter, 1)

        # subscribe to polling engine
        workspace.poller.changed.connect(self._on_poll_change)
        workspace.poller.error.connect(self._on_poll_error)

        # if a webhook bridge is wired up, refresh notifications on relevant events
        if workspace.bridge is not None:
            workspace.bridge.event.connect(self._on_webhook_event)

    # ---------- data ----------

    def refresh(self) -> None:
        self._banner.show_busy("Loading notifications…")
        svc = self._svc

        async def fetch() -> list[Notification]:
            return await svc.list(all=True, max_pages=2)

        self._worker = run_async(self, fetch, on_success=self._set_data, on_failure=self._on_error)

    def _on_poll_change(self, resource: str, value: object) -> None:
        if resource != "notifications":
            return
        if isinstance(value, list):
            self._set_data(value)

    def _on_poll_error(self, resource: str, exc: object) -> None:
        if resource == "notifications":
            self._banner.show_error(f"Polling failed: {exc}")

    def _on_webhook_event(self, event: object) -> None:
        # Any of these events may cause a new notification to be created.
        if not isinstance(event, dict):
            return
        relevant = {
            "issues", "issue_comment", "pull_request", "pull_request_review",
            "pull_request_review_comment", "discussion", "discussion_comment",
            "release", "commit_comment", "push",
        }
        if event.get("event_type") in relevant:
            self.refresh()

    def _set_data(self, items: list[Notification]) -> None:
        self._notifications = items
        self._banner.setVisible(False)
        self._refresh_list()

    def _on_error(self, exc: Exception) -> None:
        self._banner.show_error(f"Couldn't load: {exc}")

    # ---------- list ----------

    def _refresh_list(self) -> None:
        self._list.clear()
        for n in self._notifications:
            if not self._filters.accepts(n):
                continue
            unread_mark = "●" if n.unread else "○"
            text = (
                f"{unread_mark}  {n.subject.title}\n"
                f"    {n.repository.full_name} · {n.subject.type} · "
                f"{n.reason} · {humanize(n.updated_at)}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, n)
            self._list.addItem(item)

    def _current(self) -> Notification | None:
        items = self._list.selectedItems()
        if not items:
            return None
        data = items[0].data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, Notification) else None

    def _on_select(self) -> None:
        n = self._current()
        if n is None:
            self._detail_header.setText("")
            self._detail_meta.setText("")
            self._detail_body.set_markdown("")
            return
        self._detail_header.setText(n.subject.title)
        self._detail_meta.setText(
            f"{n.repository.full_name} · {n.subject.type} · reason: {n.reason} · "
            f"updated {humanize(n.updated_at)}"
        )
        # Defer body fetch to keep selection snappy; user clicks "Open in browser" for full view
        self._detail_body.set_markdown(
            f"**Subject URL:** {n.subject.url or '—'}\n\n"
            f"Click _Open in browser_ for the full thread."
        )

    # ---------- actions ----------

    def _open_current(self) -> None:
        n = self._current()
        if n is None:
            return
        from PySide6.QtCore import QUrl

        # Convert API URL to web URL
        api_url = n.subject.url or ""
        web_url = (
            api_url
            .replace("https://api.github.com/repos/", "https://github.com/")
            .replace("/pulls/", "/pull/")
        )
        if not web_url.startswith("http"):
            return
        QDesktopServices.openUrl(QUrl(web_url))

    def _mark_current_read(self) -> None:
        n = self._current()
        if n is None or not n.unread:
            return

        svc = self._svc
        nid = n.id

        async def do() -> None:
            await svc.mark_thread_read(nid)

        self._worker = run_async(
            self, do,
            on_success=lambda _: self._mark_local_read(nid),
            on_failure=self._on_error,
        )

    def _mark_local_read(self, thread_id: str) -> None:
        for n in self._notifications:
            if n.id == thread_id:
                n.unread = False
        self._refresh_list()

    def _mark_all_read(self) -> None:
        svc = self._svc

        async def do() -> None:
            await svc.mark_all_read()

        def on_done(_: object) -> None:
            for n in self._notifications:
                n.unread = False
            self._refresh_list()

        self._worker = run_async(self, do, on_success=on_done, on_failure=self._on_error)

    def _unsubscribe_current(self) -> None:
        n = self._current()
        if n is None:
            return
        svc = self._svc
        nid = n.id

        async def do() -> None:
            await svc.unsubscribe(nid)

        def on_done(_: object) -> None:
            self._notifications = [x for x in self._notifications if x.id != nid]
            self._refresh_list()
            self._banner.show_info("Unsubscribed.")

        self._worker = run_async(self, do, on_success=on_done, on_failure=self._on_error)
