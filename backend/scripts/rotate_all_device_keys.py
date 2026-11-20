"""Migra todas las claves de dispositivo existentes a HMAC.

La migración de esquema 0003 deja los dispositivos existentes como
``key_scheme='argon2'``. Este script genera una clave nueva para cada dispositivo,
la guarda como HMAC y la imprime **una sola vez**. Las claves anteriores dejan de
funcionar inmediatamente.

Uso:
    python -m scripts.rotate_all_device_keys --dry-run
    python -m scripts.rotate_all_device_keys --yes
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import device_fingerprint, generate_device_secret
from app.models.device import Device


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo cuenta cuántos dispositivos se migrarían.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma la rotación masiva (obligatorio sin --dry-run).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.dry_run and not args.yes:
        print(
            "ERROR: esto invalida las claves actuales de todos los dispositivos. "
            "Usa --dry-run para revisar o --yes para confirmar.",
            file=sys.stderr,
        )
        return 1

    with SessionLocal() as db:
        devices = list(db.scalars(select(Device).order_by(Device.id)))
        if args.dry_run:
            pending = sum(1 for device in devices if device.key_scheme != "hmac")
            print(f"Dispositivos totales: {len(devices)}")
            print(f"Dispositivos a migrar a HMAC: {pending}")
            return 0

        rotated: list[tuple[str, str]] = []
        for device in devices:
            secret = generate_device_secret()
            device.key_hash = device_fingerprint(secret)
            device.key_scheme = "hmac"
            db.add(device)
            rotated.append((device.device_id, secret))
        db.commit()

    print(f"Dispositivos rotados: {len(rotated)}")
    if rotated:
        print("\nClaves nuevas (guárdelas, no se mostrarán de nuevo):")
        for device_id, secret in rotated:
            print(f"  {device_id}: {secret}")
        print("\nActualice iot-simulator/.env y el firmware antes de reiniciar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
