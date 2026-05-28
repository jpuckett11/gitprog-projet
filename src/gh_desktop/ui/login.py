"""Login screen — shown when no user token is available in the keyring."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gh_desktop.auth import OAuthError, TokenResponse, oauth, storage
from gh_desktop.config import Settings


class _OAuthWorker(QThread):
    success = Signal(object)  # TokenResponse
    failure = Signal(str)

    def __init__(
        self,
        flow: Callable,  # async fn -> TokenResponse
        settings: Settings,
        scopes: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._flow = flow
        self._settings = settings
        self._scopes = scopes

    def run(self) -> None:
        import asyncio

        try:
            token: TokenResponse = asyncio.run(self._flow(self._settings, self._scopes))
        except OAuthError as e:
            self.failure.emit(str(e))
            return
        except Exception as e:
            self.failure.emit(f"unexpected error: {e}")
            return
        self.success.emit(token)


class LoginPane(QWidget):
    """Single screen that lets the user pick OAuth web flow or device flow."""

    logged_in = Signal()  # emitted after token stored

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._worker: _OAuthWorker | None = None

        self._stack = QStackedWidget()

        # ---- main panel ----
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        title = QLabel("Sign in to GitHub")
        title.setStyleSheet("font-size: 20pt; font-weight: 600;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("OAuth Client ID is required. Configure in Settings if not set.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888;")
        layout.addWidget(subtitle)

        # Inline client ID prompt for the very first run
        client_id_row = QHBoxLayout()
        client_id_row.addWidget(QLabel("Client ID:"))
        self._client_id_edit = QLineEdit(settings.oauth_client_id or "")
        self._client_id_edit.setPlaceholderText("Iv1.abc123…")
        client_id_row.addWidget(self._client_id_edit)
        layout.addLayout(client_id_row)

        # buttons
        btn_row = QHBoxLayout()
        self._web_btn = QPushButton("Sign in via browser (recommended)")
        self._web_btn.clicked.connect(lambda: self._start_flow("web"))
        btn_row.addWidget(self._web_btn)

        self._device_btn = QPushButton("Sign in via device code")
        self._device_btn.clicked.connect(lambda: self._start_flow("device"))
        btn_row.addWidget(self._device_btn)
        layout.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color: #d33;")
        layout.addWidget(self._status)

        self._stack.addWidget(main)

        outer = QVBoxLayout(self)
        outer.addWidget(self._stack)

    def _start_flow(self, kind: str) -> None:
        client_id = self._client_id_edit.text().strip()
        if not client_id:
            self._status.setText("Client ID is required.")
            return
        self._settings.oauth_client_id = client_id
        self._settings.save()

        self._web_btn.setEnabled(False)
        self._device_btn.setEnabled(False)
        self._status.setText("Waiting for browser…" if kind == "web" else "Waiting for device approval…")
        self._status.setStyleSheet("color: #888;")

        flow = oauth.web_flow if kind == "web" else oauth.device_flow
        scopes = ["repo", "read:org", "notifications", "read:discussion", "write:discussion"]
        self._worker = _OAuthWorker(flow, self._settings, scopes, self)
        self._worker.success.connect(self._on_success)
        self._worker.failure.connect(self._on_failure)
        self._worker.start()

    def _on_success(self, token: TokenResponse) -> None:
        storage.save_user_token(token.access_token, token.refresh_token)
        self._status.setStyleSheet("color: #2a2;")
        self._status.setText("Signed in.")
        self.logged_in.emit()

    def _on_failure(self, msg: str) -> None:
        self._web_btn.setEnabled(True)
        self._device_btn.setEnabled(True)
        self._status.setStyleSheet("color: #d33;")
        self._status.setText(msg)
