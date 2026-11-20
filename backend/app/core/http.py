"""Cliente HTTP compartido y circuit breaker para servicios externos."""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger("frostbase.http")

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=3.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
        )
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class CircuitBreaker:
    """Circuit breaker simple en memoria.

    Tras ``failure_threshold`` fallos consecutivos abre el circuito durante
    ``recovery_seconds``. Mientras está abierto no se llama al proveedor.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failures = 0
        self._opened_until = 0.0
        self._state = "closed"

    @property
    def state(self) -> str:
        return self._state

    def allow(self) -> bool:
        if self._state == "open":
            if time.monotonic() < self._opened_until:
                return False
            self._state = "half-open"
            logger.info("Circuit breaker '%s' en half-open", self.name)
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_until = time.monotonic() + self.recovery_seconds
            logger.warning(
                "Circuit breaker '%s' abierto durante %.0f s",
                self.name,
                self.recovery_seconds,
            )
