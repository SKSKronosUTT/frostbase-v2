import hashlib
import hmac
import secrets
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cachetools import TTLCache
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()

ALGORITHM = "HS256"

_DEVICE_CACHE_MAX = 4096
_DEVICE_CACHE_TTL_SECONDS = 300
_device_cache: TTLCache[str, int] = TTLCache(
    maxsize=_DEVICE_CACHE_MAX, ttl=_DEVICE_CACHE_TTL_SECONDS
)
_device_cache_lock = threading.Lock()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: str, expires_minutes: int | None = None, *, token_version: int = 1
) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "admin",
        "tv": token_version,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def generate_device_secret() -> str:
    return secrets.token_urlsafe(32)


def device_fingerprint(secret: str) -> str:
    """HMAC-SHA256 de la clave presentada con el pepper del servidor."""
    return hmac.new(
        settings.device_key_pepper.encode("utf-8"),
        secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_device_fingerprint(secret: str, expected: str) -> bool:
    return hmac.compare_digest(device_fingerprint(secret), expected)


def cache_device_fingerprint(secret: str, device_pk: int) -> None:
    with _device_cache_lock:
        _device_cache[device_fingerprint(secret)] = device_pk


def get_cached_device_id(secret: str) -> int | None:
    with _device_cache_lock:
        return _device_cache.get(device_fingerprint(secret))


def clear_device_cache() -> None:
    with _device_cache_lock:
        _device_cache.clear()


def hash_device_secret(secret: str) -> str:
    """Hash Argon2 para dispositivos legacy (key_scheme='argon2')."""
    return hash_password(secret)


def verify_device_secret(secret: str, hashed_secret: str) -> bool:
    return verify_password(secret, hashed_secret)
