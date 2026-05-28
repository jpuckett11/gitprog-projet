"""Search mode — global cross-repo search.

UI:
  Toolbar: type combo, query input (Enter to search), sort combo
  Left:    Saved searches list (pinned). Click to re-run.
  Center:  Results list. Double-click opens in browser.
  Right:   Selected result preview.

Saved searches are persisted in CONFIG_FILE under a [saved_searches] section.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gh_desktop.api.services import SearchKind, SearchResult, SearchService
from gh_desktop.config import CONFIG_DIR
from gh_desktop.ui.widgets import MarkdownView, StatusBanner, humanize, run_async
from gh_desktop.workspace import Workspace

SAVED_SEARCHES_FILE: Path = CONFIG_DIR / "saved_searches.toml"

_KIND_LABELS = {
    "issues": "Issues",
    "prs": "Pull requests",
    "repos": "Repositories",
    "code": "Code",
    "users": "Users",
}

_SORT_OPTIONS = {
    "issues": ["best match", "updated", "created", "comments", "reactions"],
    "prs": ["best match", "updated", "created", "comments", "reactions"],
    "repos": ["best match", "stars", "forks", "updated"],
    "code": ["best match", "indexed"],
    "users": ["best match", "followers", "repositories", "joined"],
}


def _load_saved() -> dict[str, dict[str, str]]:
    if not SAVED_SEARCHES_FILE.exists():
        return {}
    try:
        with SAVED_SEARCHES_FILE.open("rb") as f:
            data = tomllib.load(f)
        return {k: dict(v) for k, v in (data.get("searches") or {}).items()}
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _save_saved(searches: dict[str, dict[str, str]]) -> None:
    SAVED_SEARCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SAVED_SEARCHES_FILE.open("wb") as f:
        tomli_w.dump({"searches": searches}, f)


class SearchMode(QWidget):
    def __init__(self, workspace: Workspace, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._svc = SearchService(workspace.rest)
        self._results: list[SearchResult] = []
        self._workers: list[Any] = []
        self._saved: dict[str, dict[str, str]] = _load_saved()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.addWidget(QLabel("Type:"))
        self._kind_combo = QComboBox()
        for k, lbl in _KIND_LABELS.items():
            self._kind_combo.addItem(lbl, k)
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        toolbar.addWidget(self._kind_combo)

        self._query_input = QLineEdit()
        self._query_input.setPlaceholderText("e.g. user:jpuckett11 is:open label:bug")
        self._query_input.returnPressed.connect(self._run_search)
        toolbar.addWidget(self._query_input, 1)

        toolbar.addWidget(QLabel("Sort:"))
        self._sort_combo = QComboBox()
        self._sync_sort_options()
        toolbar.addWidget(self._sort_combo)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._run_search)
        toolbar.addWidget(self._search_btn)

        self._save_btn = QPushButton("Save…")
        self._save_btn.clicked.connect(self._save_current)
        toolbar.addWidget(self._save_btn)

        outer.addLayout(toolbar)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        # three-pane: saved | results | preview
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.addWidget(QLabel("Saved searches"))
        self._saved_list = QListWidget()
        self._saved_list.itemDoubleClicked.connect(self._on_saved_activated)
        ll.addWidget(self._saved_list, 1)
        self._delete_btn = QPushButton("Delete selected")
        self._delete_btn.clicked.connect(self._delete_saved)
        ll.addWidget(self._delete_btn)
        splitter.addWidget(left)

        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        self._results_list = QListWidget()
        self._results_list.itemSelectionChanged.connect(self._on_select)
        self._results_list.itemDoubleClicked.connect(self._open_current)
        cl.addWidget(self._results_list)
        splitter.addWidget(center)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        self._preview_header = QLabel("Select a result to preview.")
        self._preview_header.setStyleSheet("font-weight: 600;")
        self._preview_header.setWordWrap(True)
        rl.addWidget(self._preview_header)
        self._preview_meta = QLabel("")
        self._preview_meta.setStyleSheet("color: #888;")
        self._preview_meta.setWordWrap(True)
        rl.addWidget(self._preview_meta)
        self._preview_body = MarkdownView()
        rl.addWidget(self._preview_body, 1)
        self._open_btn = QPushButton("Open in browser")
        self._open_btn.clicked.connect(self._open_current)
        rl.addWidget(self._open_btn)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 4)
        splitter.setSizes([220, 480, 480])
        outer.addWidget(splitter, 1)

        self._refresh_saved_list()

    # ---------- kind / sort wiring ----------

    def _current_kind(self) -> SearchKind:
        return self._kind_combo.currentData()

    def _sync_sort_options(self) -> None:
        kind = self._kind_combo.currentData() or "issues"
        opts = _SORT_OPTIONS.get(kind, ["best match"])
        self._sort_combo.blockSignals(True)
        self._sort_combo.clear()
        self._sort_combo.addItems(opts)
        self._sort_combo.blockSignals(False)

    def _on_kind_changed(self) -> None:
        self._sync_sort_options()

    # ---------- search ----------

    def _run_search(self) -> None:
        q = self._query_input.text().strip()
        if not q:
            self._banner.show_error("Enter a query.")
            return
        kind = self._current_kind()
        sort = self._sort_combo.currentText()
        sort_param = None if sort == "best match" else sort
        svc = self._svc

        self._banner.show_busy(f"Searching {kind}…")
        self._results_list.clear()

        async def do() -> list[SearchResult]:
            return await svc.search(kind, q, sort=sort_param)

        def on_done(results: list[SearchResult]) -> None:
            self._results = results
            self._banner.setVisible(False)
            for r in results:
                item = QListWidgetItem(f"{r.title}\n    {r.subtitle}")
                item.setData(Qt.ItemDataRole.UserRole, r)
                self._results_list.addItem(item)
            if not results:
                self._banner.show_info("No results.")

        def on_err(exc: Exception) -> None:
            self._banner.show_error(f"Search failed: {exc}")

        self._workers.append(run_async(self, do, on_success=on_done, on_failure=on_err))

    # ---------- selection / preview ----------

    def _current_result(self) -> SearchResult | None:
        items = self._results_list.selectedItems()
        if not items:
            return None
        data = items[0].data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, SearchResult) else None

    def _on_select(self) -> None:
        r = self._current_result()
        if r is None:
            self._preview_header.setText("Select a result to preview.")
            self._preview_meta.setText("")
            self._preview_body.set_markdown("")
            return
        self._preview_header.setText(r.title)
        self._preview_meta.setText(r.subtitle)
        body = ""
        if r.kind in ("issues", "prs"):
            body = r.raw.get("body") or ""
            updated = r.raw.get("updated_at")
            if updated:
                self._preview_meta.setText(
                    f"{r.subtitle} · updated {humanize(updated)}"
                )
        elif r.kind == "repos":
            body = (r.raw.get("description") or "") + "\n\n" + (r.raw.get("html_url") or "")
        elif r.kind == "code":
            body = (
                f"**Path:** `{r.raw.get('path','?')}`\n\n"
                f"Open the result in your browser to view the highlighted match."
            )
        elif r.kind == "users":
            body = (
                f"**Profile:** {r.raw.get('html_url','')}\n\n"
                f"Type: {r.raw.get('type','User')}"
            )
        self._preview_body.set_markdown(body or "_(no body)_")

    def _open_current(self) -> None:
        r = self._current_result()
        if r is None or not r.url:
            return
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(r.url))

    # ---------- saved searches ----------

    def _refresh_saved_list(self) -> None:
        self._saved_list.clear()
        for name in sorted(self._saved.keys()):
            cfg = self._saved[name]
            label = f"{name}\n    [{cfg.get('kind','issues')}] {cfg.get('query','')}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._saved_list.addItem(item)

    def _on_saved_activated(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        cfg = self._saved.get(name)
        if not cfg:
            return
        # restore kind
        for i in range(self._kind_combo.count()):
            if self._kind_combo.itemData(i) == cfg.get("kind"):
                self._kind_combo.setCurrentIndex(i)
                break
        self._query_input.setText(cfg.get("query", ""))
        if cfg.get("sort"):
            idx = self._sort_combo.findText(cfg["sort"])
            if idx >= 0:
                self._sort_combo.setCurrentIndex(idx)
        self._run_search()

    def _save_current(self) -> None:
        q = self._query_input.text().strip()
        if not q:
            self._banner.show_error("Nothing to save — enter a query first.")
            return
        name, ok = QInputDialog.getText(self, "Save search", "Name:")
        if not ok or not name.strip():
            return
        self._saved[name.strip()] = {
            "kind": self._current_kind(),
            "query": q,
            "sort": self._sort_combo.currentText(),
        }
        _save_saved(self._saved)
        self._refresh_saved_list()
        self._banner.show_info(f"Saved: {name.strip()}")

    def _delete_saved(self) -> None:
        items = self._saved_list.selectedItems()
        if not items:
            return
        name = items[0].data(Qt.ItemDataRole.UserRole)
        if name in self._saved:
            del self._saved[name]
            _save_saved(self._saved)
            self._refresh_saved_list()
            self._banner.show_info(f"Deleted: {name}")
