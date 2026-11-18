"""Verifica un respaldo restaurándolo en una base temporal y comparando checksums.

Uso:
    python backend/scripts/db_verify.py \
        --dump db-backups/frostbase_nightly_20261116T020000Z.dump.enc \
        --passphrase-file C:\\frostbase\\backup.pass

La verificación compara el digest restaurado contra ``source_checksums`` guardado
en el archivo ``<dump>.json`` al momento de crear el respaldo. Devuelve código de
salida 1 si hay diferencias.
"""

from __future__ import annotations

import argparse
import json
import sys

from db_tools import (
    DB_CONTAINER,
    PASSPHRASE_ENV,
    is_encrypted_backup,
    resolve_passphrase,
    verify_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificación de respaldos Frostbase")
    parser.add_argument("--dump", required=True, help="Archivo .dump o .dump.enc")
    parser.add_argument(
        "--metadata",
        help="Archivo de metadatos (default: <dump>.json)",
    )
    parser.add_argument(
        "--passphrase-file",
        help="Archivo con la passphrase si el respaldo está cifrado",
    )
    parser.add_argument(
        "--passphrase-env",
        default=PASSPHRASE_ENV,
        help=f"Variable de entorno con la passphrase (default: {PASSPHRASE_ENV})",
    )
    parser.add_argument("--container", default=DB_CONTAINER, help="Contenedor PostgreSQL")
    parser.add_argument(
        "--temp-db",
        default="frostbase_verify",
        help="Base temporal para la restauración de verificación",
    )
    parser.add_argument(
        "--keep-temp-db",
        action="store_true",
        help="Conserva la base temporal para inspección",
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

    result = verify_backup(
        args.dump,
        metadata_path=args.metadata,
        passphrase=passphrase,
        container=args.container,
        temp_database=args.temp_db,
        keep_temp_database=args.keep_temp_db,
    )

    if args.output:
        from pathlib import Path

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # pragma: no cover - salida limpia para automatización
        print(json.dumps({"error": str(error)}, indent=2, ensure_ascii=False))
        sys.exit(1)
