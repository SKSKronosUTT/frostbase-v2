"""Respaldo programado de PostgreSQL (G8, RNF5).

Genera un dump en formato custom (``-Fc``, comprimido y restaurable con
``pg_restore``) directamente en el host, fuera del árbol del repositorio,
con retención configurable y cifrado opcional con ``age``.

El volcado se ejecuta **dentro** del contenedor y se copia al host para no
corromper binarios con pipes en Windows.

Ejemplos:
    python -m scripts.backup_db
    python -m scripts.backup_db --keep 14
    python -m scripts.backup_db --age-recipient age1xxxxx

Programación (ver docs/ops/BACKUP-RESTORE.md):
    Windows:  Programador de tareas, diario a las 03:00
    Linux:    cron: 0 3 * * *  cd /opt/frostbase && docker compose exec -T ...
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_KEEP = 14
DEFAULT_SERVICE = "db"
DEFAULT_DB = "frostbase"
DEFAULT_USER = "frostbase"
HOST_DIR = Path.home() / "backups" / "frostbase"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Respaldo de PostgreSQL FrostBase")
    parser.add_argument("--service", default=DEFAULT_SERVICE, help="Servicio compose")
    parser.add_argument("--db", default=DEFAULT_DB, help="Nombre de la base")
    parser.add_argument("--user", default=DEFAULT_USER, help="Usuario pg_dump")
    parser.add_argument(
        "--dest", default=str(HOST_DIR), help="Carpeta destino en el host"
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help="Dumps a conservar (0 = sin retención)",
    )
    parser.add_argument(
        "--age-recipient",
        default=None,
        help="Recipient público de age para cifrar el dump",
    )
    return parser.parse_args()


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=check)


def main() -> int:
    args = parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dump_name = f"frostbase_{stamp}.dump"
    container_tmp = f"/tmp/{dump_name}"

    print(f"Volcando {args.db} desde el servicio '{args.service}'…")
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            args.service,
            "pg_dump",
            "-U",
            args.user,
            "-Fc",
            "-f",
            container_tmp,
            args.db,
        ]
    )
    host_dump = dest / dump_name
    run(["docker", "compose", "cp", f"{args.service}:{container_tmp}", str(host_dump)])
    run(["docker", "compose", "exec", "-T", args.service, "rm", "-f", container_tmp])

    final_path = host_dump
    if args.age_recipient:
        encrypted = host_dump.with_suffix(".dump.age")
        result = run(
            ["age", "-r", args.age_recipient, "-o", str(encrypted), str(host_dump)],
            check=False,
        )
        if result.returncode != 0:
            print(
                "[WARN] age no está disponible o falló; "
                "se conserva el dump sin cifrar.",
                file=sys.stderr,
            )
        else:
            host_dump.unlink()
            final_path = encrypted

    size_mb = final_path.stat().st_size / (1024 * 1024)
    print(f"Respaldo listo: {final_path} ({size_mb:.1f} MB)")

    if args.keep > 0:
        import re

        # Solo los dumps generados por este script (frostbase_YYYYMMDDTHHMMSSZ);
        # los históricos manuales (pre_f1, etc.) nunca se tocan.
        stamp_pattern = re.compile(r"^frostbase_\d{8}T\d{6}Z\.dump(\.age)?$")
        dumps = sorted(
            (path for path in dest.iterdir() if stamp_pattern.match(path.name)),
            key=lambda path: path.name,
        )
        for old in dumps[: -args.keep]:
            old.unlink()
            print(f"Retención: eliminado {old.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
