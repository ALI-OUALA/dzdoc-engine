"""API-key and webhook cryptography using standard-library primitives."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_api_key() -> tuple[str, str, str]:
    prefix = secrets.token_hex(6)
    token = f"dz_live_{prefix}.{secrets.token_urlsafe(32)}"
    return token, prefix, hash_secret(token)


def hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(secret.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt-v1${salt.hex()}${digest.hex()}"


def verify_secret(secret: str, encoded: str) -> bool:
    try:
        version, salt_hex, expected_hex = encoded.split("$", 2)
        if version != "scrypt-v1":
            return False
        actual = hashlib.scrypt(
            secret.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def webhook_signature(secret: str, timestamp: int, body: bytes) -> str:
    payload = str(timestamp).encode() + b"." + body
    return "v1=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
