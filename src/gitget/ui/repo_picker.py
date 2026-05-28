"""Sidebar that lists the user's repos / orgs.

Emits selection_changed with a string like:
  "owner/repo"   for a repository
  "@org"         for an organization
  ""             when selection is cleared
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gitget.api.services import OrgsService, ReposService
from gitget.models import Organization, Repository
from gitget.ui.widgets import StatusBanner, run_async
from gitget.workspace import Workspace


class RepoPicker(QWidget):
    selection_changed = Signal(str)

    def __init__(self, workspace: Workspace, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._worker = None  # keep refs alive

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Scope"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter…")
        layout.addWidget(self._search)

        self._banner = StatusBanner()
        layout.addWidget(self._banner)

        self._list = QListWidget()
        layout.addWidget(self._list, stretch=1)

        self._list.itemSelectionChanged.connect(self._on_selection)
        self._search.textChanged.connect(self._on_filter)

        self.refresh()

    def refresh(self) -> None:
        self._banner.show_busy("Loading repos and orgs…")

        async def fetch() -> tuple[list[Organization], list[Repository]]:
            orgs_svc = OrgsService(self._workspace.rest)
            repos_svc = ReposService(self._workspace.rest)
            orgs = await orgs_svc.list_for_authenticated_user()
            repos = await repos_svc.list_for_authenticated_user(max_pages=3)
            return orgs, repos

        self._worker = run_async(
            self,
            fetch,
            on_success=self._on_loaded,
            on_failure=self._on_error,
        )

    def _on_loaded(self, result: tuple[list[Organization], list[Repository]]) -> None:
        orgs, repos = result
        self._list.clear()
        for org in orgs:
            item = QListWidgetItem(f"@{org.login}")
            item.setData(Qt.ItemDataRole.UserRole, f"@{org.login}")
            self._list.addItem(item)
        if orgs:
            sep = QListWidgetItem("—")
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(sep)
        for r in repos:
            label = r.full_name + (" 🔒" if r.private else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, r.full_name)
            self._list.addItem(item)
        self._banner.setVisible(False)

    def _on_error(self, exc: Exception) -> None:
        self._banner.show_error(f"Couldn't load: {exc}")

    def _on_selection(self) -> None:
        items = self._list.selectedItems()
        if not items:
            self.selection_changed.emit("")
            return
        data = items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(data, str):
            self.selection_changed.emit(data)

    def _on_filter(self, text: str) -> None:
        text = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(text not in item.text().lower())
