from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
import time
from dataclasses import dataclass
from urllib.parse import quote

PBKDF2_ITERATIONS = 390000


@dataclass(slots=True)
class SessionToken:
    raw_token: str
    token_hash: str


@dataclass(slots=True)
class PasswordResetToken:
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

    def new_password_reset_token(self) -> PasswordResetToken:
        raw_token = secrets.token_urlsafe(48)
        token_hash = self.hash_password_reset_token(raw_token)
        return PasswordResetToken(raw_token=raw_token, token_hash=token_hash)

    def hash_password_reset_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def new_totp_secret(self, *, length_bytes: int = 20) -> str:
        # Authenticator apps accept Base32 without padding.
        return base64.b32encode(secrets.token_bytes(length_bytes)).decode("ascii").rstrip("=")

    def totp_provisioning_uri(self, *, secret: str, issuer: str, account_name: str) -> str:
        label = quote(f"{issuer}:{account_name}")
        issuer_query = quote(issuer)
        return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_query}&digits=6&period=30&algorithm=SHA1"

    def verify_totp_code(self, secret: str | None, code: str | None, *, window: int = 1, step_seconds: int = 30) -> bool:
        if not secret or not code:
            return False

        normalized_code = "".join(ch for ch in str(code) if ch.isdigit())
        if len(normalized_code) != 6:
            return False

        normalized_secret = secret.strip().replace(" ", "").upper()
        if not normalized_secret:
            return False

        padding = "=" * ((8 - (len(normalized_secret) % 8)) % 8)
        try:
            secret_bytes = base64.b32decode(normalized_secret + padding, casefold=True)
        except (ValueError, binascii.Error):
            return False

        counter = int(time.time() // step_seconds)
        for offset in range(-window, window + 1):
            candidate = self._hotp(secret_bytes, counter + offset)
            if hmac.compare_digest(candidate, normalized_code):
                return True
        return False

    @staticmethod
    def _hotp(secret: bytes, counter: int, *, digits: int = 6) -> str:
        counter_bytes = struct.pack(">Q", max(counter, 0))
        digest = hmac.new(secret, counter_bytes, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
        return str(truncated % (10**digits)).zfill(digits)
