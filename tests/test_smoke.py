"""Smoke tests — imports and basic construction."""

from __future__ import annotations

import pytest


def test_imports() -> None:
    """All top-level modules import without error."""
    import gitget
    import gitget.api
    import gitget.api.services
    import gitget.auth
    import gitget.config
    import gitget.models
    import gitget.polling
    import gitget.workspace  # noqa: F401


def test_settings_defaults() -> None:
    from gitget.config import Settings

    s = Settings()
    assert s.api_base.startswith("https://")
    assert s.poll_notifications_seconds > 0


def test_pkce_pair_unique() -> None:
    from gitget.auth.oauth import _pkce_pair

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

    from gitget.auth.github_app import make_jwt

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

    from gitget.api.services.secrets import encrypt_secret

    sk = public.PrivateKey.generate()
    pk_b64 = sk.public_key.encode(encoder=encoding.Base64Encoder).decode()
    enc = encrypt_secret(pk_b64, "hunter2")
    decrypted = public.SealedBox(sk).decrypt(base64.b64decode(enc))
    assert decrypted == b"hunter2"


def test_main_window_constructs(qtbot) -> None:
    """MainWindow constructs without crashing (no auth required)."""
    from gitget.config import Settings
    from gitget.ui.main_window import MainWindow

    w = MainWindow(Settings())
    qtbot.addWidget(w)
    assert "GitGet" in w.windowTitle()


def test_workspace_builds(qtbot) -> None:
    """Workspace.build wires all clients without running them."""
    from gitget.config import Settings
    from gitget.workspace import Workspace

    ws = Workspace.build(Settings())
    assert ws.rest is not None
    assert ws.graphql is not None
    assert ws.poller is not None


@pytest.mark.parametrize("mode_cls_path", [
    "gitget.ui.modes.triage.TriageMode",
    "gitget.ui.modes.investigation.InvestigationMode",
    "gitget.ui.modes.admin.AdminMode",
    "gitget.ui.modes.contents.ContentsMode",
    "gitget.ui.modes.search.SearchMode",
    "gitget.ui.modes.pulls.PullsMode",
])
def test_modes_construct(qtbot, mode_cls_path: str) -> None:
    import importlib

    from gitget.config import Settings
    from gitget.workspace import Workspace

    module_name, cls_name = mode_cls_path.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_name), cls_name)
    ws = Workspace.build(Settings())
    w = cls(ws)
    qtbot.addWidget(w)


def test_repo_picker_constructs(qtbot) -> None:
    from gitget.config import Settings
    from gitget.ui.repo_picker import RepoPicker
    from gitget.workspace import Workspace

    ws = Workspace.build(Settings())
    w = RepoPicker(ws)
    qtbot.addWidget(w)
