"""Calcula checksums deterministas de una base de datos Frostbase.

Uso:
    python backend/scripts/db_checksum.py --db frostbase_drill
    python backend/scripts/db_checksum.py --db frostbase_restore \\
        --compare docs/security/evidence/2026-11-15/checksums_baseline.json

El comando devuelve código de salida 1 cuando la comparación no coincide.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from db_tools import (
    DB_CONTAINER,
    database_checksums,
    compare_checksums,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Checksums de tablas Frostbase")
    parser.add_argument("--db", required=True, help="Base de datos a verificar")
    parser.add_argument("--container", default=DB_CONTAINER, help="Contenedor PostgreSQL")
    parser.add_argument("--output", help="Archivo JSON de salida")
    parser.add_argument(
        "--compare",
        help="Archivo JSON de checksums de referencia para comparar",
    )
    args = parser.parse_args()

    result = database_checksums(args.db, container=args.container)
    payload: dict = {"checksums": result}
    exit_code = 0

    if args.compare:
        expected = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        if "checksums" in expected:
            expected = expected["checksums"]
        comparison = compare_checksums(expected, result)
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
    sys.exit(main())
