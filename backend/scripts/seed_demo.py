"""Seed de demostración idempotente de FrostBase.

Uso (desde backend/):
    python -m scripts.seed_demo [--reset] [--print-keys] [--trucks N] [--devices M]

- Ejecutarlo varias veces no duplica rutas, camiones ni dispositivos.
- Las claves solo se imprimen con ``--print-keys`` (o en la primera creación).
- ``--trucks``/``--devices`` generan datos extra para pruebas de carga.
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.core.security import device_fingerprint, generate_device_secret
from app.models.device import Device
from app.models.route import DeliveryPoint, Route
from app.models.truck import Truck
from app.services import routing, settings_service
from app.services.bootstrap import bootstrap_database, ensure_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("frostbase.seed")

POINTS = [
    ("Villa Fontana", "Blvd. Gustavo Díaz Ordaz, Tijuana", 32.5062, -116.9725),
    ("Zona Centro", "Av. Revolución, Tijuana", 32.5333, -117.0369),
    ("Playas de Tijuana", "Paseo Ensenada, Tijuana", 32.5346, -117.1217),
]

ROUTE_NAME = f"{POINTS[0][0]} - {POINTS[-1][0]}"

BASE_TRUCKS = [
    {
        "brand": "Freightliner",
        "model": "M2 106",
        "year": 2022,
        "plate": "ABC-123-A",
        "description": "Unidad de reparto refrigerado",
        "status": "en_ruta",
    },
    {
        "brand": "Isuzu",
        "model": "NPR",
        "year": 2021,
        "plate": "JKL-456-B",
        "description": "Unidad de apoyo",
        "status": "disponible",
    },
    {
        "brand": "Kenworth",
        "model": "T370",
        "year": 2023,
        "plate": "XYZ-789-C",
        "description": "Unidad en mantenimiento",
        "status": "mantenimiento",
    },
]

BASE_DEVICES = ["ESP32-FROST-001", "ESP32-FROST-002"]


def truck_specs(total: int) -> list[dict]:
    specs = [dict(item) for item in BASE_TRUCKS]
    for index in range(len(specs), total):
        specs.append(
            {
                "brand": "LoadTest",
                "model": "Generado",
                "year": 2024,
                "plate": f"LOAD-{index + 1:03d}",
                "description": "Camión generado para pruebas de carga",
                "status": "disponible",
            }
        )
    return specs


def device_specs(total: int) -> list[str]:
    devices = list(BASE_DEVICES)
    for index in range(len(devices), total):
        devices.append(f"LOAD-DEV-{index + 1:03d}")
    return devices


def reset_demo(db) -> None:
    db.execute(delete(Device).where(Device.device_id.like("LOAD-DEV-%")))
    db.execute(delete(Device).where(Device.device_id.in_(BASE_DEVICES)))
    db.execute(delete(Truck).where(Truck.plate.like("LOAD-%")))
    db.execute(delete(Truck).where(Truck.plate.in_([s["plate"] for s in BASE_TRUCKS])))
    db.execute(delete(Route).where(Route.name == ROUTE_NAME))
    db.commit()
    logger.info("Datos de demo eliminados")


def get_or_create_route(db) -> tuple[Route, bool]:
    route = db.scalar(select(Route).where(Route.name == ROUTE_NAME))
    if route is not None:
        return route, False

    route = Route(name=ROUTE_NAME, status="activa", description="Ruta de demostración")
    route.points = [
        DeliveryPoint(
            name=name,
            address=address,
            latitude=lat,
            longitude=lon,
            order_index=index,
        )
        for index, (name, address, lat, lon) in enumerate(POINTS)
    ]
    try:
        route.geometry = routing.calculate_geometry(
            [(point[2], point[3]) for point in POINTS]
        )
        logger.info("Geometría calculada con OSRM")
    except routing.RoutingUnavailableError as exc:
        logger.warning("OSRM no disponible, ruta creada sin geometría: %s", exc)
    db.add(route)
    db.flush()
    return route, True


def get_or_create_truck(db, spec: dict, route_id: int | None) -> tuple[Truck, bool]:
    truck = db.scalar(
        select(Truck).where(Truck.plate == spec["plate"], Truck.is_deleted.is_(False))
    )
    if truck is not None:
        return truck, False
    truck = Truck(
        brand=spec["brand"],
        model=spec["model"],
        year=spec["year"],
        plate=spec["plate"],
        description=spec["description"],
        status=spec["status"],
        route_id=route_id,
    )
    db.add(truck)
    db.flush()
    return truck, True


def ensure_device(db, device_id: str, truck_id: int) -> str | None:
    existing = db.scalar(select(Device).where(Device.device_id == device_id))
    if existing is not None:
        return None
    secret = generate_device_secret()
    db.add(
        Device(
            device_id=device_id,
            truck_id=truck_id,
            key_hash=device_fingerprint(secret),
            key_scheme="hmac",
        )
    )
    db.flush()
    return secret


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed idempotente de FrostBase")
    parser.add_argument(
        "--reset", action="store_true", help="Elimina los datos de demo"
    )
    parser.add_argument(
        "--print-keys",
        action="store_true",
        help="Imprime las claves generadas en esta ejecución",
    )
    parser.add_argument(
        "--trucks", type=int, default=len(BASE_TRUCKS), help="Total de camiones"
    )
    parser.add_argument(
        "--devices", type=int, default=len(BASE_DEVICES), help="Total de dispositivos"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.trucks < len(BASE_TRUCKS):
        raise SystemExit(f"--trucks debe ser >= {len(BASE_TRUCKS)}")
    if args.devices < len(BASE_DEVICES):
        raise SystemExit(f"--devices debe ser >= {len(BASE_DEVICES)}")

    ensure_schema()
    created_devices: list[tuple[str, str]] = []

    with SessionLocal() as db:
        bootstrap_database(db)
        settings_service.get_settings(db)

        if args.reset:
            reset_demo(db)

        route, route_created = get_or_create_route(db)
        trucks: list[Truck] = []
        for index, spec in enumerate(truck_specs(args.trucks)):
            truck, _ = get_or_create_truck(db, spec, route.id if index == 0 else None)
            trucks.append(truck)

        for index, device_id in enumerate(device_specs(args.devices)):
            truck = trucks[index % len(trucks)]
            secret = ensure_device(db, device_id, truck.id)
            if secret:
                created_devices.append((device_id, secret))

        db.commit()

    print("\n=== Seed de FrostBase completado ===")
    print(f"Ruta: {ROUTE_NAME} ({'creada' if route_created else 'ya existía'})")
    print(f"Camiones activos de demo: {len(trucks)}")
    print(f"Dispositivos de demo: {args.devices}")
    if created_devices and (args.print_keys or len(created_devices) <= 2):
        print("\nClaves de dispositivos (guárdelas, no se mostrarán de nuevo):")
        for device_id, secret in created_devices:
            print(f"  {device_id}: {secret}")
        print(
            "\nCopie la clave en iot-simulator/.env como DEVICE_KEY. "
            "NO es la placa del camión: es la cadena larga anterior."
        )
    elif created_devices:
        print(
            "\nSe generaron claves nuevas; use --print-keys en esta ejecución "
            "para mostrarlas o rótelas con scripts.rotate_device_key."
        )
    print()


if __name__ == "__main__":
    main()
