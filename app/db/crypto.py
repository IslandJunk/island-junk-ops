"""Transparent at-rest encryption for sensitive columns (WS4: QBO OAuth tokens).

`EncryptedText` is a SQLAlchemy type that Fernet-encrypts on write and decrypts on read, so model
code and queries are unchanged. Keyless → plaintext (dev fallback). Decryption tolerates a legacy
plaintext value (a row written before the key existed), so enabling encryption never breaks an
existing connection — that row upgrades to ciphertext on its next write.
"""
from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


def _fernet():
    key = settings.qbo_token_key
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


class EncryptedText(TypeDecorator):
    """A Text column encrypted at rest with Fernet when `qbo_token_key` is set (else plaintext)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        f = _fernet()
        return f.encrypt(value.encode()).decode() if f else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        f = _fernet()
        if f is None:
            return value
        from cryptography.fernet import InvalidToken
        try:
            return f.decrypt(value.encode()).decode()
        except InvalidToken:
            return value   # legacy plaintext (pre-encryption) — hand it back as-is
