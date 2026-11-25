"""Diagnóstico rápido del asistente tras cambiar de red (desarrollo).

Uso desde la raíz del repositorio (Windows):

    .\\tasks.ps1 net-check
    .\\tasks.ps1 net-check -- --host-ip 192.168.1.45

O directamente desde ``backend/`` con el entorno del proyecto:

    python -m scripts.network_check
    python -m scripts.network_check --no-prompt
    python -m scripts.network_check --no-token

El script no modifica nada: detecta la IP local, compara la configuración,
prueba backend/ESP32/agent-read y muestra las líneas de ``.env`` y el prompt
listo para pegar en ESP-Claw.
"""

from __future__ import annotations

import argparse
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from scripts.runtime import configure_stdio, load_project_env

DEFAULT_PORT = 8050


@dataclass
class Probe:
    ok: bool
    detail: str
    latency_ms: float = 0.0

    def render(self) -> str:
        state = "OK   " if self.ok else "FALLO"
        latency = f" · {self.latency_ms:.0f} ms" if self.latency_ms else ""
        return f"{state} · {self.detail}{latency}"


def detect_local_ip() -> str | None:
    """IP de la interfaz con ruta por defecto (sin depender de servicios)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()
    if address.startswith(("127.", "169.254.")):
        return None
    return address


def backend_host_port(url: str, fallback_host: str | None) -> tuple[str, int]:
    parsed = urlparse(url or "")
    host = parsed.hostname or fallback_host or "127.0.0.1"
    return host, parsed.port or DEFAULT_PORT


def suggested_hosts(current: str, host_ip: str) -> str:
    items = [item.strip() for item in (current or "").split(",") if item.strip()]
    items = [item for item in ("localhost", "127.0.0.1") if item not in items] + items
    if host_ip not in items:
        items.append(host_ip)
    return ",".join(items)


def _request(url: str, *, timeout: float, headers: dict | None = None) -> tuple:
    started = time.perf_counter()
    try:
        response = httpx.get(
            url,
            timeout=timeout,
            headers=headers or {},
            follow_redirects=False,
        )
        elapsed = (time.perf_counter() - started) * 1000
        return response, None, elapsed
    except httpx.HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return None, type(exc).__name__, elapsed


def probe_health(url: str, timeout: float) -> Probe:
    response, error, elapsed = _request(url, timeout=timeout)
    if response is None:
        return Probe(False, error or "error de red", elapsed)
    if response.status_code == 400:
        return Probe(False, "HTTP 400 · revise ALLOWED_HOSTS", elapsed)
    return Probe(response.status_code < 400, f"HTTP {response.status_code}", elapsed)


def probe_agent(url: str, timeout: float) -> Probe:
    if not url:
        return Probe(False, "AI_AGENT_URL vacío")
    target = f"{url.rstrip('/')}/api/status"
    response, error, elapsed = _request(target, timeout=timeout)
    if response is None:
        return Probe(False, error or "error de red", elapsed)
    if response.status_code >= 400:
        return Probe(
            False, f"HTTP {response.status_code} · revise AI_AGENT_URL", elapsed
        )
    try:
        payload = response.json()
    except ValueError:
        return Probe(False, "respuesta no JSON", elapsed)
    boot_id = str(payload.get("boot_id") or "sin boot_id")[:12]
    wifi = payload.get("wifi_connected")
    return Probe(True, f"boot_id={boot_id} · wifi={wifi}", elapsed)


def probe_agent_read(url: str, token: str, timeout: float) -> Probe:
    if not token:
        return Probe(False, "AI_AGENT_READ_TOKEN vacío")
    target = f"{url.rstrip('/')}/api/v1/agent-read/fleet-summary"
    response, error, elapsed = _request(
        target,
        timeout=timeout,
        headers={"Authorization": f"Bearer {token}"},
    )
    if response is None:
        return Probe(False, error or "error de red", elapsed)
    if response.status_code == 401:
        return Probe(False, "HTTP 401 · token inválido", elapsed)
    if response.status_code == 404:
        return Probe(False, "HTTP 404 · asistente o token deshabilitado", elapsed)
    return Probe(response.status_code == 200, f"HTTP {response.status_code}", elapsed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnóstico de red del asistente FrostBase"
    )
    parser.add_argument(
        "--host-ip",
        default=None,
        help="IP de la LAN de este equipo (si la detección automática falla)",
    )
    parser.add_argument(
        "--backend-url",
        default=None,
        help="URL del backend para el prompt (por defecto, IP detectada:8050)",
    )
    parser.add_argument(
        "--agent-url",
        default=None,
        help="IP nueva del ESP32 para la sugerencia de AI_AGENT_URL",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Timeout de cada comprobación en segundos (default: 3)",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="No imprimir el prompt del agente",
    )
    parser.add_argument(
        "--no-token",
        action="store_true",
        help="Sustituir el token real por un marcador en el prompt",
    )
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    load_project_env()
    from app.core.config import settings
    from scripts.agent_prompt import build_prompt

    args = parse_args()
    host_ip = args.host_ip or detect_local_ip()
    backend_host, port = backend_host_port(settings.ai_backend_url, host_ip)
    suggested_backend = args.backend_url or (
        f"http://{host_ip}:{port}" if host_ip else settings.ai_backend_url
    )
    suggested_agent = args.agent_url or settings.ai_agent_url
    allowed = suggested_hosts(settings.allowed_hosts, host_ip) if host_ip else ""

    print("\n=== FrostBase · diagnóstico de red del asistente ===\n")
    print(f"IP local detectada : {host_ip or 'no detectada'}")
    if not host_ip:
        print("  Repita con --host-ip <IP_DE_LA_LAN> si hay VPN o varias interfaces.")
    print("\nConfiguración actual (.env):")
    print(f"  AI_AGENT_URL     : {settings.ai_agent_url or '(vacío)'}")
    print(f"  AI_BACKEND_URL   : {settings.ai_backend_url or '(vacío)'}")
    print(f"  ALLOWED_HOSTS    : {settings.allowed_hosts or '(vacío)'}")
    token_state = (
        f"configurado ({len(settings.ai_agent_read_token)} caracteres)"
        if settings.ai_agent_read_token
        else "vacío"
    )
    print(f"  Token agent-read : {token_state}")

    local_backend = f"http://127.0.0.1:{port}"
    lan_backend = f"http://{host_ip}:{port}" if host_ip else ""

    print("\nComprobaciones:")
    print(
        "  Backend local    : "
        + probe_health(f"{local_backend}/health/ready", args.timeout).render()
    )
    if lan_backend:
        print(
            "  Backend por LAN  : "
            + probe_health(f"{lan_backend}/health/ready", args.timeout).render()
        )
    print(
        "  ESP32 /api/status: "
        + probe_agent(settings.ai_agent_url, args.timeout).render()
    )
    print(
        "  agent-read       : "
        + probe_agent_read(
            local_backend, settings.ai_agent_read_token, args.timeout
        ).render()
    )

    print("\nSugerencia para .env:")
    if suggested_agent:
        print(f"  AI_AGENT_URL={suggested_agent}")
    else:
        print("  AI_AGENT_URL=http://<IP_NUEVA_ESP32>")
    print(f"  AI_BACKEND_URL={suggested_backend}")
    if allowed:
        print(f"  ALLOWED_HOSTS={allowed}")

    warnings: list[str] = []
    if host_ip and backend_host != host_ip:
        warnings.append(
            f"AI_BACKEND_URL apunta a {backend_host}, no a la IP detectada ({host_ip})."
        )
    if host_ip and host_ip not in settings.allowed_host_list:
        warnings.append(f"ALLOWED_HOSTS no incluye {host_ip}.")
    if not settings.ai_agent_read_token:
        warnings.append("AI_AGENT_READ_TOKEN está vacío: el agente no podrá leer.")
    if not settings.ai_agent_enabled:
        warnings.append("AI_AGENT_ENABLED=false: el asistente está deshabilitado.")
    if warnings:
        print("\nAvisos:")
        for warning in warnings:
            print(f"  - {warning}")

    print("\nSiguiente:")
    print("  1) Copie las líneas sugeridas en .env (si cambiaron).")
    print("  2) docker compose up -d --force-recreate app watcher")
    print("  3) Vuelva a ejecutar este script y pegue el prompt en ESP-Claw.")
    print("  4) Pruebe chat, alertas, historial y reinicio del ESP32.")

    if not args.no_prompt:
        prompt_backend = suggested_backend or "http://<IP_DEL_BACKEND>:8050"
        prompt = build_prompt(
            backend_url=prompt_backend,
            token="" if args.no_token else settings.ai_agent_read_token,
        )
        print("\n=== Prompt para el agente (copiar en ESP-Claw) ===\n")
        print(prompt)
        print("=== Fin del prompt ===")
        if not args.no_token and settings.ai_agent_read_token:
            print(
                "El prompt contiene el token real: no lo comparta ni lo pegue en chats."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
