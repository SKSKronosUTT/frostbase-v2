"""Genera, cifra, espeja y verifica un respaldo lógico de Frostbase.

Uso:
    # Respaldo plano
    python backend/scripts/db_backup.py --db frostbase --label nightly

    # Respaldo cifrado, con retención y copia externa
    python backend/scripts/db_backup.py --db frostbase --label nightly \
        --encrypt --passphrase-file C:\\frostbase\\backup.pass \
        --mirror-dir D:\\Backups\\frostbase \
        --prune --retention-days 30 --keep-last 7

    # Respaldo + verificación inmediata (restaura en una base temporal)
    python backend/scripts/db_backup.py --db frostbase --label nightly \
        --encrypt --passphrase-file C:\\frostbase\\backup.pass --verify

La passphrase nunca se recibe por argumento: use ``--passphrase-file`` o la
variable de entorno ``FROSTBASE_BACKUP_PASSPHRASE``. Si no se indica ninguna y
la terminal es interactiva, se solicita de forma segura.
"""

from __future__ import annotations

import argparse
import json
import sys

from db_tools import (
    DB_CONTAINER,
    DB_NAME,
    DEFAULT_BACKUP_DIR,
    PASSPHRASE_ENV,
    backup_database,
    prune_backups,
    resolve_passphrase,
    verify_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Respaldo lógico de Frostbase")
    parser.add_argument("--db", default=DB_NAME, help="Base de datos a respaldar")
    parser.add_argument("--label", default="", help="Etiqueta del respaldo")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Carpeta destino de los respaldos",
    )
    parser.add_argument("--container", default=DB_CONTAINER, help="Contenedor PostgreSQL")
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Cifra el respaldo con AES-256-GCM",
    )
    parser.add_argument(
        "--passphrase-file",
        help="Archivo que contiene la passphrase (recomendado)",
    )
    parser.add_argument(
        "--passphrase-env",
        default=PASSPHRASE_ENV,
        help=f"Variable de entorno con la passphrase (default: {PASSPHRASE_ENV})",
    )
    parser.add_argument(
        "--keep-plaintext",
        action="store_true",
        help="Conserva el .dump en claro aunque se cifre (no recomendado)",
    )
    parser.add_argument(
        "--no-checksums",
        action="store_true",
        help="Omite el cálculo de checksums del origen (más rápido)",
    )
    parser.add_argument(
        "--mirror-dir",
        help="Copia el respaldo y sus metadatos a esta ubicación externa",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Aplica retención después de crear el respaldo",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Días de retención para --prune (default: 30)",
    )
    parser.add_argument(
        "--keep-last",
        type=int,
        default=7,
        help="Cantidad mínima de respaldos a conservar (default: 7)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Restaura el respaldo en una base temporal y compara checksums",
    )
    parser.add_argument(
        "--temp-db",
        default="frostbase_verify",
        help="Base temporal para --verify (default: frostbase_verify)",
    )
    args = parser.parse_args()

    passphrase = None
    if args.encrypt:
        passphrase = resolve_passphrase(
            args.passphrase_file,
            env_var=args.passphrase_env,
            allow_prompt=sys.stdin.isatty(),
        )

    metadata = backup_database(
        args.db,
        label=args.label,
        out_dir=args.out_dir,
        container=args.container,
        passphrase=passphrase,
        remove_plaintext=not args.keep_plaintext,
        include_checksums=not args.no_checksums,
        mirror_dir=args.mirror_dir,
    )
    result: dict = {"backup": metadata}

    if args.prune:
        result["prune"] = prune_backups(
            args.out_dir,
            database=args.db,
            retention_days=args.retention_days,
            keep_last=args.keep_last,
        )

    exit_code = 0
    if args.verify:
        verification = verify_backup(
            metadata["file"],
            passphrase=passphrase,
            container=args.container,
            temp_database=args.temp_db,
        )
        result["verification"] = verification
        if not verification["verified"]:
            exit_code = 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # pragma: no cover - salida limpia para automatización
        print(json.dumps({"error": str(error)}, indent=2, ensure_ascii=False))
        sys.exit(1)
