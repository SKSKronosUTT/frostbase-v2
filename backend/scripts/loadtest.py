"""Prueba de carga de ingesta IoT y dashboard (T4.12).

Crea camiones y dispositivos temporales vía API, envía lecturas concurrentes y
mide p50/p95/p99 de `/iot/readings` y `/dashboard/summary`.

Ejemplo:
    python -m scripts.loadtest --devices 50 --duration 60 --interval 2
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import uuid
from datetime import UTC, datetime

import httpx

READING_PATH = "/api/v1/iot/readings"
SUMMARY_PATH = "/api/v1/dashboard/summary"
LOGIN_PATH = "/api/v1/auth/login"


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga de ingesta FrostBase")
    parser.add_argument("--base-url", default="http://127.0.0.1:8050")
    parser.add_argument("--devices", type=int, default=10)
    parser.add_argument("--duration", type=int, default=30, help="Segundos")
    parser.add_argument(
        "--interval", type=float, default=2.0, help="Segundos entre lecturas"
    )
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-password", default=None)
    return parser.parse_args()


async def login(client: httpx.AsyncClient, user: str, password: str) -> str:
    response = await client.post(
        LOGIN_PATH, json={"identifier": user, "password": password}
    )
    response.raise_for_status()
    token = client.cookies.get("frostbase_token") or ""
    if token:
        client.headers["Authorization"] = f"Bearer {token}"
    return token


async def create_device(
    client: httpx.AsyncClient, csrf: str, plate: str
) -> tuple[str, str]:
    headers = {"X-CSRF-Token": csrf}
    truck = await client.post(
        "/api/v1/trucks",
        headers=headers,
        json={
            "brand": "LoadTest",
            "model": "Async",
            "year": 2024,
            "plate": plate,
            "status": "disponible",
        },
    )
    truck.raise_for_status()
    truck_id = truck.json()["id"]
    device_id = f"LOAD-{uuid.uuid4().hex[:10].upper()}"
    last_response = None
    for _ in range(6):
        device = await client.post(
            "/api/v1/devices",
            headers=headers,
            json={"device_id": device_id, "truck_id": truck_id},
        )
        if device.status_code < 400:
            return device_id, device.json()["device_key"]
        last_response = device
        await asyncio.sleep(0.2)
    raise RuntimeError(
        f"device {device_id} -> {last_response.status_code}: {last_response.text[:300]}"
    )


async def simulate_device(
    client: httpx.AsyncClient,
    device_id: str,
    device_key: str,
    interval: float,
    deadline: float,
    latencies: list[float],
    errors: list[str],
    start_offset: float = 0.0,
) -> None:
    sequence = 0
    if start_offset:
        await asyncio.sleep(start_offset)
    while time.monotonic() < deadline:
        sequence += 1
        started = time.perf_counter()
        try:
            response = await client.post(
                READING_PATH,
                headers={"X-Device-Id": device_id, "X-Device-Key": device_key},
                json={
                    "device_id": device_id,
                    "temperature": 2.5,
                    "humidity": 78.0,
                    "latitude": 32.51 + (sequence % 10) * 0.0001,
                    "longitude": -117.03 - (sequence % 10) * 0.0001,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            if response.status_code >= 400:
                errors.append(f"{response.status_code}: {response.text[:120]}")
            else:
                latencies.append((time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
        await asyncio.sleep(interval)


async def main_async(args: argparse.Namespace) -> int:
    import os

    password = args.admin_password or os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("Defina --admin-password o ADMIN_PASSWORD")

    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        await login(client, args.admin_user, password)
        csrf = client.cookies.get("frostbase_csrf") or ""
        run = uuid.uuid4().hex[:6].upper()
        devices = [
            await create_device(client, csrf, f"LOAD-{run}-{index + 1:03d}")
            for index in range(args.devices)
        ]

        latencies: list[float] = []
        errors: list[str] = []
        summary_latencies: list[float] = []
        deadline = time.monotonic() + args.duration

        async def dashboard_probe() -> None:
            while time.monotonic() < deadline:
                started = time.perf_counter()
                response = await client.get(SUMMARY_PATH)
                if response.status_code == 200:
                    summary_latencies.append((time.perf_counter() - started) * 1000)
                await asyncio.sleep(5)

        tasks = [
            asyncio.create_task(
                simulate_device(
                    client,
                    device_id,
                    key,
                    args.interval,
                    deadline,
                    latencies,
                    errors,
                    start_offset=index * (args.interval / max(1, args.devices)),
                )
            )
            for index, (device_id, key) in enumerate(devices)
        ]
        tasks.append(asyncio.create_task(dashboard_probe()))
        await asyncio.gather(*tasks)

    print("\n=== Resultado de carga ===")
    print(f"Dispositivos: {args.devices} · duración: {args.duration} s")
    print(f"Lecturas OK: {len(latencies)} · errores: {len(errors)}")
    if latencies:
        print(
            "Ingesta ms · "
            f"p50={statistics.median(latencies):.1f} "
            f"p95={percentile(latencies, 95):.1f} "
            f"p99={percentile(latencies, 99):.1f} "
            f"max={max(latencies):.1f}"
        )
    if summary_latencies:
        print(
            "Dashboard ms · "
            f"p50={statistics.median(summary_latencies):.1f} "
            f"p95={percentile(summary_latencies, 95):.1f}"
        )
    if errors:
        print("Primeros errores:")
        for message in errors[:5]:
            print(" -", message)
    return 0 if not errors else 1


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
