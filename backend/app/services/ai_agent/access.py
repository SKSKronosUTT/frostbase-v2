"""Control de origen para ``agent-read`` (B5 fase 1).

La allowlist es opcional. En Docker la IP de origen suele ser la puerta NAT, no
la del ESP32; use red de host o un proxy de confianza antes de activarla.
"""

from __future__ import annotations

import ipaddress

from fastapi import Request


def client_ip(request: Request, *, trust_forwarded_for: bool = False) -> str | None:
    """IP del cliente; ``X-Forwarded-For`` solo si se confía en el proxy."""
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            if candidate:
                return candidate
    if request.client and request.client.host:
        return request.client.host
    return None


def is_ip_allowed(client: str | None, allowed_ips: str) -> bool:
    """``True`` si no hay allowlist o si la IP cae en alguna red permitida."""
    if not allowed_ips.strip():
        return True
    if not client:
        return False
    try:
        address = ipaddress.ip_address(client)
    except ValueError:
        return False
    for item in allowed_ips.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError:
            return False
        if address in network:
            return True
    return False
