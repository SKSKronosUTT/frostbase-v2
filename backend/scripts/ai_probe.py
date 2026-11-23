"""Sondeo del agente ESP-Claw alojado en el ESP32-S3 (Fase A0).

Descubre el contrato real del agente antes de implementar la integración:

- Comprueba alcanzabilidad del host y puerto.
- Prueba rutas HTTP candidatas y registra códigos, cabeceras y fragmentos.
- Intenta el WebSocket del Web Chat con varios formatos de mensaje y captura
  los frames de respuesta.

Solo se permiten hosts de red privada (por defecto); use ``--allow-public``
de forma consciente. No escribe nada en el repositorio salvo que se indique
``--output``.

Uso (desde backend/):
    python -m scripts.ai_probe --mode both
    python -m scripts.ai_probe --mode http
    python -m scripts.ai_probe --mode ws --message "¿Cuántas alertas activas hay?"
    python -m scripts.ai_probe --output ..\\docs\\ai\\evidencia-a0.json --json

Desde Docker (mismo resultado que tendrá el backend):
    docker compose exec app python -m scripts.ai_probe --mode both
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
import websockets

DEFAULT_URL = "http://192.168.4.1"
DEFAULT_WS_PATH = "/api/webim/ws"
DEFAULT_MESSAGE = "¿Cuántas alertas activas hay y qué camiones están fuera de rango?"
DEFAULT_HTTP_PATHS = (
    "/",
    "/api/status",
    "/api/config",
    "/api/webim/ws",
    "/api/chat",
    "/chat",
    "/v1/models",
)
# Plantillas de payload para el WebSocket; ``{message}`` se sustituye.
DEFAULT_WS_PAYLOADS = (
    "{message}",
    '{"message": "{message}"}',
    '{"type": "text", "text": "{message}"}',
    '{"type": "chat", "content": "{message}"}',
    '{"role": "user", "content": "{message}"}',
)
BODY_PREVIEW_CHARS = 300
FRAME_PREVIEW_CHARS = 800
MAX_FRAMES = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sondeo del agente ESP-Claw")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL base del agente")
    parser.add_argument(
        "--mode", choices=("http", "ws", "both"), default="both", help="Qué sondear"
    )
    parser.add_argument("--ws-path", default=DEFAULT_WS_PATH, help="Ruta WebSocket")
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Ruta HTTP candidata (repetible; reemplaza la lista por defecto)",
    )
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="Mensaje de prueba")
    parser.add_argument(
        "--payload",
        action="append",
        dest="payloads",
        help=(
            "Plantilla de payload WS con {message} (repetible; reemplaza las "
            "plantillas por defecto)"
        ),
    )
    parser.add_argument("--token", default=None, help="Bearer opcional")
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="Timeout HTTP (segundos)"
    )
    parser.add_argument(
        "--ws-timeout",
        type=float,
        default=25.0,
        help="Espera máxima de respuesta WS (segundos)",
    )
    parser.add_argument(
        "--ws-idle",
        type=float,
        default=4.0,
        help="Silencio tras el que se considera completa la respuesta WS",
    )
    parser.add_argument("--json", action="store_true", help="Imprimir solo JSON")
    parser.add_argument("--output", type=Path, default=None, help="Guardar evidencia")
    parser.add_argument(
        "--allow-public",
        action="store_true",
        help="Permitir hosts fuera de red privada (no recomendado)",
    )
    return parser.parse_args()


def _assert_private_host(host: str, *, allow_public: bool) -> None:
    if host in {"localhost"} or host.endswith(".local"):
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if allow_public:
            return
        raise SystemExit(
            f"Host '{host}' no es una IP privada. Use --allow-public solo si "
            "el agente está en una red de confianza."
        ) from None
    if address.is_private or address.is_loopback:
        return
    if allow_public:
        print(
            f"[AVISO] Host público {host}; el sondeo revelará el contrato del "
            "agente. Continúe solo si es su propio dispositivo.",
            file=sys.stderr,
        )
        return
    raise SystemExit(f"Host {host} no es privado. Use --allow-public para forzarlo.")


def _tcp_check(host: str, port: int, timeout: float) -> dict:
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = (time.perf_counter() - started) * 1000
            return {"reachable": True, "port": port, "latency_ms": round(elapsed, 1)}
    except OSError as exc:
        return {"reachable": False, "port": port, "error": str(exc)}


def _payload_for(template: str, message: str) -> str:
    if template == "{message}":
        return message
    escaped = json.dumps(message)[1:-1]
    return template.replace("{message}", escaped)


def probe_http(
    client: httpx.Client, base_url: str, paths: list[str], token: str | None
) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    results: list[dict] = []
    for path in paths:
        url = base_url.rstrip("/") + "/" + path.lstrip("/")
        started = time.perf_counter()
        entry: dict = {"path": path, "url": url}
        try:
            response = client.get(url, headers=headers)
            elapsed = (time.perf_counter() - started) * 1000
            entry.update(
                status=response.status_code,
                elapsed_ms=round(elapsed, 1),
                content_type=response.headers.get("content-type"),
                length=len(response.content),
                server=response.headers.get("server"),
                www_authenticate=response.headers.get("www-authenticate"),
                upgrade=response.headers.get("upgrade"),
                body_preview=response.text[:BODY_PREVIEW_CHARS].strip(),
            )
        except httpx.HTTPError as exc:
            entry.update(error=str(exc), elapsed_ms=None)
        results.append(entry)
    return results


async def _ws_attempt(
    ws_url: str,
    payload: str,
    token: str | None,
    timeout: float,
    idle: float,
) -> dict:
    entry: dict = {"payload": payload[:200], "frames": []}
    headers = {"Authorization": f"Bearer {token}"} if token else None
    try:
        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            open_timeout=timeout,
            close_timeout=2,
            max_size=1 << 20,
        ) as socket_ws:
            await socket_ws.send(payload)
            deadline = time.monotonic() + timeout
            while len(entry["frames"]) < MAX_FRAMES and time.monotonic() < deadline:
                remaining = min(idle, deadline - time.monotonic())
                if remaining <= 0:
                    break
                try:
                    frame = await asyncio.wait_for(socket_ws.recv(), timeout=remaining)
                except TimeoutError:
                    break
                entry["frames"].append(str(frame)[:FRAME_PREVIEW_CHARS])
        entry["connected"] = True
    except Exception as exc:  # noqa: BLE001 - diagnóstico: se reporta cualquier fallo
        entry.update(connected=False, error=f"{type(exc).__name__}: {exc}")
    return entry


async def probe_ws(
    ws_url: str,
    payloads: list[str],
    token: str | None,
    timeout: float,
    idle: float,
) -> dict:
    return {
        "url": ws_url,
        "attempts": [
            await _ws_attempt(ws_url, payload, token, timeout, idle)
            for payload in payloads
        ],
    }


def _print_human(report: dict) -> None:
    print("\n=== Sondeo del agente ESP-Claw ===")
    print(f"URL base: {report['base_url']}")
    print(f"Fecha: {report['generated_at']}")
    tcp = report["tcp"]
    if tcp["reachable"]:
        print(f"TCP {tcp['port']}: OK ({tcp['latency_ms']} ms)")
    else:
        print(f"TCP {tcp['port']}: INALCANZABLE — {tcp.get('error')}")
        print("Conecte el equipo al AP del ESP32 (esp-claw-XXXXXX) y repita el sondeo.")

    if report.get("http"):
        print("\n--- HTTP ---")
        for item in report["http"]:
            if "status" in item:
                print(
                    f"{item['path']:<20} {item['status']} "
                    f"{item.get('content_type') or '-'} "
                    f"{item.get('length', 0)} B {item.get('elapsed_ms')} ms"
                )
                if item.get("body_preview"):
                    print(f"    {item['body_preview'][:160]!r}")
            else:
                print(f"{item['path']:<20} ERROR {item.get('error')}")

    if report.get("ws"):
        print(f"\n--- WebSocket {report['ws']['url']} ---")
        for attempt in report["ws"]["attempts"]:
            status = "conectado" if attempt.get("connected") else "fallo"
            print(f"· payload {attempt['payload'][:60]!r}: {status}")
            if attempt.get("error"):
                print(f"    {attempt['error']}")
            for frame in attempt.get("frames", []):
                print(f"    <- {frame[:200]}")

    print("\nSiguiente paso: copie los hallazgos a docs/AI-AGENT.md (A0).")


async def main_async(args: argparse.Namespace) -> int:
    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https", "ws", "wss"}:
        raise SystemExit(f"Esquema no soportado en --url: {parsed.scheme}")
    host = parsed.hostname or ""
    if not host:
        raise SystemExit("--url debe incluir un host")
    _assert_private_host(host, allow_public=args.allow_public)

    http_scheme = "https" if parsed.scheme in {"https", "wss"} else "http"
    port = parsed.port or (443 if http_scheme == "https" else 80)
    base_url = f"{http_scheme}://{host}" + (f":{port}" if parsed.port else "")

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "host": host,
        "tcp": _tcp_check(host, port, args.timeout),
    }
    payloads = [
        _payload_for(template, args.message)
        for template in (args.payloads or DEFAULT_WS_PAYLOADS)
    ]
    ws_scheme = "wss" if http_scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{host}" + (f":{port}" if parsed.port else "")
    ws_url += "/" + args.ws_path.lstrip("/")

    if args.mode in {"http", "both"} and report["tcp"]["reachable"]:
        paths = args.paths or list(DEFAULT_HTTP_PATHS)
        with httpx.Client(timeout=args.timeout, follow_redirects=False) as client:
            report["http"] = probe_http(client, base_url, paths, args.token)

    if args.mode in {"ws", "both"} and report["tcp"]["reachable"]:
        report["ws"] = await probe_ws(
            ws_url, payloads, args.token, args.ws_timeout, args.ws_idle
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not args.json:
            print(f"\nEvidencia guardada en {args.output}")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["tcp"]["reachable"] else 2


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
