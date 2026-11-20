"""Cuenta y elimina lecturas duplicadas antes/después de la migración 0004.

Uso:
    python -m scripts.dedupe_readings --dry-run   # solo cuenta
    python -m scripts.dedupe_readings --apply     # elimina duplicados

Conserva la lectura con MIN(id) para cada (device_id, reading_timestamp).
Requiere un respaldo verificado antes de usar ``--apply``.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.core.database import SessionLocal

_COUNT_SQL = text(
    """
    SELECT COALESCE(sum(n - 1), 0)
    FROM (
        SELECT count(*) AS n
        FROM readings
        GROUP BY device_id, reading_timestamp
        HAVING count(*) > 1
    ) AS duplicates
    """
)

_DELETE_SQL = text(
    """
    DELETE FROM readings a
    USING readings b
    WHERE a.device_id = b.device_id
      AND a.reading_timestamp = b.reading_timestamp
      AND a.id > b.id
    """
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Solo contar.")
    parser.add_argument("--apply", action="store_true", help="Eliminar duplicados.")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("ERROR: use --dry-run o --apply.", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        pending = int(db.execute(_COUNT_SQL).scalar() or 0)
        print(f"Lecturas duplicadas a eliminar: {pending}")
        if args.dry_run:
            return 0
        if pending:
            result = db.execute(_DELETE_SQL)
            db.commit()
            print(f"Lecturas eliminadas: {result.rowcount}")
        else:
            print("No hay duplicados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
