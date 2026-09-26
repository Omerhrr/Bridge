"""Symmetric encryption for secrets stored in the database (e.g. database
connection strings of knowledge sources). The key is derived from SECRET_KEY,
so rotating SECRET_KEY makes stored secrets unreadable (sources must then be
re-entered)."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"bridge-secrets:{settings.secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Stored secret can no longer be decrypted (SECRET_KEY changed?)") from exc
