"""Rota la clave de un dispositivo y la imprime una sola vez.

Uso (dentro del contenedor):
    docker compose exec app python -m scripts.rotate_device_key --device-id ESP32-FROST-001

La clave anterior deja de funcionar inmediatamente. Copie el valor impreso en
``iot-simulator/.env`` como ``DEVICE_KEY`` y reinicie el simulador o el firmware.
"""

from __future__ import annotations

import argparse
import sys

from app.core.database import SessionLocal
from app.repositories import devices as devices_repo
from app.services import device_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--device-id",
        help="Identificador del dispositivo (por ejemplo ESP32-FROST-001).",
    )
    group.add_argument(
        "--device-pk",
        type=int,
        help="ID interno del dispositivo (columna devices.id).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    with SessionLocal() as db:
        if args.device_pk is not None:
            device = devices_repo.get(db, args.device_pk)
        else:
            device = devices_repo.get_by_identifier(db, args.device_id.strip())

        if device is None:
            print(
                "ERROR: no existe ese dispositivo. Compruebe el identificador "
                "en el panel (Flota → dispositivo).",
                file=sys.stderr,
            )
            return 1

        created = device_service.rotate_key(db, device.id)

    print(f"Dispositivo: {created.device_id}")
    print(f"DEVICE_KEY={created.device_key}")
    print(
        "\nCopie la clave en iot-simulator/.env (o en el firmware) y reinicie "
        "el cliente. La clave anterior ya no funciona."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
