"""Main application window: login overlay, sidebar, three mode tabs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from gh_desktop.api.services import NotificationsService
from gh_desktop.auth import storage
from gh_desktop.config import Settings
from gh_desktop.ui.login import LoginPane
from gh_desktop.ui.modes.admin import AdminMode
from gh_desktop.ui.modes.contents import ContentsMode
from gh_desktop.ui.modes.investigation import InvestigationMode
from gh_desktop.ui.modes.triage import TriageMode
from gh_desktop.ui.repo_picker import RepoPicker
from gh_desktop.ui.settings import SettingsDialog
from gh_desktop.ui.widgets import Terminal
from gh_desktop.workspace import Workspace


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._workspace: Workspace | None = None
        self.setWindowTitle("gh-desktop")
        self.resize(1280, 800)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._login = LoginPane(settings, self)
        self._login.logged_in.connect(self._on_logged_in)
        self._stack.addWidget(self._login)

        self._workspace_widget: QWidget | None = None
        self._terminal_dock: QDockWidget | None = None
        self._terminal: Terminal | None = None

        self.setStatusBar(QStatusBar())

        self._build_menus()
        self._build_terminal_dock()
        self._route_initial()

    # ---------- menus ----------

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        act_settings = QAction("Settings…", self)
        act_settings.triggered.connect(self._open_settings)
        file_menu.addAction(act_settings)

        act_signout = QAction("Sign out", self)
        act_signout.triggered.connect(self._sign_out)
        file_menu.addAction(act_signout)

        file_menu.addSeparator()
        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = self.menuBar().addMenu("&View")

        self._act_toggle_terminal = QAction("Toggle &Terminal", self)
        self._act_toggle_terminal.setCheckable(True)
        self._act_toggle_terminal.setShortcut(QKeySequence("Ctrl+`"))
        self._act_toggle_terminal.triggered.connect(self._toggle_terminal)
        view_menu.addAction(self._act_toggle_terminal)

        act_focus_terminal = QAction("Focus terminal input", self)
        act_focus_terminal.setShortcut(QKeySequence("Ctrl+Shift+`"))
        act_focus_terminal.triggered.connect(self._focus_terminal)
        view_menu.addAction(act_focus_terminal)

        view_menu.addSeparator()

        act_refresh = QAction("Refresh current view", self)
        act_refresh.setShortcut(QKeySequence("Ctrl+R"))
        act_refresh.triggered.connect(self._refresh_current_view)
        view_menu.addAction(act_refresh)

    def _build_terminal_dock(self) -> None:
        dock = QDockWidget("Terminal", self)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self._terminal = Terminal()
        dock.setWidget(self._terminal)
        dock.setMinimumHeight(180)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.hide()  # start collapsed
        dock.visibilityChanged.connect(self._on_terminal_visibility_changed)
        self._terminal_dock = dock

    def _toggle_terminal(self) -> None:
        if self._terminal_dock is None:
            return
        self._terminal_dock.setVisible(not self._terminal_dock.isVisible())
        if self._terminal_dock.isVisible() and self._terminal is not None:
            self._terminal.focus_input()

    def _on_terminal_visibility_changed(self, visible: bool) -> None:
        self._act_toggle_terminal.setChecked(visible)

    def _focus_terminal(self) -> None:
        if self._terminal_dock is None or self._terminal is None:
            return
        if not self._terminal_dock.isVisible():
            self._terminal_dock.setVisible(True)
        self._terminal.focus_input()

    def _refresh_current_view(self) -> None:
        if self._workspace_widget is None:
            return
        current = self._tabs.currentWidget()
        for method in ("refresh", "_load_root", "_reload"):
            fn = getattr(current, method, None)
            if callable(fn):
                fn()
                return

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        dlg.exec()

    def _sign_out(self) -> None:
        confirm = QMessageBox.question(
            self, "Sign out", "Remove stored OAuth token and return to login?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        storage.clear_user_token()
        if self._workspace is not None:
            self._workspace.poller.stop()
        self._stack.setCurrentWidget(self._login)
        self.statusBar().showMessage("Signed out.")

    # ---------- workspace ----------

    def _route_initial(self) -> None:
        if storage.load_user_token() is not None:
            self._build_workspace()
            assert self._workspace_widget is not None
            self._stack.setCurrentWidget(self._workspace_widget)
        else:
            self._stack.setCurrentWidget(self._login)

    def _on_logged_in(self) -> None:
        if self._workspace_widget is None:
            self._build_workspace()
        assert self._workspace_widget is not None
        self._stack.setCurrentWidget(self._workspace_widget)
        self.statusBar().showMessage("Signed in.", 4000)

    def _build_workspace(self) -> None:
        ws = Workspace.build(self._settings)
        self._workspace = ws

        # Register polling resources (notifications only for now)
        notifications_svc = NotificationsService(ws.rest)

        async def fetch_notifications():
            return await notifications_svc.list(all=True, max_pages=1)

        ws.poller.add_resource(
            "notifications",
            interval=float(self._settings.poll_notifications_seconds),
            fetch=fetch_notifications,
        )
        ws.poller.start()

        # Start webhook bridge / tunnel if configured
        if ws.bridge is not None:
            ws.bridge.state_changed.connect(
                lambda s: self.statusBar().showMessage(f"webhook bridge: {s}", 5000)
            )
            ws.bridge.start()
        if ws.tunnel is not None:
            ws.tunnel.state_changed.connect(
                lambda s: self.statusBar().showMessage(f"tunnel: {s}", 5000)
            )
            ws.tunnel.url_ready.connect(
                lambda url: self.statusBar().showMessage(
                    f"tunnel ready — webhook URL: {url}/webhook", 0
                )
            )
            ws.tunnel.start()

        splitter = QSplitter()
        self._repo_picker = RepoPicker(ws)
        splitter.addWidget(self._repo_picker)

        self._tabs = QTabWidget()
        self._triage = TriageMode(ws)
        self._investigation = InvestigationMode(ws)
        self._admin = AdminMode(ws)
        self._contents = ContentsMode(ws)
        self._tabs.addTab(self._triage, "Triage")
        self._tabs.addTab(self._investigation, "Investigation")
        self._tabs.addTab(self._admin, "Admin")
        self._tabs.addTab(self._contents, "Contents")
        splitter.addWidget(self._tabs)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([280, 1000])

        # Route repo-picker selection to the modes
        self._repo_picker.selection_changed.connect(self._on_scope_change)

        self._workspace_widget = splitter
        self._stack.addWidget(self._workspace_widget)

    def _on_scope_change(self, scope: str) -> None:
        if not scope:
            return
        # Investigation + Contents need a repo (owner/repo); Admin accepts both.
        if "/" in scope and not scope.startswith("@"):
            self._investigation.set_scope(scope)
            self._contents.set_scope(scope)
        self._admin.set_scope(scope)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._workspace is not None:
            self._workspace.poller.stop()
        super().closeEvent(event)
