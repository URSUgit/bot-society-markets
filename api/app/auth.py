from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

PBKDF2_ITERATIONS = 390000


@dataclass(slots=True)
class SessionToken:
    raw_token: str
    token_hash: str


class AuthManager:
    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

    def verify_password(self, password: str, password_hash: str | None) -> bool:
        if not password_hash:
            return False
        try:
            algorithm, iterations_text, salt_hex, digest_hex = password_hash.split("$", 3)
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)

    def new_session_token(self) -> SessionToken:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return SessionToken(raw_token=raw_token, token_hash=token_hash)

    def hash_session_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
