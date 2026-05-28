"""Admin mode — org/repo dashboard.

Sub-tabs (per scope):
  - Members (org only)
  - Secrets (org or repo)
  - Actions runs (repo)
  - Webhooks (org or repo)

Scope is set externally via set_scope(scope) where scope is either "owner/repo" or "@org".
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gh_desktop.api.services import (
    ActionsService,
    MembersService,
    SecretsService,
    WebhooksService,
)
from gh_desktop.api.services.secrets import encrypt_secret
from gh_desktop.ui.widgets import StatusBanner, humanize, run_async
from gh_desktop.workspace import Workspace


class AdminMode(QWidget):
    def __init__(self, workspace: Workspace, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._scope: str = ""
        self._workers: list[Any] = []

        self._actions_svc = ActionsService(workspace.rest)
        self._secrets_svc = SecretsService(workspace.rest)
        self._webhooks_svc = WebhooksService(workspace.rest)
        self._members_svc = MembersService(workspace.rest)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.addWidget(QLabel("Scope:"))
        self._scope_input = QLineEdit()
        self._scope_input.setPlaceholderText("owner/repo  or  @org")
        self._scope_input.returnPressed.connect(self._on_scope_changed)
        toolbar.addWidget(self._scope_input, 1)
        self._load_btn = QPushButton("Load")
        self._load_btn.clicked.connect(self._on_scope_changed)
        toolbar.addWidget(self._load_btn)
        outer.addLayout(toolbar)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        self._tabs = QTabWidget()
        self._members_tab = _MembersTab(self._members_svc, self._banner)
        self._secrets_tab = _SecretsTab(self._secrets_svc, self._banner)
        self._actions_tab = _ActionsTab(self._actions_svc, self._banner)
        self._webhooks_tab = _WebhooksTab(self._webhooks_svc, self._banner)

        self._tabs.addTab(self._members_tab, "Members")
        self._tabs.addTab(self._secrets_tab, "Secrets")
        self._tabs.addTab(self._actions_tab, "Actions")
        self._tabs.addTab(self._webhooks_tab, "Webhooks")
        outer.addWidget(self._tabs, 1)

    def set_scope(self, scope: str) -> None:
        if not scope:
            return
        self._scope_input.setText(scope)
        self._on_scope_changed()

    def _on_scope_changed(self) -> None:
        scope = self._scope_input.text().strip()
        if not scope:
            return
        self._scope = scope
        is_org = scope.startswith("@")
        is_repo = "/" in scope and not is_org

        # enable/disable tabs based on scope
        self._tabs.setTabEnabled(0, is_org)            # members
        self._tabs.setTabEnabled(1, is_org or is_repo)  # secrets
        self._tabs.setTabEnabled(2, is_repo)           # actions
        self._tabs.setTabEnabled(3, is_org or is_repo)  # webhooks

        self._members_tab.set_scope(scope)
        self._secrets_tab.set_scope(scope)
        self._actions_tab.set_scope(scope)
        self._webhooks_tab.set_scope(scope)


# ---------- Members tab ----------

class _MembersTab(QWidget):
    def __init__(self, svc: MembersService, banner: StatusBanner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._banner = banner
        self._scope: str = ""
        self._worker = None

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Login", "Type", "Profile"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def set_scope(self, scope: str) -> None:
        self._scope = scope
        if not scope.startswith("@"):
            return
        org = scope.lstrip("@")
        self._banner.show_busy(f"Loading members of @{org}…")
        svc = self._svc

        async def fetch():
            return await svc.list_org_members(org, max_pages=3)

        self._worker = run_async(self, fetch, on_success=self._populate, on_failure=self._error)

    def _populate(self, members) -> None:
        self._table.setRowCount(0)
        for m in members:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(m.login))
            self._table.setItem(row, 1, QTableWidgetItem(m.type or "User"))
            link = QTableWidgetItem(f"https://github.com/{m.login}")
            self._table.setItem(row, 2, link)
        self._banner.setVisible(False)

    def _error(self, exc: Exception) -> None:
        self._banner.show_error(f"Members: {exc}")


# ---------- Secrets tab ----------

class _SecretsTab(QWidget):
    def __init__(self, svc: SecretsService, banner: StatusBanner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._banner = banner
        self._scope: str = ""
        self._worker = None

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self._add_btn = QPushButton("Add / update secret…")
        self._add_btn.clicked.connect(self._add_secret)
        self._delete_btn = QPushButton("Delete selected")
        self._delete_btn.clicked.connect(self._delete_secret)
        controls.addWidget(self._add_btn)
        controls.addWidget(self._delete_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Name", "Updated"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def set_scope(self, scope: str) -> None:
        self._scope = scope
        self._reload()

    def _reload(self) -> None:
        svc = self._svc
        scope = self._scope

        if scope.startswith("@"):
            org = scope.lstrip("@")

            async def fetch():
                return await svc.list_org_secrets(org)
        elif "/" in scope:
            owner, repo = scope.split("/", 1)

            async def fetch():
                return await svc.list_repo_secrets(owner, repo)
        else:
            return

        self._banner.show_busy("Loading secrets…")
        self._worker = run_async(self, fetch, on_success=self._populate, on_failure=self._error)

    def _populate(self, secrets) -> None:
        self._table.setRowCount(0)
        for s in secrets:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(humanize(s.get("updated_at"))))
        self._banner.setVisible(False)

    def _add_secret(self) -> None:
        name, ok = QInputDialog.getText(self, "Add secret", "Secret name:")
        if not ok or not name.strip():
            return
        value, ok = QInputDialog.getText(self, "Add secret", f"Value for {name}:", echo=QLineEdit.EchoMode.Password)
        if not ok:
            return
        svc = self._svc
        scope = self._scope

        if scope.startswith("@"):
            org = scope.lstrip("@")

            async def do():
                pk = await svc.get_org_public_key(org)
                encrypted = encrypt_secret(pk["key"], value)
                await svc.put_org_secret(org, name.strip(), encrypted_value=encrypted, key_id=pk["key_id"])
        elif "/" in scope:
            owner, repo = scope.split("/", 1)

            async def do():
                pk = await svc.get_repo_public_key(owner, repo)
                encrypted = encrypt_secret(pk["key"], value)
                await svc.put_repo_secret(owner, repo, name.strip(), encrypted_value=encrypted, key_id=pk["key_id"])
        else:
            return

        self._banner.show_busy(f"Saving {name}…")
        self._worker = run_async(
            self, do,
            on_success=lambda _: (self._banner.show_info(f"Saved {name}."), self._reload()),
            on_failure=self._error,
        )

    def _delete_secret(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._table.item(row, 0).text()
        ok = QMessageBox.question(self, "Delete secret", f"Delete secret {name!r}?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        svc = self._svc
        scope = self._scope

        if scope.startswith("@"):
            org = scope.lstrip("@")

            async def do():
                await svc.delete_org_secret(org, name)
        elif "/" in scope:
            owner, repo = scope.split("/", 1)

            async def do():
                await svc.delete_repo_secret(owner, repo, name)
        else:
            return

        self._worker = run_async(
            self, do,
            on_success=lambda _: (self._banner.show_info(f"Deleted {name}."), self._reload()),
            on_failure=self._error,
        )

    def _error(self, exc: Exception) -> None:
        self._banner.show_error(f"Secrets: {exc}")


# ---------- Actions tab ----------

class _ActionsTab(QWidget):
    def __init__(self, svc: ActionsService, banner: StatusBanner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._banner = banner
        self._scope: str = ""
        self._worker = None

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Workflow", "Run #", "Status", "Conclusion", "Updated"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemDoubleClicked.connect(self._open_run)
        layout.addWidget(self._table)

    def set_scope(self, scope: str) -> None:
        self._scope = scope
        if "/" not in scope or scope.startswith("@"):
            return
        owner, repo = scope.split("/", 1)
        svc = self._svc
        self._banner.show_busy("Loading workflow runs…")

        async def fetch():
            return await svc.list_workflow_runs(owner, repo, max_pages=2)

        self._worker = run_async(self, fetch, on_success=self._populate, on_failure=self._error)

    def _populate(self, runs) -> None:
        self._table.setRowCount(0)
        for r in runs:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(r.get("name") or ""))
            self._table.setItem(row, 1, QTableWidgetItem(str(r.get("run_number", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(r.get("status") or ""))
            self._table.setItem(row, 3, QTableWidgetItem(r.get("conclusion") or ""))
            self._table.setItem(row, 4, QTableWidgetItem(humanize(r.get("updated_at"))))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, r.get("html_url"))
        self._banner.setVisible(False)

    def _open_run(self, item: QTableWidgetItem) -> None:
        row = item.row()
        url = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if url:
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(url))

    def _error(self, exc: Exception) -> None:
        self._banner.show_error(f"Actions: {exc}")


# ---------- Webhooks tab ----------

class _WebhooksTab(QWidget):
    def __init__(self, svc: WebhooksService, banner: StatusBanner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._banner = banner
        self._scope: str = ""
        self._worker = None

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self._add_btn = QPushButton("Add webhook…")
        self._add_btn.clicked.connect(self._add_hook)
        self._delete_btn = QPushButton("Delete selected")
        self._delete_btn.clicked.connect(self._delete_hook)
        controls.addWidget(self._add_btn)
        controls.addWidget(self._delete_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["ID", "URL", "Events", "Active"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def set_scope(self, scope: str) -> None:
        self._scope = scope
        self._reload()

    def _reload(self) -> None:
        svc = self._svc
        scope = self._scope

        if scope.startswith("@"):
            org = scope.lstrip("@")

            async def fetch():
                return await svc.list_org_hooks(org)
        elif "/" in scope:
            owner, repo = scope.split("/", 1)

            async def fetch():
                return await svc.list_repo_hooks(owner, repo)
        else:
            return

        self._banner.show_busy("Loading webhooks…")
        self._worker = run_async(self, fetch, on_success=self._populate, on_failure=self._error)

    def _populate(self, hooks) -> None:
        self._table.setRowCount(0)
        for h in hooks:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(h.get("id", ""))))
            self._table.setItem(row, 1, QTableWidgetItem((h.get("config") or {}).get("url", "")))
            events = ", ".join(h.get("events", []))
            self._table.setItem(row, 2, QTableWidgetItem(events))
            self._table.setItem(row, 3, QTableWidgetItem("yes" if h.get("active") else "no"))
        self._banner.setVisible(False)

    def _add_hook(self) -> None:
        url, ok = QInputDialog.getText(self, "Add webhook", "Payload URL (https://…):")
        if not ok or not url.strip():
            return
        events_str, ok = QInputDialog.getText(
            self, "Add webhook",
            "Events (comma-separated, e.g. push,issues,discussion):",
            text="push,issues,pull_request",
        )
        if not ok:
            return
        events = [e.strip() for e in events_str.split(",") if e.strip()]
        secret, _ = QInputDialog.getText(
            self, "Add webhook",
            "Optional shared secret (recommended):",
            echo=QLineEdit.EchoMode.Password,
        )

        svc = self._svc
        scope = self._scope

        if scope.startswith("@"):
            org = scope.lstrip("@")

            async def do():
                return await svc.create_org_hook(
                    org, url=url.strip(), events=events, secret=secret.strip() or None
                )
        elif "/" in scope:
            owner, repo = scope.split("/", 1)

            async def do():
                return await svc.create_repo_hook(
                    owner, repo, url=url.strip(), events=events, secret=secret.strip() or None
                )
        else:
            return

        self._banner.show_busy("Creating webhook…")
        self._worker = run_async(
            self, do,
            on_success=lambda _: (self._banner.show_info("Webhook created."), self._reload()),
            on_failure=self._error,
        )

    def _delete_hook(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        try:
            hook_id = int(self._table.item(row, 0).text())
        except (ValueError, AttributeError):
            return
        ok = QMessageBox.question(self, "Delete webhook", f"Delete webhook {hook_id}?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        svc = self._svc
        scope = self._scope

        if scope.startswith("@"):
            org = scope.lstrip("@")

            async def do():
                await svc.delete_org_hook(org, hook_id)
        elif "/" in scope:
            owner, repo = scope.split("/", 1)

            async def do():
                await svc.delete_repo_hook(owner, repo, hook_id)
        else:
            return

        self._worker = run_async(
            self, do,
            on_success=lambda _: (self._banner.show_info(f"Deleted webhook {hook_id}."), self._reload()),
            on_failure=self._error,
        )

    def _error(self, exc: Exception) -> None:
        self._banner.show_error(f"Webhooks: {exc}")
