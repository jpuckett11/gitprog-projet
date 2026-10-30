
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
