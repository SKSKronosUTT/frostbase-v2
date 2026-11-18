"""Restaura un respaldo lógico de Frostbase y verifica su contenido.

Uso:
    # Restauración limpia en una base de datos de verificación
    python backend/scripts/db_restore.py \\
        --dump db-backups/frostbase_drill_dr01_20261115T120000Z.dump \\
        --target frostbase_restore \\
        --compare docs/security/evidence/2026-11-15/checksums_baseline.json

La restauración se ejecuta en una sola transacción (``--single-transaction``),
de modo que un fallo no deja una base de datos parcialmente restaurada.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from db_tools import (
    DB_CONTAINER,
    PASSPHRASE_ENV,
    compare_checksums,
    database_checksums,
    is_encrypted_backup,
    resolve_passphrase,
    restore_database,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restauración de Frostbase")
    parser.add_argument("--dump", required=True, help="Archivo .dump a restaurar")
    parser.add_argument("--target", required=True, help="Base de datos destino")
    parser.add_argument(
        "--no-drop",
        action="store_true",
        help="No elimina la base destino antes de restaurar",
    )
    parser.add_argument("--container", default=DB_CONTAINER, help="Contenedor PostgreSQL")
    parser.add_argument(
        "--passphrase-file",
        help="Archivo con la passphrase si el respaldo está cifrado",
    )
    parser.add_argument(
        "--passphrase-env",
        default=PASSPHRASE_ENV,
        help=f"Variable de entorno con la passphrase (default: {PASSPHRASE_ENV})",
    )
    parser.add_argument(
        "--compare",
        help="Archivo JSON de checksums de referencia para comparar",
    )
    parser.add_argument("--output", help="Archivo JSON de salida")
    args = parser.parse_args()

    passphrase = None
    if is_encrypted_backup(args.dump):
        passphrase = resolve_passphrase(
            args.passphrase_file,
            env_var=args.passphrase_env,
            allow_prompt=sys.stdin.isatty(),
        )

    restore = restore_database(
        args.dump,
        args.target,
        drop=not args.no_drop,
        container=args.container,
        passphrase=passphrase,
    )
    payload: dict = {"restore": restore}
    exit_code = 0

    if args.compare:
        expected = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        if "checksums" in expected:
            expected = expected["checksums"]
        actual = database_checksums(args.target, container=args.container)
        comparison = compare_checksums(expected, actual)
        payload["checksums"] = actual
        payload["comparison"] = comparison
        if not comparison["match"]:
            exit_code = 1

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # pragma: no cover - salida limpia para automatización
        print(json.dumps({"error": str(error)}, indent=2, ensure_ascii=False))
        sys.exit(1)
