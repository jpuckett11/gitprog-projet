"""HMAC-SHA256 verification of GitHub webhook payloads.

GitHub signs each webhook body with the shared secret. The signature is sent in
the `X-Hub-Signature-256` header as `sha256=<hex digest>`. We compare with
hmac.compare_digest to avoid timing leaks.
"""

from __future__ import annotations

import hashlib
import hmac


def expected_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify(secret: str, body: bytes, header: str | None) -> bool:
    if not header:
        return False
    return hmac.compare_digest(header, expected_signature(secret, body))
