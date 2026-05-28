"""Smoke tests — imports and basic construction."""

from __future__ import annotations

import pytest


def test_imports() -> None:
    """All top-level modules import without error."""
    import gh_desktop
    import gh_desktop.api
    import gh_desktop.api.services
    import gh_desktop.auth
    import gh_desktop.config
    import gh_desktop.models
    import gh_desktop.polling
    import gh_desktop.workspace  # noqa: F401


def test_settings_defaults() -> None:
    from gh_desktop.config import Settings

    s = Settings()
    assert s.api_base.startswith("https://")
    assert s.poll_notifications_seconds > 0


def test_pkce_pair_unique() -> None:
    from gh_desktop.auth.oauth import _pkce_pair

    v1, c1 = _pkce_pair()
    v2, c2 = _pkce_pair()
    assert v1 != v2
    assert c1 != c2
    assert len(v1) >= 43
    assert len(c1) >= 43


def test_make_jwt_roundtrip() -> None:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from gh_desktop.auth.github_app import make_jwt

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    token = make_jwt(12345, pem)
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    decoded = jwt.decode(token, pub_pem, algorithms=["RS256"])
    assert decoded["iss"] == "12345"


def test_secret_encryption_roundtrip() -> None:
    """Encrypting with a known keypair produces a payload the same key can decrypt."""
    import base64

    from nacl import encoding, public

    from gh_desktop.api.services.secrets import encrypt_secret

    sk = public.PrivateKey.generate()
    pk_b64 = sk.public_key.encode(encoder=encoding.Base64Encoder).decode()
    enc = encrypt_secret(pk_b64, "hunter2")
    decrypted = public.SealedBox(sk).decrypt(base64.b64decode(enc))
    assert decrypted == b"hunter2"


def test_main_window_constructs(qtbot) -> None:
    """MainWindow constructs without crashing (no auth required)."""
    from gh_desktop.config import Settings
    from gh_desktop.ui.main_window import MainWindow

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    assert w.windowTitle() == "gh-desktop"


def test_workspace_builds(qtbot) -> None:
    """Workspace.build wires all clients without running them."""
    from gh_desktop.config import Settings
    from gh_desktop.workspace import Workspace

    ws = Workspace.build(Settings())
    assert ws.rest is not None
    assert ws.graphql is not None
    assert ws.poller is not None


@pytest.mark.parametrize("mode_cls_path", [
    "gh_desktop.ui.modes.triage.TriageMode",
    "gh_desktop.ui.modes.investigation.InvestigationMode",
    "gh_desktop.ui.modes.admin.AdminMode",
])
def test_modes_construct(qtbot, mode_cls_path: str) -> None:
    import importlib

    from gh_desktop.config import Settings
    from gh_desktop.workspace import Workspace

    module_name, cls_name = mode_cls_path.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_name), cls_name)
    ws = Workspace.build(Settings())
    w = cls(ws)
    qtbot.addWidget(w)


def test_repo_picker_constructs(qtbot) -> None:
    from gh_desktop.config import Settings
    from gh_desktop.ui.repo_picker import RepoPicker
    from gh_desktop.workspace import Workspace

    ws = Workspace.build(Settings())
    w = RepoPicker(ws)
    qtbot.addWidget(w)
