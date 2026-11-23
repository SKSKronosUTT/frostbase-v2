"""Estado del agente con caché corta (no gasta LLM)."""

from __future__ import annotations

import threading
import time
from datetime import datetime

from app.core.config import settings
from app.services.ai_agent.client import AgentError, build_client
from app.utils.time import utcnow

_lock = threading.Lock()
_cache: dict = {}
_last_ok_at: datetime | None = None


def get_status() -> dict:
    global _last_ok_at

    if not settings.ai_agent_enabled:
        return {
            "enabled": False,
            "online": False,
            "latency_ms": None,
            "boot_id": None,
            "wifi_connected": None,
            "last_ok_at": None,
        }

    now = time.monotonic()
    ttl = max(1, settings.ai_agent_status_cache_seconds)
    with _lock:
        cached = _cache.get("payload")
        if cached is not None and now - _cache.get("at", 0.0) < ttl:
            return dict(cached)

    try:
        with build_client() as client:
            status = client.status(timeout=5.0)
        if status.online:
            _last_ok_at = utcnow()
        payload = {
            "enabled": True,
            "online": status.online,
            "latency_ms": round(status.latency_ms or 0.0, 1),
            "boot_id": status.boot_id,
            "wifi_connected": status.wifi_connected,
            "last_ok_at": _last_ok_at,
        }
    except AgentError:
        payload = {
            "enabled": True,
            "online": False,
            "latency_ms": None,
            "boot_id": None,
            "wifi_connected": None,
            "last_ok_at": _last_ok_at,
        }

    with _lock:
        _cache["payload"] = payload
        _cache["at"] = time.monotonic()
    return dict(payload)


def reset_status_cache() -> None:
    global _last_ok_at
    with _lock:
        _cache.clear()
        _last_ok_at = None
