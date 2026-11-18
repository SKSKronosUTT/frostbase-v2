"""Recuperación guiada de Frostbase en un solo comando.

El flujo es:
    1. Respalda el estado actual (``pre_restore``) como red de seguridad.
    2. Detiene el contenedor de la aplicación.
    3. Restaura el respaldo en la base destino (operación destructiva).
    4. Compara checksums contra la huella guardada en los metadatos.
    5. Arranca la aplicación y espera ``/api/health``.
    6. Si algo falla, restaura automáticamente el respaldo previo.

Uso:
    # Simulación: muestra el plan sin tocar nada
    python backend/scripts/db_recover.py --dump db-backups/frostbase_nightly.dump.enc --dry-run

    # Recuperación real de la base principal
    python backend/scripts/db_recover.py \
        --dump db-backups/frostbase_nightly_20261116T020000Z.dump.enc \
        --passphrase-file C:\\frostbase\\backup.pass --yes

    # Prueba sobre la copia de práctica y su API aislada
    python backend/scripts/db_recover.py \
        --dump db-backups/frostbase_drill_dr01_....dump \
        --target frostbase_drill \
        --app-container frostbase-drill-app \
        --health-url http://localhost:8001/api/health --yes
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from db_tools import (
    DB_CONTAINER,
    PASSPHRASE_ENV,
    backup_database,
    compare_checksums,
    container_exists,
    database_checksums,
    database_exists,
    is_encrypted_backup,
    load_metadata,
    resolve_passphrase,
    restore_database,
    start_container,
    stop_container,
    wait_http,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recuperación guiada de Frostbase")
    parser.add_argument("--dump", required=True, help="Respaldo a restaurar")
    parser.add_argument("--target", default="frostbase", help="Base destino")
    parser.add_argument("--container", default=DB_CONTAINER, help="Contenedor PostgreSQL")
    parser.add_argument(
        "--app-container",
        default="frostbase-app",
        help="Contenedor de la aplicación (default: frostbase-app)",
    )
    parser.add_argument(
        "--health-url",
        default="http://localhost:8000/api/health",
        help="URL de health de la aplicación",
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=60,
        help="Segundos de espera para el health check",
    )
    parser.add_argument(
        "--skip-app",
        action="store_true",
        help="No detiene ni arranca la aplicación (solo restaura la base)",
    )
    parser.add_argument(
        "--no-pre-backup",
        action="store_true",
        help="No crea el respaldo previo de seguridad",
    )
    parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="No intenta volver al respaldo previo si la recuperación falla",
    )
    parser.add_argument(
        "--backup-dir",
        default=str(Path(__file__).resolve().parents[2] / "db-backups"),
        help="Carpeta para el respaldo previo",
    )
    parser.add_argument(
        "--metadata",
        help="Metadatos del respaldo (default: <dump>.json)",
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
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma la operación destructiva",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el plan sin ejecutar cambios",
    )
    parser.add_argument("--output", help="Archivo JSON de salida")
    args = parser.parse_args()

    source = Path(args.dump)
    plan = {
        "dump": str(source),
        "target": args.target,
        "app_container": args.app_container,
        "skip_app": args.skip_app,
        "pre_backup": not args.no_pre_backup,
        "rollback_on_failure": not args.no_rollback,
        "encrypted": is_encrypted_backup(source) if source.exists() else None,
    }
    if args.dry_run:
        print(json.dumps({"dry_run": True, "plan": plan}, indent=2, ensure_ascii=False))
        return 0
    if not args.yes:
        print(
            json.dumps(
                {
                    "error": "Operación destructiva no confirmada",
                    "hint": "Agregue --yes para ejecutar o --dry-run para simular",
                    "plan": plan,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2
    if not source.exists():
        print(json.dumps({"error": f"No existe el respaldo: {source}"}, indent=2))
        return 1

    passphrase = None
    if plan["encrypted"]:
        passphrase = resolve_passphrase(
            args.passphrase_file,
            env_var=args.passphrase_env,
            allow_prompt=sys.stdin.isatty(),
        )

    started = time.perf_counter()
    result: dict = {"plan": plan, "success": False}
    pre_backup = None
    app_stopped = False
    app_started = False

    try:
        if not args.no_pre_backup and database_exists(
            args.target, container=args.container
        ):
            pre_backup = backup_database(
                args.target,
                label="pre_restore",
                out_dir=args.backup_dir,
                container=args.container,
                passphrase=passphrase,
                include_checksums=True,
            )
            result["pre_backup"] = pre_backup

        if not args.skip_app and container_exists(args.app_container):
            result["app_stop"] = stop_container(args.app_container)
            app_stopped = result["app_stop"]["stopped"]

        result["restore"] = restore_database(
            source,
            args.target,
            drop=True,
            container=args.container,
            passphrase=passphrase,
        )

        metadata = load_metadata(source, args.metadata)
        if metadata and metadata.get("source_checksums"):
            actual = database_checksums(args.target, container=args.container)
            comparison = compare_checksums(
                metadata["source_checksums"], actual
            )
            result["verification"] = {
                "comparison": comparison,
                "checksums": actual,
            }
        else:
            result["verification"] = {
                "comparison": None,
                "note": "Sin metadatos de checksums; se omite la comparación",
            }

        if app_stopped:
            result["app_start"] = start_container(args.app_container)
            app_started = result["app_start"]["started"]
            healthy = wait_http(args.health_url, args.health_timeout)
        else:
            healthy = None
        result["app_health"] = healthy

        verified = (
            result["verification"]["comparison"] is None
            or result["verification"]["comparison"]["match"]
        )
        if not verified:
            raise RuntimeError("Los checksums restaurados no coinciden con el respaldo")
        if healthy is False:
            raise RuntimeError("La aplicación no respondió al health check")

        result["success"] = True
    except Exception as error:
        result["error"] = str(error)
        if pre_backup and not args.no_rollback:
            try:
                if app_stopped:
                    stop_container(args.app_container)
                    app_started = False
                result["rollback"] = {
                    "performed": True,
                    "restore": restore_database(
                        pre_backup["file"],
                        args.target,
                        drop=True,
                        container=args.container,
                        passphrase=passphrase,
                    ),
                }
                if app_stopped:
                    start_container(args.app_container)
                    app_started = True
                    result["rollback"]["healthy"] = wait_http(
                        args.health_url, args.health_timeout
                    )
            except Exception as rollback_error:
                result["rollback"] = {
                    "performed": True,
                    "error": str(rollback_error),
                }
    finally:
        if app_stopped and not app_started:
            start_container(args.app_container)
        result["rto_seconds"] = round(time.perf_counter() - started, 2)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # pragma: no cover - salida limpia para automatización
        print(json.dumps({"error": str(error)}, indent=2, ensure_ascii=False))
        sys.exit(1)
