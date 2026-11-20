"""Lanza N peticiones contra FrostBase y reporta la distribución de estados.

Ejemplos:
    python -m scripts.loadcheck --path /api/v1/auth/login \
        --json '{"identifier":"admin","password":"..."}' --count 20

    python -m scripts.loadcheck --path /api/v1/iot/readings --method POST \
        --json '{"device_id":"ESP32-FROST-001","temperature":-2,"humidity":80}' \
        --header "X-Device-Key: <clave>" --count 200 --concurrency 20

No está pensado para pruebas de carga sostenida; para eso use
``scripts/loadtest.py`` (Fase 4). El objetivo es verificar que el rate limit
devuelve 429 y que los códigos son los esperados.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8050")
    parser.add_argument("--path", default="/api/v1/auth/login")
    parser.add_argument("--method", default="POST")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--json", dest="json_body", default=None)
    parser.add_argument("--json-file", type=Path, default=None)
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        metavar="CLAVE:VALOR",
        help="Cabecera adicional (repetible).",
    )
    return parser


def parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    for item in values:
        if ":" not in item:
            raise SystemExit(f"Cabecera inválida: {item!r}. Use CLAVE:VALOR.")
        key, value = item.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> int:
    args = build_parser().parse_args()
    if args.count < 1:
        raise SystemExit("--count debe ser >= 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency debe ser >= 1")

    body = None
    if args.json_body:
        body = json.loads(args.json_body)
    elif args.json_file:
        body = json.loads(args.json_file.read_text(encoding="utf-8"))

    headers = parse_headers(args.header)
    url = f"{args.base_url.rstrip('/')}/{args.path.lstrip('/')}"
    codes: Counter[int] = Counter()
    latencies: list[float] = []

    with httpx.Client(timeout=args.timeout) as client:

        def send(_: int) -> tuple[int, float]:
            started = time.perf_counter()
            try:
                response = client.request(
                    args.method.upper(), url, json=body, headers=headers
                )
                return response.status_code, (time.perf_counter() - started) * 1000
            except httpx.HTTPError as exc:
                print(f"[ERROR] {exc}", file=sys.stderr)
                return 0, (time.perf_counter() - started) * 1000

        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for status_code, elapsed_ms in pool.map(send, range(args.count)):
                codes[status_code] += 1
                latencies.append(elapsed_ms)

    print(f"URL: {args.method.upper()} {url}")
    print(f"Peticiones: {args.count} · concurrencia: {args.concurrency}")
    print("Distribución de códigos:")
    for code, count in sorted(codes.items()):
        label = "ERROR DE RED" if code == 0 else str(code)
        print(f"  {label}: {count}")

    if latencies:
        print("Latencia (ms):")
        print(f"  media: {statistics.mean(latencies):.1f}")
        print(f"  p50:   {statistics.median(latencies):.1f}")
        print(f"  p95:   {percentile(latencies, 0.95):.1f}")
        print(f"  máx:   {max(latencies):.1f}")

    return 1 if codes.get(0, 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
