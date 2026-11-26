"""Prueba de concurrencia del asistente IA (B7).

Comprueba el lock global: con varias peticiones simultáneas debe responder
**una sola** y el resto recibir 429 (agente ocupado), sin consumir cuota las
rechazadas.

Uso:
    python -m scripts.loadtest_ai --concurrency 3
    python -m scripts.loadtest_ai --concurrency 5 --message "Responde solo: X"

Consume una consulta de la cuota diaria. Ejecútelo contra el stack local.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time

import httpx

from scripts.runtime import configure_stdio, load_project_env

load_project_env()

LOGIN_PATH = "/api/v1/auth/login"
CHAT_PATH = "/api/v1/ai/chat"
USAGE_PATH = "/api/v1/ai/usage"


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concurrencia del asistente IA")
    parser.add_argument("--base-url", default="http://127.0.0.1:8050")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--message", default="Responde solo: LOADTEST-IA")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-password", default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args()


async def send_one(
    client: httpx.AsyncClient,
    *,
    csrf: str,
    message: str,
    gate: asyncio.Event,
) -> dict:
    await gate.wait()
    started = time.perf_counter()
    try:
        response = await client.post(
            CHAT_PATH,
            headers={"X-CSRF-Token": csrf},
            json={"message": message},
        )
        return {
            "status": response.status_code,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "detail": "",
        }
    except httpx.HTTPError as exc:
        return {
            "status": None,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "detail": type(exc).__name__,
        }


async def main_async(args: argparse.Namespace) -> int:
    if not 2 <= args.concurrency <= 5:
        raise SystemExit("--concurrency debe estar entre 2 y 5 (rate limit 6/min)")
    password = args.admin_password or os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("Defina --admin-password o ADMIN_PASSWORD")

    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=args.timeout
    ) as client:
        login = await client.post(
            LOGIN_PATH,
            json={"identifier": args.admin_user, "password": password},
        )
        if login.status_code != 200:
            print(f"[ERROR] Login {login.status_code}: {login.text[:200]}")
            return 1
        csrf = client.cookies.get("frostbase_csrf") or ""
        before = (await client.get(USAGE_PATH)).json()

        gate = asyncio.Event()
        tasks = [
            send_one(
                client,
                csrf=csrf,
                message=f"{args.message} #{index + 1}",
                gate=gate,
            )
            for index in range(args.concurrency)
        ]
        await asyncio.sleep(0.1)
        gate.set()
        results = await asyncio.gather(*tasks)
        after = (await client.get(USAGE_PATH)).json()

    statuses: dict[str, int] = {}
    for result in results:
        key = str(result["status"] if result["status"] is not None else "error")
        statuses[key] = statuses.get(key, 0) + 1
    latencies = [result["latency_ms"] for result in results]
    success_latencies = [
        result["latency_ms"] for result in results if result["status"] == 200
    ]

    print("\n=== Concurrencia del asistente IA ===")
    print(f"Peticiones: {args.concurrency}")
    print(f"Estados: {statuses}")
    print(
        f"Latencia p50/p95: {percentile(latencies, 50):.0f} / "
        f"{percentile(latencies, 95):.0f} ms"
    )
    if success_latencies:
        print(f"Respuesta exitosa: {statistics.mean(success_latencies):.0f} ms (media)")
    print(
        f"Cuota usada: {before.get('used')} → {after.get('used')} "
        f"(límite {after.get('limit')})"
    )

    expected_busy = args.concurrency - 1
    if statuses.get("200") == 1 and statuses.get("429") == expected_busy:
        print("\nOK: una respuesta y el resto 429 (lock global correcto).")
        return 0

    print(
        "\nFALLO: se esperaba 1×200 y "
        f"{expected_busy}×429. Revise agente, lock, cuota y rate limit."
    )
    return 1


def main() -> int:
    configure_stdio()
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
