"""Settings dialog: endpoints, polling intervals, webhook mode, App config."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gh_desktop.auth import storage
from gh_desktop.config import Settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("gh-desktop settings")
        self.setMinimumWidth(560)
        self._settings = settings

        root = QVBoxLayout(self)

        # ----- Endpoints -----
        endpoints = QGroupBox("GitHub endpoints (override for Enterprise Server)")
        ef = QFormLayout(endpoints)
        self._api_base = QLineEdit(settings.api_base)
        self._graphql_url = QLineEdit(settings.graphql_url)
        ef.addRow("REST base", self._api_base)
        ef.addRow("GraphQL URL", self._graphql_url)
        root.addWidget(endpoints)

        # ----- OAuth / App -----
        creds = QGroupBox("OAuth / GitHub App")
        cf = QFormLayout(creds)
        self._client_id = QLineEdit(settings.oauth_client_id or "")
        self._app_id = QLineEdit(str(settings.github_app_id) if settings.github_app_id else "")
        self._app_slug = QLineEdit(settings.github_app_slug or "")
        cf.addRow("OAuth client ID", self._client_id)
        cf.addRow("GitHub App ID", self._app_id)
        cf.addRow("GitHub App slug", self._app_slug)
        root.addWidget(creds)

        # ----- Polling -----
        poll = QGroupBox("Polling intervals (seconds)")
        pf = QFormLayout(poll)
        self._poll_notifications = self._make_int_spin(settings.poll_notifications_seconds, 15, 3600)
        self._poll_issues = self._make_int_spin(settings.poll_issues_seconds, 30, 3600)
        self._poll_discussions = self._make_int_spin(settings.poll_discussions_seconds, 30, 3600)
        self._poll_actions = self._make_int_spin(settings.poll_actions_seconds, 30, 3600)
        pf.addRow("Notifications", self._poll_notifications)
        pf.addRow("Issues", self._poll_issues)
        pf.addRow("Discussions", self._poll_discussions)
        pf.addRow("Actions", self._poll_actions)
        root.addWidget(poll)

        # ----- Webhooks -----
        webhook = QGroupBox("Webhook delivery")
        wf = QFormLayout(webhook)
        self._webhook_mode = QComboBox()
        self._webhook_mode.addItems(["polling", "tunnel", "remote"])
        self._webhook_mode.setCurrentText(settings.webhook_mode)
        self._webhook_url = QLineEdit(settings.webhook_remote_url or "")
        self._cloudflared = QLineEdit(settings.cloudflared_path)
        self._subscriber_token = QLineEdit(storage.load_subscriber_token() or "")
        self._subscriber_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._subscriber_token.setPlaceholderText("from gh-desktop-receiver --gen-secrets")
        wf.addRow("Mode", self._webhook_mode)
        wf.addRow("Remote receiver URL", self._webhook_url)
        wf.addRow("Subscriber token", self._subscriber_token)
        wf.addRow("cloudflared path", self._cloudflared)
        root.addWidget(webhook)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    @staticmethod
    def _make_int_spin(value: int, lo: int, hi: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(value)
        return s

    def _save_and_accept(self) -> None:
        s = self._settings
        s.api_base = self._api_base.text().strip() or s.api_base
        s.graphql_url = self._graphql_url.text().strip() or s.graphql_url
        s.oauth_client_id = self._client_id.text().strip() or None
        s.github_app_id = int(self._app_id.text()) if self._app_id.text().strip() else None
        s.github_app_slug = self._app_slug.text().strip() or None
        s.poll_notifications_seconds = self._poll_notifications.value()
        s.poll_issues_seconds = self._poll_issues.value()
        s.poll_discussions_seconds = self._poll_discussions.value()
        s.poll_actions_seconds = self._poll_actions.value()
        s.webhook_mode = self._webhook_mode.currentText()
        s.webhook_remote_url = self._webhook_url.text().strip() or None
        s.cloudflared_path = self._cloudflared.text().strip() or "cloudflared"
        sub = self._subscriber_token.text().strip()
        if sub:
            storage.save_subscriber_token(sub)
        s.save()
        self.accept()
