"""Rate limiting por ventana deslizante con backend memory o redis."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings

logger = logging.getLogger("frostbase.ratelimit")

KEY_PREFIX = "frostbase:rl:"

# Si Redis falla, se usa este backend para no tumbar la autenticación.
_fallback_backend: "MemoryBackend | None" = None


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_after: int


class MemoryBackend:
    """Ventana deslizante en memoria del proceso."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.monotonic()
        with self._lock:
            events = self._events.setdefault(key, deque())
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()

            allowed = len(events) < limit
            if allowed:
                events.append(now)

            remaining = max(0, limit - len(events))
            if allowed:
                retry_after = 0
                oldest = events[0] if events else now
                reset_after = max(1, int(oldest + window_seconds - now) + 1)
            else:
                retry_after = max(1, int(events[0] + window_seconds - now) + 1)
                reset_after = retry_after

            if not events:
                self._events.pop(key, None)

        return RateLimitDecision(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            retry_after=retry_after,
            reset_after=reset_after,
        )

    def reset(self, prefix: str | None = None) -> None:
        with self._lock:
            if prefix is None:
                self._events.clear()
                return
            for key in [item for item in self._events if item.startswith(prefix)]:
                self._events.pop(key, None)


_REDIS_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)

if count < limit then
  redis.call('ZADD', key, now, member)
  redis.call('PEXPIRE', key, window)
  local reset = window
  if count > 0 then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    reset = tonumber(oldest[2]) + window - now
  end
  return {1, limit - count - 1, math.ceil(reset / 1000)}
end

local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local retry = math.ceil((tonumber(oldest[2]) + window - now) / 1000)
return {0, 0, retry}
"""


class RedisBackend:
    """Ventana deslizante compartida entre workers mediante sorted sets."""

    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        self._script = self._client.register_script(_REDIS_LUA)

    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        global _fallback_backend
        now_ms = int(time.time() * 1000)
        window_ms = int(window_seconds * 1000)
        member = f"{now_ms}-{uuid.uuid4().hex}"
        try:
            allowed, remaining, reset = self._script(
                keys=[key],
                args=[now_ms, window_ms, limit, member],
            )
        except Exception:
            logger.exception("Redis no disponible; se usa rate limit en memoria")
            if _fallback_backend is None:
                _fallback_backend = MemoryBackend()
            return _fallback_backend.hit(key, limit, window_seconds)

        allowed_bool = bool(int(allowed))
        retry_after = 0 if allowed_bool else int(reset)
        return RateLimitDecision(
            allowed=allowed_bool,
            limit=limit,
            remaining=int(remaining),
            retry_after=retry_after,
            reset_after=int(reset),
        )

    def reset(self, prefix: str | None = None) -> None:
        pattern = f"{prefix or KEY_PREFIX}*"
        try:
            for key in self._client.scan_iter(match=pattern, count=500):
                self._client.delete(key)
        except Exception:
            logger.exception("No se pudieron limpiar las claves de rate limit en Redis")


_backend: MemoryBackend | RedisBackend | None = None
_backend_lock = threading.Lock()


def get_backend() -> MemoryBackend | RedisBackend:
    global _backend
    if _backend is not None:
        return _backend

    with _backend_lock:
        if _backend is None:
            if settings.rate_limit_backend == "redis" and settings.redis_url:
                try:
                    _backend = RedisBackend(settings.redis_url)
                except Exception:
                    logger.exception(
                        "No se pudo inicializar Redis; se usa rate limit en memoria"
                    )
                    _backend = MemoryBackend()
            else:
                _backend = MemoryBackend()
    return _backend


def reset_rate_limits() -> None:
    """Limpia los contadores (útil en tests y tareas de mantenimiento)."""
    get_backend().reset(KEY_PREFIX)


def client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class RateLimit:
    """Aplica una ventana deslizante.

    ``key_fn`` recibe la petición y devuelve la parte variable de la clave
    (por defecto, la IP del cliente). ``extra`` permite añadir un identificador
    adicional, por ejemplo el usuario o el ``device_id``.
    """

    def __init__(
        self,
        scope: str,
        limit: int,
        window_seconds: int,
        key_fn: Callable[[Request], str] | None = None,
    ) -> None:
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds
        self._key_fn = key_fn or client_ip

    def key(self, request: Request, extra: str | None = None) -> str:
        base = self._key_fn(request)
        suffix = f":{extra}" if extra else ""
        return f"{KEY_PREFIX}{self.scope}:{base}{suffix}"

    def hit(
        self, request: Request, response: Response | None = None, extra: str | None = None
    ) -> RateLimitDecision:
        decision = get_backend().hit(
            self.key(request, extra), self.limit, self.window_seconds
        )
        if response is not None:
            response.headers["X-RateLimit-Limit"] = str(self.limit)
            response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
            response.headers["X-RateLimit-Reset"] = str(decision.reset_after)
            if not decision.allowed:
                response.headers["Retry-After"] = str(decision.retry_after)
        return decision

    def check(
        self, request: Request, response: Response | None = None, extra: str | None = None
    ) -> RateLimitDecision:
        decision = self.hit(request, response, extra)
        if decision.allowed:
            return decision

        headers = {
            "Retry-After": str(decision.retry_after),
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
            "X-RateLimit-Reset": str(decision.reset_after),
        }
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas peticiones. Inténtalo de nuevo más tarde.",
            headers=headers,
        )

    def __call__(self, request: Request, response: Response) -> None:
        self.check(request, response)
