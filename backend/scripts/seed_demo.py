"""Seed de demostración de FrostBase.

Uso (desde backend/):
    python -m scripts.seed_demo

Crea camiones, una ruta, dispositivos IoT y muestra sus claves una sola vez.
No se ejecuta automáticamente en producción.
"""
from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.core.security import generate_device_secret, hash_device_secret
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

TRUCKS = [
    {
        "brand": "Freightliner",
        "model": "M2 106",
        "year": 2022,
        "plate": "ABC-123-A",
        "description": "Unidad de reparto refrigerado",
        "status": "en_ruta",
        "device_id": "ESP32-FROST-001",
    },
    {
        "brand": "Isuzu",
        "model": "NPR",
        "year": 2021,
        "plate": "JKL-456-B",
        "description": "Unidad de apoyo",
        "status": "disponible",
        "device_id": "ESP32-FROST-002",
    },
    {
        "brand": "Kenworth",
        "model": "T370",
        "year": 2023,
        "plate": "XYZ-789-C",
        "description": "Unidad en mantenimiento",
        "status": "mantenimiento",
        "device_id": None,
    },
]


def main() -> None:
    ensure_schema()
    created_devices: list[tuple[str, str]] = []

    with SessionLocal() as db:
        bootstrap_database(db)
        settings_service.get_settings(db)

        route = Route(name="", status="activa", description="Ruta de demostración")
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
        route.name = f"{POINTS[0][0]} - {POINTS[-1][0]}"
        try:
            route.geometry = routing.calculate_geometry(
                [(point[2], point[3]) for point in POINTS]
            )
            logger.info("Geometría calculada con OSRM")
        except routing.RoutingUnavailableError as exc:
            logger.warning("OSRM no disponible, ruta creada sin geometría: %s", exc)
        db.add(route)
        db.flush()

        for index, data in enumerate(TRUCKS):
            if db.query(Truck).filter(Truck.plate == data["plate"]).first():
                logger.info("El camión %s ya existe, se omite", data["plate"])
                continue
            truck = Truck(
                brand=data["brand"],
                model=data["model"],
                year=data["year"],
                plate=data["plate"],
                description=data["description"],
                status=data["status"],
                route_id=route.id if index == 0 else None,
            )
            db.add(truck)
            db.flush()

            if data["device_id"]:
                if db.query(Device).filter(Device.device_id == data["device_id"]).first():
                    continue
                secret = generate_device_secret()
                db.add(
                    Device(
                        device_id=data["device_id"],
                        truck_id=truck.id,
                        key_hash=hash_device_secret(secret),
                    )
                )
                created_devices.append((data["device_id"], secret))

        db.commit()

    print("\n=== Seed de FrostBase completado ===")
    print(f"Ruta creada: {POINTS[0][0]} - {POINTS[-1][0]}")
    if created_devices:
        print("\nClaves de dispositivos (guárdelas, no se mostrarán de nuevo):")
        for device_id, secret in created_devices:
            print(f"  {device_id}: {secret}")
        print("\nUse la primera clave en iot-simulator/.env como DEVICE_KEY.")
    print()


if __name__ == "__main__":
    main()
