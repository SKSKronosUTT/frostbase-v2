"""Genera un respaldo físico del clúster con pg_basebackup.

Este respaldo es la base para una recuperación punto en el tiempo (PITR) cuando
se activa ``archive_mode=on`` y un ``archive_command``. También sirve como copia
física completa del clúster.

Uso:
    python backend/scripts/db_basebackup.py
    python backend/scripts/db_basebackup.py --label pre_upgrade

Salida: ``db-backups/base/frostbase_base_<timestamp>.tar.gz`` + ``.json`` con
metadatos (tamaño, SHA-256, archive_mode, wal_level, archivos incluidos).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from db_tools import (
    DB_CONTAINER,
    DB_USER,
    DEFAULT_BACKUP_DIR,
    docker,
    exec_in,
    psql_scalar,
    sha256_file,
    utc_now,
    utc_stamp,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Respaldo físico con pg_basebackup")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_BACKUP_DIR / "base"),
        help="Carpeta destino para el respaldo físico",
    )
    parser.add_argument("--container", default=DB_CONTAINER, help="Contenedor PostgreSQL")
    parser.add_argument("--user", default=DB_USER, help="Usuario de PostgreSQL")
    parser.add_argument("--label", default="", help="Etiqueta del respaldo")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    stem = f"frostbase_base_{args.label + '_' if args.label else ''}{stamp}"
    remote_dir = f"/tmp/{stem}"
    remote_archive = f"/tmp/{stem}.tar.gz"
    local_archive = out_dir / f"{stem}.tar.gz"

    archive_mode = psql_scalar("postgres", "SHOW archive_mode", container=args.container)
    wal_level = psql_scalar("postgres", "SHOW wal_level", container=args.container)

    try:
        exec_in(args.container, "rm", "-rf", remote_dir, check=False)
        exec_in(args.container, "mkdir", "-p", remote_dir)
        exec_in(
            args.container,
            "pg_basebackup",
            "-U",
            args.user,
            "-D",
            remote_dir,
            "-Ft",
            "-z",
            "-P",
            "-X",
            "stream",
            "--checkpoint=fast",
        )
        files = exec_in(args.container, "ls", "-1", remote_dir).stdout.split()
        exec_in(
            args.container,
            "tar",
            "-czf",
            remote_archive,
            "-C",
            remote_dir,
            ".",
        )
        exec_in(args.container, "tar", "-tzf", remote_archive)
        docker("cp", f"{args.container}:{remote_archive}", str(local_archive))
    finally:
        exec_in(args.container, "rm", "-rf", remote_dir, check=False)
        exec_in(args.container, "rm", "-f", remote_archive, check=False)

    metadata = {
        "file": str(local_archive),
        "created_at": utc_now(),
        "label": args.label,
        "format": "pg_basebackup tar.gz",
        "size_bytes": local_archive.stat().st_size,
        "sha256": sha256_file(local_archive),
        "archive_mode": archive_mode,
        "wal_level": wal_level,
        "included_files": files,
        "pitr_ready": archive_mode == "on",
        "note": (
            "PITR requiere archive_mode=on y archive_command configurado; "
            "sin eso este respaldo es una copia física completa pero no permite "
            "recuperar a un instante arbitrario."
            if archive_mode != "on"
            else "PITR habilitado: conserve también el archivo WAL."
        ),
    }
    metadata_path = Path(str(local_archive) + ".json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # pragma: no cover - salida limpia para automatización
        print(json.dumps({"error": str(error)}, indent=2, ensure_ascii=False))
        sys.exit(1)
