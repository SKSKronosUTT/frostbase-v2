"""Resuelve alertas activas de dispositivos de prueba (B0).

Por defecto **no modifica nada**: muestra una simulación. Para aplicar:

    python -m scripts.resolve_stale_alerts --apply

Filtros:
    --device-prefix LOAD-          (repetible; reemplaza los prefijos por defecto)
    --older-than-days 2            (solo alertas iniciadas antes del corte)
    --show 20                      (filas de muestra)
    --keep-devices                 (no silenciar los dispositivos de prueba)

Los prefijos por defecto son ``LOAD-``, ``E2E-`` y ``ESP32-DOOR-``; la demo
``ESP32-DEMO-*`` se conserva. Las alertas se marcan como ``resuelta``, no se
borran. Además, los dispositivos de prueba se silencian (``last_seen=NULL``)
para que el watcher no vuelva a crear alertas de desconexión. Es idempotente.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import timedelta

from scripts.runtime import configure_stdio, load_project_env

load_project_env()

from sqlalchemy import func, or_, select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.alert import Alert  # noqa: E402
from app.models.device import Device  # noqa: E402
from app.utils.time import utcnow  # noqa: E402

DEFAULT_DEVICE_PREFIXES = ("LOAD-", "E2E-", "ESP32-DOOR-")


@dataclass
class CleanupResult:
    total: int
    by_prefix: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)
    applied: int = 0
    devices_to_silence: int = 0
    devices_silenced: int = 0
    dry_run: bool = True


def run_cleanup(
    db: Session,
    *,
    device_prefixes: tuple[str, ...] | list[str] = DEFAULT_DEVICE_PREFIXES,
    older_than_days: int | None = None,
    dry_run: bool = True,
    sample_limit: int = 10,
    silence_devices: bool = True,
) -> CleanupResult:
    """Resuelve las alertas activas que coinciden con los filtros.

    Si ``silence_devices`` está activo, también pone ``last_seen=NULL`` en los
    dispositivos de prueba para que el watcher no recree las desconexiones.
    """
    prefixes = tuple(prefix for prefix in device_prefixes if prefix)
    if not prefixes:
        raise ValueError("Indica al menos un --device-prefix")
    if older_than_days is not None and older_than_days < 0:
        raise ValueError("--older-than-days no puede ser negativo")

    device_filter = or_(*[Device.device_id.startswith(prefix) for prefix in prefixes])
    devices_to_silence = 0
    if silence_devices:
        devices_to_silence = int(
            db.scalar(
                select(func.count(Device.id)).where(
                    device_filter,
                    Device.last_seen.is_not(None),
                )
            )
            or 0
        )

    statement = (
        select(
            Alert.id,
            Alert.alert_type,
            Alert.started_at,
            Device.device_id,
        )
        .join(Device, Device.id == Alert.device_id)
        .where(Alert.status == "activa", device_filter)
        .order_by(Alert.started_at)
    )
    if older_than_days is not None:
        statement = statement.where(
            Alert.started_at < utcnow() - timedelta(days=older_than_days)
        )

    rows = list(db.execute(statement).all())
    by_prefix: dict[str, int] = {}
    by_type: dict[str, int] = {}
    samples: list[str] = []
    for row in rows:
        prefix = next(
            (item for item in prefixes if row.device_id.startswith(item)),
            "otros",
        )
        by_prefix[prefix] = by_prefix.get(prefix, 0) + 1
        by_type[row.alert_type] = by_type.get(row.alert_type, 0) + 1
        if len(samples) < sample_limit:
            moment = row.started_at.astimezone(settings.tz)
            samples.append(
                f"{row.device_id} · {row.alert_type} · {moment:%Y-%m-%d %H:%M}"
            )

    applied = 0
    devices_silenced = 0
    if not dry_run:
        if silence_devices and devices_to_silence:
            result = db.execute(
                update(Device)
                .where(device_filter, Device.last_seen.is_not(None))
                .values(last_seen=None)
            )
            devices_silenced = int(getattr(result, "rowcount", 0) or 0)
        if rows:
            result = db.execute(
                update(Alert)
                .where(Alert.id.in_([row.id for row in rows]))
                .values(status="resuelta", resolved_at=utcnow())
            )
            applied = int(getattr(result, "rowcount", 0) or 0)
        db.commit()

    return CleanupResult(
        total=len(rows),
        by_prefix=by_prefix,
        by_type=by_type,
        samples=samples,
        applied=applied,
        devices_to_silence=devices_to_silence,
        devices_silenced=devices_silenced,
        dry_run=dry_run,
    )


def _format_counts(counts: dict[str, int]) -> str:
    return (
        ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))
        or "ninguna"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resuelve alertas activas de dispositivos de prueba"
    )
    parser.add_argument(
        "--device-prefix",
        action="append",
        dest="prefixes",
        default=None,
        help=(
            "Prefijo de device_id (repetible). Por defecto: "
            + ", ".join(DEFAULT_DEVICE_PREFIXES)
        ),
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=None,
        help="Solo alertas iniciadas antes de N días",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios (sin esto solo simula)",
    )
    parser.add_argument(
        "--show",
        type=int,
        default=10,
        help="Número de alertas de muestra (default: 10)",
    )
    parser.add_argument(
        "--keep-devices",
        action="store_true",
        help=(
            "No silenciar los dispositivos de prueba (el watcher puede recrear alertas)"
        ),
    )
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    args = parse_args()
    prefixes = tuple(args.prefixes or DEFAULT_DEVICE_PREFIXES)
    mode = "APLICAR" if args.apply else "SIMULACIÓN (use --apply)"
    print("\n=== Limpieza de alertas de prueba ===")
    print(f"Modo: {mode}")
    print(f"Prefijos: {', '.join(prefixes)}")
    if args.older_than_days is not None:
        print(f"Antigüedad mínima: {args.older_than_days} días")

    try:
        with SessionLocal() as db:
            result = run_cleanup(
                db,
                device_prefixes=prefixes,
                older_than_days=args.older_than_days,
                dry_run=not args.apply,
                sample_limit=max(0, args.show),
                silence_devices=not args.keep_devices,
            )
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    if result.total == 0:
        if args.keep_devices:
            print("Dispositivos de prueba: sin cambios (--keep-devices)")
        elif result.dry_run:
            print(f"Dispositivos a silenciar: {result.devices_to_silence}")
        else:
            print(f"Dispositivos silenciados: {result.devices_silenced}")
        print("\nNo hay alertas que coincidan con los filtros.")
        return 0

    print(f"\nCandidatas: {result.total} ({_format_counts(result.by_prefix)})")
    print(f"Por tipo: {_format_counts(result.by_type)}")
    if args.keep_devices:
        print("Dispositivos de prueba: sin cambios (--keep-devices)")
    elif result.dry_run:
        print(f"Dispositivos a silenciar: {result.devices_to_silence}")
    else:
        print(f"Dispositivos silenciados: {result.devices_silenced}")
    if result.samples:
        print("\nMuestra:")
        for sample in result.samples:
            print(f"  - {sample}")
    if result.dry_run:
        print("\nNo se modificó nada. Ejecute con --apply para resolverlas.")
    else:
        print(f"\nResueltas: {result.applied} alertas.")
    print(
        "\nLas alertas se marcan como resueltas (no se borran) y los dispositivos "
        "de prueba quedan silenciados para que el watcher no recree desconexiones. "
        "La demo ESP32-DEMO-* queda fuera de los prefijos por defecto."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
