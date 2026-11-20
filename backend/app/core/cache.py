"""Caché TTL intercambiable memory/redis para datos derivados."""

from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings

logger = logging.getLogger("frostbase.cache")

KEY_PREFIX = "frostbase:cache:"


class MemoryTTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + max(1, ttl_seconds), value)

    def delete(self, prefix: str) -> None:
        with self._lock:
            for key in [item for item in self._data if item.startswith(prefix)]:
                self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisTTLCache:
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        return value if isinstance(value, str) else None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._client.setex(key, max(1, ttl_seconds), value)

    def delete(self, prefix: str) -> None:
        for key in self._client.scan_iter(match=f"{prefix}*", count=500):
            self._client.delete(key)

    def clear(self) -> None:
        self.delete(KEY_PREFIX)


_cache: MemoryTTLCache | RedisTTLCache | None = None
_cache_lock = threading.Lock()


def get_cache() -> MemoryTTLCache | RedisTTLCache:
    global _cache
    if _cache is not None:
        return _cache
    with _cache_lock:
        if _cache is None:
            if settings.rate_limit_backend == "redis" and settings.redis_url:
                try:
                    _cache = RedisTTLCache(settings.redis_url)
                except Exception:
                    logger.exception(
                        "No se pudo inicializar Redis; se usa caché en memoria"
                    )
                    _cache = MemoryTTLCache()
            else:
                _cache = MemoryTTLCache()
    return _cache


def cache_get(key: str) -> str | None:
    try:
        return get_cache().get(f"{KEY_PREFIX}{key}")
    except Exception:
        logger.exception("Error leyendo la caché")
        return None


def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    try:
        get_cache().set(f"{KEY_PREFIX}{key}", value, ttl_seconds)
    except Exception:
        logger.exception("Error escribiendo en la caché")


def cache_delete(prefix: str) -> None:
    try:
        get_cache().delete(f"{KEY_PREFIX}{prefix}")
    except Exception:
        logger.exception("Error invalidando la caché")


def reset_cache() -> None:
    try:
        get_cache().clear()
    except Exception:
        logger.exception("Error limpiando la caché")
