"""PIN hashing. pbkdf2_sha256 is pure-python (no native build on 3.14)."""
from __future__ import annotations

from passlib.context import CryptContext

_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def normalize_pin(raw: str) -> str:
    """Digits only, max 4 — matches the prototype (`replace(/[^0-9]/g,'').slice(0,4)`)."""
    return "".join(c for c in raw if c.isdigit())[:4]


def hash_pin(pin: str) -> str:
    return _ctx.hash(normalize_pin(pin))


def verify_pin(pin: str, pin_hash: str) -> bool:
    return _ctx.verify(normalize_pin(pin), pin_hash)


# Owner Hub gate password (a real password, NOT digit-normalized like a PIN).
def hash_password(password: str) -> str:
    return _ctx.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _ctx.verify(password, password_hash)
