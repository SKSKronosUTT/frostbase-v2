"""Prueba de carga del portal del conductor (G8, RNF2: 999 usuarios).

Simula usuarios concurrentes reales del módulo de conductores: login con
contraseña temporal (o dada) y polling cada 5 s de ``/driver/dashboard``,
``/driver/trips/current`` y ``/driver/alerts`` (RNF3). Mide p50/p95/p99,
rendimiento y tasa de error por endpoint.

Prepara ``--drivers`` conductores con camión y ruta de hoy vía API y reparte
los ``--users`` entre ellos (varios usuarios comparten conductor: el sistema
no distingue dispositivo, solo sesión).

Importante: ejecute contra un stack de pruebas con los límites de login
elevados, porque cada usuario virtual inicia sesión:

    docker compose up -d --force-recreate app
      -e LOGIN_IP_RATE_LIMIT=99999 -e LOGIN_IDENTIFIER_RATE_LIMIT=99999

Ejemplo:
    python -m scripts.loadtest_portal --users 999 --ramp 120 --duration 60
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import uuid
from datetime import UTC

import httpx

PORTAL_PATHS = (
    "/api/v1/driver/dashboard",
    "/api/v1/driver/trips/current",
    "/api/v1/driver/alerts?page_size=10",
)
LOGIN_PATH = "/api/v1/auth/login"


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga del portal de conductores")
    parser.add_argument("--base-url", default="http://127.0.0.1:8050")
    parser.add_argument(
        "--users", type=int, default=999, help="Usuarios virtuales concurrentes"
    )
    parser.add_argument("--drivers", type=int, default=25, help="Conductores de prueba")
    parser.add_argument("--duration", type=int, default=60, help="Segundos de polling")
    parser.add_argument(
        "--ramp", type=float, default=120.0, help="Segundos para repartir los logins"
    )
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Segundos entre rondas de polling"
    )
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-password", default=None)
    return parser.parse_args()


async def bootstrap_drivers(
    client: httpx.AsyncClient, args: argparse.Namespace, csrf: str
) -> list[tuple[str, str]]:
    """Crea conductores con camión y ruta de hoy; devuelve (email, password)."""
    from datetime import datetime as dt

    weekday = dt.now(UTC).isoweekday() % 7
    headers = {"X-CSRF-Token": csrf}
    credentials: list[tuple[str, str]] = []
    run = uuid.uuid4().hex[:6]
    for index in range(args.drivers):
        plate = f"LOAD-{run}-{index + 1:03d}"
        truck = await client.post(
            "/api/v1/trucks",
            headers=headers,
            json={
                "brand": "LoadTest",
                "model": "Portal",
                "year": 2024,
                "plate": plate,
                "status": "disponible",
            },
        )
        truck.raise_for_status()
        truck_id = truck.json()["id"]

        email = f"carga.{run}.{index + 1:03d}@frostbase.local"
        driver: httpx.Response | None = None
        for attempt in range(3):
            driver = await client.post(
                "/api/v1/drivers",
                headers=headers,
                json={
                    "first_name": "Carga",
                    "last_name": f"Concurrente {index + 1}",
                    "email": email,
                    "phone": "6640000000",
                    "birthdate": "1990-01-01",
                    "truck_id": truck_id,
                },
            )
            if driver.status_code < 500:
                break
            await asyncio.sleep(0.5 * (attempt + 1))
        assert driver is not None
        if driver.status_code >= 400:
            raise RuntimeError(
                f"driver {email} -> {driver.status_code}: {driver.text[:300]}"
            )
        driver_id = driver.json()["id"]
        temp_password = driver.json()["temporary_password"]

        # Sesión aparte para el cambio forzado: no toca las cookies del admin.
        password = f"Carga{run}!{index + 1:03d}"
        async with httpx.AsyncClient(
            base_url=args.base_url, timeout=httpx.Timeout(30)
        ) as driver_client:
            login_response = await driver_client.post(
                LOGIN_PATH, json={"identifier": email, "password": temp_password}
            )
            login_response.raise_for_status()
            driver_csrf = login_response.cookies.get("frostbase_csrf") or ""
            change = await driver_client.post(
                "/api/v1/auth/change-password",
                headers={"X-CSRF-Token": driver_csrf},
                json={"current_password": temp_password, "new_password": password},
            )
            change.raise_for_status()
        credentials.append((email, password))

        route = await client.post(
            "/api/v1/routes",
            headers=headers,
            json={
                "description": f"Ruta carga {index + 1}",
                "status": "activa",
                "points": [
                    {
                        "name": "Punto 1",
                        "address": "Calle 1",
                        "latitude": 32.51,
                        "longitude": -117.02,
                    },
                    {
                        "name": "Punto 2",
                        "address": "Calle 2",
                        "latitude": 32.52,
                        "longitude": -117.03,
                    },
                ],
            },
        )
        route.raise_for_status()
        route_id = route.json()["id"]
        # Carrera read-your-writes: el commit de otro worker puede aterrizar
        # unos ms después de la respuesta; reintento breve en caso de 404.
        for attempt in range(3):
            assign = await client.put(
                f"/api/v1/routes/{route_id}/driver",
                headers=headers,
                json={"driver_id": driver_id, "weekdays": [weekday]},
            )
            if assign.status_code < 500 and assign.status_code != 404:
                break
            await asyncio.sleep(0.2 * (attempt + 1))
        assign.raise_for_status()
    return credentials


async def virtual_user(
    base_url: str,
    credential: tuple[str, str],
    deadline: float,
    interval: float,
    latencies: dict[str, list[float]],
    counters: dict[str, int],
    lock: asyncio.Lock,
    stagger: float,
) -> None:
    """Un usuario virtual: inicia sesión y hace polling hasta el deadline.

    Los fallos de transporte del login cuentan como ``login_fail`` (con un
    reintento) en lugar de tumbar la corrida completa.
    """
    await asyncio.sleep(stagger)
    timeout = httpx.Timeout(30)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        email, password = credential
        login = None
        for attempt in range(3):
            started = time.perf_counter()
            try:
                login = await client.post(
                    LOGIN_PATH, json={"identifier": email, "password": password}
                )
            except httpx.HTTPError:
                if attempt == 2:
                    async with lock:
                        counters["login_fail"] += 1
                    return
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            async with lock:
                latencies["login"].append((time.perf_counter() - started) * 1000)
                counters["login_ok"] += login.status_code == 200
                counters["login_fail"] += login.status_code != 200
            break
        if login is None or login.status_code != 200:
            return

        while time.monotonic() < deadline:
            for path in PORTAL_PATHS:
                label = path.split("?")[0].rsplit("/", 1)[-1]
                started = time.perf_counter()
                try:
                    response = await client.get(path)
                    elapsed = (time.perf_counter() - started) * 1000
                    async with lock:
                        latencies[label].append(elapsed)
                        key = (
                            f"{label}_ok"
                            if response.status_code == 200
                            else f"{label}_fail"
                        )
                        counters[key] = counters.get(key, 0) + 1
                except Exception:  # noqa: BLE001
                    async with lock:
                        counters[f"{label}_fail"] = counters.get(f"{label}_fail", 0) + 1
            await asyncio.sleep(interval)


async def main_async(args: argparse.Namespace) -> int:
    import os

    password = args.admin_password or os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("Defina --admin-password o ADMIN_PASSWORD")

    print(f"Preparando {args.drivers} conductores de prueba en {args.base_url} …")
    timeout = httpx.Timeout(30)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        login = await client.post(
            LOGIN_PATH, json={"identifier": args.admin_user, "password": password}
        )
        login.raise_for_status()
        csrf = login.cookies.get("frostbase_csrf") or ""
        credentials = await bootstrap_drivers(client, args, csrf)

    latencies: dict[str, list[float]] = {
        "login": [],
        "dashboard": [],
        "current": [],
        "alerts": [],
    }
    counters: dict[str, int] = {"login_ok": 0, "login_fail": 0}
    lock = asyncio.Lock()
    # Rampa: los logins se reparten a lo largo de --ramp segundos (no todos a
    # la vez; el proxy de Docker no tolera 999 conexiones nuevas simultáneas)
    # y el polling sigue hasta ramp + duration.
    deadline = time.monotonic() + args.ramp + args.duration

    print(
        f"Lanzando {args.users} usuarios virtuales "
        f"(rampa {args.ramp:.0f} s, polling {args.duration} s, "
        f"cada {args.interval} s) …"
    )
    started_at = time.monotonic()
    tasks = [
        asyncio.create_task(
            virtual_user(
                args.base_url,
                credentials[index % len(credentials)],
                deadline,
                args.interval,
                latencies,
                counters,
                lock,
                stagger=(args.ramp * index) / max(1, args.users),
            )
        )
        for index in range(args.users)
    ]
    await asyncio.gather(*tasks)
    elapsed = time.monotonic() - started_at

    print("\n=== Resultado de carga del portal (RNF2) ===")
    print(f"Usuarios virtuales: {args.users} · duración: {elapsed:.0f} s")
    for label, values in latencies.items():
        if not values:
            continue
        ok = counters.get(f"{label}_ok", 0)
        fail = counters.get(f"{label}_fail", 0)
        total = ok + fail
        print(
            f"{label:<10} · ok={ok} fail={fail} "
            f"({(100 * fail / total):.1f}% error) · "
            f"p50={statistics.median(values):.1f} ms "
            f"p95={percentile(values, 95):.1f} ms "
            f"p99={percentile(values, 99):.1f} ms "
            f"max={max(values):.1f} ms"
        )
    total_fail = sum(value for key, value in counters.items() if key.endswith("_fail"))
    total_ok = sum(value for key, value in counters.items() if key.endswith("_ok"))
    rate = total_ok / elapsed if elapsed else 0
    print(f"Total: {total_ok} OK · {total_fail} fallos · {rate:.1f} req/s efectivas")
    return 0 if total_fail == 0 else 1


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
