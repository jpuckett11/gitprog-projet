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
from gh_desktop.ui.theme import ACCENT_HI, APP_NAME, APP_TAGLINE, ERROR, SUCCESS, TEXT_MUTED


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
        outer_v = QVBoxLayout(main)
        outer_v.setContentsMargins(0, 0, 0, 0)
        outer_v.addStretch(1)

        # centered card
        card = QWidget()
        card.setMaximumWidth(540)
        card.setObjectName("loginCard")
        card.setStyleSheet(
            """
            QWidget#loginCard {
                background-color: #1f1828;
                border: 1px solid #3d2d52;
                border-radius: 14px;
            }
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(12)

        # Brand
        brand = QLabel(APP_NAME)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet(
            f"font-size: 36pt; font-weight: 700; color: {ACCENT_HI}; letter-spacing: 2px;"
        )
        layout.addWidget(brand)

        tagline = QLabel(APP_TAGLINE)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(f"font-size: 11pt; color: {TEXT_MUTED}; margin-bottom: 16px;")
        layout.addWidget(tagline)

        # spacer
        layout.addSpacing(20)

        sub = QLabel("Sign in with your GitHub account")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 13pt; font-weight: 500;")
        layout.addWidget(sub)

        hint = QLabel("Paste your OAuth App Client ID below. (Settings can change it later.)")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9pt;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(6)

        # Inline client ID prompt for the very first run
        client_id_row = QHBoxLayout()
        client_id_row.addWidget(QLabel("Client ID"))
        self._client_id_edit = QLineEdit(settings.oauth_client_id or "")
        self._client_id_edit.setPlaceholderText("Iv1.abc123… or Ov23li…")
        client_id_row.addWidget(self._client_id_edit, 1)
        layout.addLayout(client_id_row)

        # buttons
        btn_row = QHBoxLayout()
        self._web_btn = QPushButton("Sign in via browser  →")
        self._web_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ACCENT_HI};
                color: #ffffff;
                font-weight: 600;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #c684ff; }}
            QPushButton:disabled {{ background-color: #54487a; color: #aaa; }}
            """
        )
        self._web_btn.clicked.connect(lambda: self._start_flow("web"))
        btn_row.addWidget(self._web_btn, 2)

        self._device_btn = QPushButton("Device code")
        self._device_btn.clicked.connect(lambda: self._start_flow("device"))
        btn_row.addWidget(self._device_btn, 1)
        layout.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"color: {ERROR};")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # store success/error colors for runtime swaps
        self._color_success = SUCCESS
        self._color_error = ERROR
        self._color_muted = TEXT_MUTED

        # center the card horizontally
        card_h = QHBoxLayout()
        card_h.addStretch(1)
        card_h.addWidget(card)
        card_h.addStretch(1)
        outer_v.addLayout(card_h)

        outer_v.addStretch(2)

        self._stack.addWidget(main)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
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
        self._status.setStyleSheet(f"color: {self._color_muted};")

        flow = oauth.web_flow if kind == "web" else oauth.device_flow
        scopes = ["repo", "read:org", "notifications", "read:discussion", "write:discussion"]
        self._worker = _OAuthWorker(flow, self._settings, scopes, self)
        self._worker.success.connect(self._on_success)
        self._worker.failure.connect(self._on_failure)
        self._worker.start()

    def _on_success(self, token: TokenResponse) -> None:
        storage.save_user_token(token.access_token, token.refresh_token)
        self._status.setStyleSheet(f"color: {self._color_success};")
        self._status.setText("Signed in.")
        self.logged_in.emit()

    def _on_failure(self, msg: str) -> None:
        self._web_btn.setEnabled(True)
        self._device_btn.setEnabled(True)
        self._status.setStyleSheet(f"color: {self._color_error};")
        self._status.setText(msg)
