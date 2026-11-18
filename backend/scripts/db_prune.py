"""Aplica la política de retención de respaldos de Frostbase.

Uso:
    # Simulación (no borra nada)
    python backend/scripts/db_prune.py --dir db-backups --database frostbase

    # Aplicar la política
    python backend/scripts/db_prune.py --dir db-backups --database frostbase \
        --retention-days 30 --keep-last 7 --yes

Reglas:
    * Siempre se conservan los ``--keep-last`` respaldos más recientes.
    * Del resto, se eliminan los que superen ``--retention-days`` días.
    * Solo se consideran ``*.dump`` y ``*.dump.enc`` (y sus ``.json``).
"""

from __future__ import annotations

import argparse
import json
import sys

from db_tools import DEFAULT_BACKUP_DIR, prune_backups


def main() -> int:
    parser = argparse.ArgumentParser(description="Retención de respaldos Frostbase")
    parser.add_argument(
        "--dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Carpeta de respaldos",
    )
    parser.add_argument(
        "--database",
        help="Limita la poda a los respaldos de esta base (prefijo del nombre)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Días de retención (default: 30)",
    )
    parser.add_argument(
        "--keep-last",
        type=int,
        default=7,
        help="Cantidad mínima de respaldos a conservar (default: 7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra lo que se eliminaría",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma la eliminación real (sin esto solo simula)",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or not args.yes
    result = prune_backups(
        args.dir,
        database=args.database,
        retention_days=args.retention_days,
        keep_last=args.keep_last,
        dry_run=dry_run,
    )
    if dry_run and not args.dry_run:
        result["note"] = "Modo simulación: agregue --yes para eliminar realmente"
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # pragma: no cover - salida limpia para automatización
        print(json.dumps({"error": str(error)}, indent=2, ensure_ascii=False))
        sys.exit(1)
