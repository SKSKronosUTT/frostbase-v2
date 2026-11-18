"""Ejecuta las pruebas DLP y DRP de Frostbase sobre una copia de práctica.

El flujo completo es:

1. Prepara ``frostbase_drill`` a partir de un respaldo de la base principal.
2. Levanta una instancia aislada de la API (puerto 8001) contra la copia.
3. DR-01: respaldo lógico + restauración completa + verificación de checksums.
4. DLP-01: control de acceso, PII y exfiltración.
5. DLP-02: borrado lógico, trazabilidad y recuperación de un borrado físico.
6. DR-02: pérdida total de la base de práctica y recuperación con medición de RTO.

Los resultados y evidencias se escriben en ``docs/security/evidence/<fecha>/``.

Uso:
    python backend/scripts/run_dlp_drp_tests.py
    python backend/scripts/run_dlp_drp_tests.py --evidence-dir docs/security/evidence/2026-11-15
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from db_tools import (
    APP_IMAGE,
    DB_CONTAINER,
    DB_NAME,
    DB_PASSWORD,
    DB_USER,
    NETWORK,
    REPO_ROOT,
    backup_database,
    compare_checksums,
    database_checksums,
    docker,
    exec_in,
    psql,
    psql_scalar,
    restore_database,
)

DRILL_DB = os.getenv("FROSTBASE_DRILL_DB", "frostbase_drill")
RESTORE_DB = os.getenv("FROSTBASE_RESTORE_DB", "frostbase_restore")
RECOVERY_DB = os.getenv("FROSTBASE_RECOVERY_DB", "frostbase_restore_recovery")
DRILL_APP = "frostbase-drill-app"
RESTORE_APP = "frostbase-restore-app"
DRILL_PORT = 8001
RESTORE_PORT = 8002
DRILL_SECRET = "frostbase-drill-secret"
ADMIN_EMAIL = "mgonzalez@logisticarf.com"
ADMIN_PASSWORD = "admin123"
DRIVER_EMAIL = "rsilva@logisticarf.com"
DRIVER_PASSWORD = "driver001"
RTO_TARGET_SECONDS = 120


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def redact_email(value: str | None) -> str:
    if not value or "@" not in value:
        return "***"
    local, _, domain = value.partition("@")
    return f"{local[:1]}***@{domain}"


def redact_phone(value: str | None) -> str:
    digits = "".join(char for char in (value or "") if char.isdigit())
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"


def api(
    base: str,
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
    timeout: float = 20,
) -> tuple[int | None, object]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(base.rstrip("/") + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        try:
            return error.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return error.code, raw
    except Exception as error:  # pragma: no cover - diagnóstico
        return None, {"error": str(error)}


def wait_health(base: str, timeout: float = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _ = api(base, "GET", "/api/health", timeout=3)
        if status == 200:
            return True
        time.sleep(0.5)
    return False


def login(base: str, email: str, password: str) -> str:
    status, payload = api(
        base, "POST", "/api/auth/login", body={"email": email, "password": password}
    )
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"Login falló para {email}: HTTP {status} {payload}")
    return payload["data"]["token"]


@contextmanager
def app_instance(database: str, port: int, name: str):
    docker("rm", "-f", name, check=False)
    docker(
        "run",
        "-d",
        "--name",
        name,
        "--network",
        NETWORK,
        "-e",
        f"DATABASE_URL=postgresql://{DB_USER}:{DB_PASSWORD}@db:5432/{database}",
        "-e",
        f"FROSTBASE_SECRET={DRILL_SECRET}",
        "-e",
        "AUTO_SEED=false",
        "-p",
        f"{port}:8000",
        APP_IMAGE,
    )
    base = f"http://localhost:{port}"
    try:
        if not wait_health(base):
            logs = docker("logs", name, "--tail", "40", check=False)
            raise RuntimeError(f"La API de práctica no arrancó.\n{logs.stdout}{logs.stderr}")
        yield base
    finally:
        docker("rm", "-f", name, check=False)


class Recorder:
    def __init__(self):
        self.results: list[dict] = []

    def add(
        self,
        test_id: str,
        name: str,
        status: str,
        expected: str,
        observed,
        evidence: str | None = None,
    ) -> None:
        self.results.append(
            {
                "id": test_id,
                "name": name,
                "status": status,
                "expected": expected,
                "observed": observed,
                "evidence": evidence,
                "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        marker = {"PASS": "OK", "FAIL": "FALLO", "INFO": "INFO"}.get(status, status)
        print(f"[{marker}] {test_id} {name}: {observed}")

    def counts(self) -> dict:
        result = {"PASS": 0, "FAIL": 0, "INFO": 0, "ERROR": 0}
        for item in self.results:
            result[item["status"]] = result.get(item["status"], 0) + 1
        return result


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )


def git_commit() -> str:
    from db_tools import run

    process = run(["git", "rev-parse", "--short", "HEAD"], check=False)
    return process.stdout.strip() if process.returncode == 0 else "desconocido"


def setup_drill(recorder: Recorder) -> dict:
    """Recrea frostbase_drill a partir de un respaldo de la base principal."""

    docker("rm", "-f", DRILL_APP, check=False)
    docker("rm", "-f", RESTORE_APP, check=False)
    for database in (RESTORE_DB, RECOVERY_DB):
        psql("postgres", f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)', check=False)

    source_backup = backup_database(DB_NAME, label="drill_source")
    restore = restore_database(source_backup["file"], DRILL_DB, drop=True)
    recorder.add(
        "PREP-01",
        "Copia de práctica frostbase_drill creada",
        "PASS",
        "Restauración exacta de la base principal",
        {
            "source_database": DB_NAME,
            "drill_database": DRILL_DB,
            "source_dump": source_backup["file"],
            "source_sha256": source_backup["sha256"],
            "restore_seconds": restore["seconds"],
        },
        "checksums_baseline.json",
    )
    return {"source_backup": source_backup, "restore": restore}


def test_dr01(
    recorder: Recorder, baseline: dict, evidence: Path, backup: dict
) -> dict:
    write_json(evidence / "backup_dr01.json", backup)
    recorder.add(
        "DR-01.1",
        "Respaldo lógico íntegro y verificable",
        "PASS"
        if backup["verified_with_pg_restore_list"] and backup["objects"] > 0
        else "FAIL",
        "pg_dump -Fc validado con pg_restore --list",
        {
            "file": backup["file"],
            "size_bytes": backup["size_bytes"],
            "sha256": backup["sha256"],
            "objects": backup["objects"],
        },
        "backup_dr01.json",
    )

    restore = restore_database(backup["file"], RESTORE_DB, drop=True)
    restored = database_checksums(RESTORE_DB)
    comparison = compare_checksums(baseline, restored)
    write_json(evidence / "checksums_restored_dr01.json", restored)
    recorder.add(
        "DR-01.2",
        "Restauración completa sin diferencias",
        "PASS" if comparison["match"] else "FAIL",
        "Mismo digest y mismas filas/checksums en las 20 tablas",
        {
            "restore_seconds": restore["seconds"],
            "expected_digest": comparison["expected_digest"],
            "actual_digest": comparison["actual_digest"],
            "differences": comparison["differences"],
        },
        "checksums_restored_dr01.json",
    )

    functional = {"server_ok": False, "login_ok": False, "dashboard_status": None}
    with app_instance(RESTORE_DB, RESTORE_PORT, RESTORE_APP) as base:
        functional["server_ok"] = True
        token = login(base, ADMIN_EMAIL, ADMIN_PASSWORD)
        functional["login_ok"] = bool(token)
        status, _ = api(base, "GET", "/api/dashboard/summary", token)
        functional["dashboard_status"] = status
    recorder.add(
        "DR-01.3",
        "La base restaurada es funcional para la aplicación",
        "PASS"
        if functional["server_ok"]
        and functional["login_ok"]
        and functional["dashboard_status"] == 200
        else "FAIL",
        "Health 200, login de administrador y dashboard 200",
        functional,
        "checksums_restored_dr01.json",
    )
    return {"backup": backup, "restore": restore, "comparison": comparison, "functional": functional}


def test_dlp01(recorder: Recorder, dr_dump: str, evidence: Path, base: str) -> dict:
    anonymous_paths = [
        "/api/users",
        "/api/orders",
        "/api/readings",
        "/api/dashboard/summary",
        "/api/stores",
        "/api/trucks",
    ]
    anonymous = {path: api(base, "GET", path)[0] for path in anonymous_paths}
    recorder.add(
        "DLP-01.1",
        "Acceso anónimo bloqueado en endpoints de datos",
        "PASS" if all(status == 401 for status in anonymous.values()) else "FAIL",
        "HTTP 401 en todos los endpoints",
        anonymous,
        "dlp01.json",
    )

    driver = login(base, DRIVER_EMAIL, DRIVER_PASSWORD)
    status, payload = api(base, "GET", "/api/users", driver)
    users = payload.get("data", []) if isinstance(payload, dict) else []
    pii_fields = ("email", "phone", "birthDate")
    pii_exposed = any(
        any(field in user for field in pii_fields) for user in users if isinstance(user, dict)
    )
    passwords_exposed = "password_hash" in json.dumps(payload or {})
    sample = [
        {
            "email": redact_email(user.get("email")),
            "phone": redact_phone(user.get("phone")),
            "birthDate": "***" if user.get("birthDate") else None,
            "isAdmin": user.get("isAdmin"),
        }
        for user in users[:3]
        if isinstance(user, dict)
    ]
    write_json(
        evidence / "dlp01_users_sample.json",
        {"http_status": status, "users_returned": len(users), "redacted_sample": sample},
    )
    recorder.add(
        "DLP-01.2",
        "Un conductor no puede enumerar usuarios ni ver PII",
        "PASS" if status in (401, 403) or not pii_exposed else "FAIL",
        "403, o como mínimo respuesta sin email/teléfono/cumpleaños",
        {
            "http_status": status,
            "users_returned": len(users),
            "pii_exposed": pii_exposed,
            "password_hash_exposed": passwords_exposed,
            "redacted_sample": sample,
        },
        "dlp01_users_sample.json",
    )

    status, _ = api(base, "POST", "/api/simulator/check", driver)
    recorder.add(
        "DLP-01.3",
        "RBAC en endpoints exclusivos de administrador",
        "PASS" if status == 403 else "FAIL",
        "HTTP 403 para el rol conductor",
        {"endpoint": "POST /api/simulator/check", "http_status": status},
        "dlp01.json",
    )

    head, _, signature = driver.partition(".")
    tampered = ("A" if head[:1] != "A" else "B") + head[1:] + "." + signature
    status, _ = api(base, "GET", "/api/auth/me", tampered)
    recorder.add(
        "DLP-01.4",
        "Token manipulado rechazado",
        "PASS" if status == 401 else "FAIL",
        "HTTP 401 al alterar el cuerpo firmado",
        {"http_status": status},
        "dlp01.json",
    )

    status, _ = api(base, "GET", "/openapi.json")
    recorder.add(
        "DLP-01.5",
        "Documentación de API no expuesta sin autenticación",
        "PASS" if status in (401, 403, 404) else "FAIL",
        "HTTP 401/403/404",
        {"endpoint": "/openapi.json", "http_status": status},
        "dlp01.json",
    )

    connection_url = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@host.docker.internal:5433/{DB_NAME}"
    )
    process = docker(
        "run",
        "--rm",
        "--add-host=host.docker.internal:host-gateway",
        "postgres:16",
        "psql",
        connection_url,
        "-tAc",
        "SELECT count(*) FROM users",
        check=False,
    )
    host_db_access = process.returncode == 0
    recorder.add(
        "DLP-01.6",
        "Base de datos no accesible desde el host con credenciales por defecto",
        "PASS" if not host_db_access else "FAIL",
        "Conexión rechazada en el puerto 5433",
        {
            "host_db_access": host_db_access,
            "rows_read": process.stdout.strip() if host_db_access else None,
            "port": 5433,
        },
        "dlp01.json",
    )

    remote = "/tmp/frostbase_pii_inspect.dump"
    docker("cp", dr_dump, f"{DB_CONTAINER}:{remote}")
    process = exec_in(
        DB_CONTAINER,
        "pg_restore",
        "-a",
        "-t",
        "users",
        "-f",
        "-",
        remote,
        check=False,
    )
    exec_in(DB_CONTAINER, "rm", "-f", remote, check=False)
    rows_with_email = process.stdout.count("@")
    recorder.add(
        "DLP-01.7",
        "Los respaldos contienen PII en texto claro y sin cifrar",
        "FAIL" if rows_with_email else "PASS",
        "Respaldo cifrado o sin PII en claro",
        {
            "rows_with_email_in_dump": rows_with_email,
            "backup_encrypted": False,
            "backup_file": dr_dump,
            "inspection_error": (process.stderr or "").strip()[:200] or None,
        },
        "backup_dr01.json",
    )
    return {"anonymous": anonymous, "users_status": status}


def test_dlp02(recorder: Recorder, dr_dump: str, evidence: Path, base: str) -> dict:
    admin = login(base, ADMIN_EMAIL, ADMIN_PASSWORD)
    driver = login(base, DRIVER_EMAIL, DRIVER_PASSWORD)
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")

    status, stores_payload = api(base, "GET", "/api/stores", admin)
    stores = stores_payload.get("data", []) if isinstance(stores_payload, dict) else []
    if not stores:
        raise RuntimeError("No hay tiendas en la copia de práctica")
    store_id = stores[0]["id"]

    status, created = api(
        base, "POST", "/api/orders", driver, {"idStore": store_id}
    )
    order_id = created["data"]["id"] if status == 200 else None
    logs_before = int(
        psql_scalar(
            DRILL_DB,
            f"SELECT count(*) FROM order_logs WHERE id_order = {sql_literal(order_id)}",
        )
        or 0
    )
    status, _ = api(base, "DELETE", f"/api/orders/{order_id}", driver)
    row = psql_scalar(
        DRILL_DB,
        "SELECT id_state_order FROM orders WHERE id = " + sql_literal(order_id),
    )
    logs_after = int(
        psql_scalar(
            DRILL_DB,
            f"SELECT count(*) FROM order_logs WHERE id_order = {sql_literal(order_id)}",
        )
        or 0
    )
    recorder.add(
        "DLP-02.1",
        "Cancelar un pedido es un borrado lógico y queda en bitácora",
        "PASS"
        if status == 200 and row == "CO" and logs_after > logs_before
        else "FAIL",
        "HTTP 200, fila conservada, estado CO y nuevo registro en order_logs",
        {
            "http_status": status,
            "order_id": order_id,
            "state_after": row,
            "order_logs_before": logs_before,
            "order_logs_after": logs_after,
            "cancelled_by": "rol conductor",
        },
        "dlp02.json",
    )

    created_entities = {}
    user_email = f"drill.dlp.{stamp}@example.test"
    status, created = api(
        base,
        "POST",
        "/api/users",
        driver,
        {
            "firstName": "Drill",
            "lastName": "DLP",
            "email": user_email,
            "password": "Drill1234!",
        },
    )
    user_id = created["data"]["id"] if status == 200 else None
    api(base, "DELETE", f"/api/users/{user_id}", driver)
    user_state = psql_scalar(
        DRILL_DB,
        "SELECT active::text FROM users WHERE id = " + sql_literal(user_id),
    )
    created_entities["user"] = {"id": user_id, "active_after_delete": user_state}

    status, created = api(
        base,
        "POST",
        "/api/stores",
        driver,
        {
            "name": f"Drill Store {stamp}",
            "phone": "555-0100",
            "location": {
                "address": "Calle de Prueba 1",
                "latitude": 32.46,
                "longitude": -116.98,
            },
        },
    )
    store_test_id = created["data"]["id"] if status == 200 else None
    api(base, "DELETE", f"/api/stores/{store_test_id}", driver)
    store_state = psql_scalar(
        DRILL_DB,
        "SELECT active::text FROM stores WHERE id = " + sql_literal(store_test_id),
    )
    created_entities["store"] = {"id": store_test_id, "active_after_delete": store_state}

    status, created = api(
        base,
        "POST",
        "/api/routes",
        driver,
        {"name": f"Drill Route {stamp}", "deliverDays": [1], "stores": []},
    )
    route_id = created["data"]["id"] if status == 200 else None
    api(base, "DELETE", f"/api/routes/{route_id}", driver)
    route_state = psql_scalar(
        DRILL_DB,
        "SELECT active::text FROM routes WHERE id = " + sql_literal(route_id),
    )
    created_entities["route"] = {"id": route_id, "active_after_delete": route_state}

    status, created = api(
        base,
        "POST",
        "/api/trucks",
        driver,
        {
            "brand": "Drill",
            "model": "T1",
            "licensePlate": f"DRL-{stamp}",
            "idStateTruck": "AV",
        },
    )
    truck_id = created["data"]["id"] if status == 200 else None
    api(base, "DELETE", f"/api/trucks/{truck_id}", driver)
    truck_state = psql_scalar(
        DRILL_DB,
        "SELECT id_state_truck FROM trucks WHERE id = " + sql_literal(truck_id),
    )
    truck_logs = int(
        psql_scalar(
            DRILL_DB,
            f"SELECT count(*) FROM truck_logs WHERE id_truck = {sql_literal(truck_id)}",
        )
        or 0
    )
    created_entities["truck"] = {
        "id": truck_id,
        "state_after_delete": truck_state,
        "truck_logs": truck_logs,
    }

    logical_ok = (
        user_state == "false"
        and store_state == "false"
        and route_state == "false"
        and truck_state == "OS"
        and truck_logs >= 1
    )
    write_json(evidence / "dlp02_entities.json", created_entities)
    recorder.add(
        "DLP-02.2",
        "Usuario, tienda, ruta y camión se desactivan sin borrar la fila",
        "PASS" if logical_ok else "FAIL",
        "active=false / estado OS conservando la fila original",
        created_entities,
        "dlp02_entities.json",
    )

    occurrences = []
    for path in sorted((REPO_ROOT / "backend" / "app" / "routers").glob("*.py")):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "DELETE FROM" in line:
                occurrences.append(
                    {
                        "file": f"backend/app/routers/{path.name}",
                        "line": number,
                        "statement": line.strip(),
                    }
                )
    recorder.add(
        "DLP-02.3",
        "Los endpoints HTTP no ejecutan borrados físicos",
        "PASS" if not occurrences else "FAIL",
        "0 sentencias DELETE FROM en backend/app/routers",
        {
            "delete_from_occurrences": occurrences,
            "scope_note": (
                "El único caso es el reemplazo transaccional de route_stores "
                "en la actualización de rutas; no conserva historial de asignaciones."
                if occurrences
                else "Sin borrados físicos en manejadores HTTP"
            ),
        },
        "dlp02.json",
    )

    audit_columns = psql_scalar(
        DRILL_DB,
        "SELECT coalesce(string_agg(table_name || '.' || column_name, ','), '') "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' "
        "AND table_name IN ('order_logs', 'truck_logs', 'trip_logs', 'alerts') "
        "AND (column_name ILIKE '%user%' OR column_name ILIKE '%actor%')",
    )
    audit_table = psql_scalar(
        DRILL_DB,
        "SELECT coalesce(to_regclass('public.audit_log')::text, '')",
    )
    recorder.add(
        "DLP-02.4",
        "Las bitácoras identifican al actor de cada cambio",
        "PASS" if audit_columns or audit_table else "FAIL",
        "Columna de usuario/actor en las bitácoras o tabla audit_log",
        {
            "actor_columns_found": audit_columns,
            "audit_log_table": audit_table or None,
            "gap": "No se registra quién canceló, desactivó o modificó el dato",
        },
        "dlp02.json",
    )

    target_order = psql_scalar(
        DRILL_DB,
        "SELECT o.id FROM orders o "
        "WHERE EXISTS (SELECT 1 FROM order_logs l WHERE l.id_order = o.id) "
        "AND NOT EXISTS (SELECT 1 FROM trip_orders t WHERE t.order_id = o.id) "
        "ORDER BY o.id LIMIT 1",
    )
    original = psql_scalar(
        DRILL_DB,
        "SELECT id || '|' || date::text || '|' || coalesce(delivered::text, '') || '|' || "
        "coalesce(id_created_by_user, '') || '|' || id_store || '|' || id_state_order "
        "FROM orders WHERE id = " + sql_literal(target_order),
    )
    attempt = psql(
        DRILL_DB,
        "DELETE FROM orders WHERE id = " + sql_literal(target_order),
        check=False,
    )
    blocked_by_fk = (
        attempt.returncode != 0
        and "foreign key" in (attempt.stderr or "").lower()
    )
    recorder.add(
        "DLP-02.5",
        "La integridad referencial impide borrar un pedido con bitácora",
        "PASS" if blocked_by_fk else "FAIL",
        "Violación de llave foránea al intentar DELETE físico",
        {
            "order_id": target_order,
            "blocked": blocked_by_fk,
            "error": (attempt.stderr or "").strip()[:240],
        },
        "dlp02.json",
    )

    psql(
        DRILL_DB,
        "DELETE FROM order_logs WHERE id_order = " + sql_literal(target_order) + "; "
        "DELETE FROM orders WHERE id = " + sql_literal(target_order) + ";",
    )
    lost = psql_scalar(
        DRILL_DB,
        "SELECT count(*) FROM orders WHERE id = " + sql_literal(target_order),
    )
    recorder.add(
        "DLP-02.6",
        "Un borrado físico deliberado sí destruye la información",
        "FAIL" if lost == "0" else "PASS",
        "La información debería sobrevivir o bloquearse",
        {"order_id": target_order, "rows_after_hard_delete": int(lost or 0)},
        "dlp02.json",
    )

    recovery = restore_database(dr_dump, RECOVERY_DB, drop=True)
    recovered = psql_scalar(
        RECOVERY_DB,
        "SELECT id || '|' || date::text || '|' || coalesce(delivered::text, '') || '|' || "
        "coalesce(id_created_by_user, '') || '|' || id_store || '|' || id_state_order "
        "FROM orders WHERE id = " + sql_literal(target_order),
    )
    recorder.add(
        "DLP-02.7",
        "El dato destruido se recupera desde el respaldo",
        "PASS" if recovered == original and recovered else "FAIL",
        "Fila restaurada idéntica a la original",
        {
            "order_id": target_order,
            "recovered": bool(recovered),
            "restore_seconds": recovery["seconds"],
            "matches_original": recovered == original,
        },
        "dlp02.json",
    )

    psql("postgres", f'DROP DATABASE IF EXISTS "{RECOVERY_DB}" WITH (FORCE)', check=False)
    return {
        "order_id": order_id,
        "target_order": target_order,
        "entities": created_entities,
        "audit_columns": audit_columns,
        "hard_delete_lost": lost == "0",
        "recovered": recovered == original,
    }


def test_dr02(
    recorder: Recorder, baseline: dict, dr_dump: str, evidence: Path, base: str
) -> dict:
    started = time.perf_counter()
    psql("postgres", f'DROP DATABASE IF EXISTS "{DRILL_DB}" WITH (FORCE)')
    exists = psql_scalar(
        "postgres", f"SELECT count(*) FROM pg_database WHERE datname = '{DRILL_DB}'"
    )
    recorder.add(
        "DR-02.1",
        "Simulación de pérdida total de la base de práctica",
        "PASS" if exists == "0" else "FAIL",
        "Base de datos eliminada por completo",
        {"database": DRILL_DB, "exists_after_drop": exists == "1"},
        "dr02.json",
    )

    restore = restore_database(dr_dump, DRILL_DB, drop=False)
    healthy = wait_health(base, timeout=60)
    token = login(base, ADMIN_EMAIL, ADMIN_PASSWORD)
    status, _ = api(base, "GET", "/api/dashboard/summary", token)
    elapsed = round(time.perf_counter() - started, 2)

    restored = database_checksums(DRILL_DB)
    comparison = compare_checksums(baseline, restored)
    write_json(evidence / "checksums_restored_dr02.json", restored)
    recorder.add(
        "DR-02.2",
        "Recuperación completa del servicio y de los datos",
        "PASS"
        if healthy and status == 200 and comparison["match"]
        else "FAIL",
        "Health 200, login/dashboard 200 y checksums idénticos",
        {
            "healthy": healthy,
            "dashboard_status": status,
            "checksums_match": comparison["match"],
            "restore_seconds": restore["seconds"],
            "differences": comparison["differences"],
        },
        "checksums_restored_dr02.json",
    )

    recorder.add(
        "DR-02.3",
        "RTO medido dentro de la meta",
        "PASS" if elapsed <= RTO_TARGET_SECONDS else "FAIL",
        f"RTO <= {RTO_TARGET_SECONDS} segundos para el volumen actual",
        {"rto_seconds": elapsed, "target_seconds": RTO_TARGET_SECONDS},
        "dr02.json",
    )

    backup_created = datetime.fromisoformat(
        json.loads((evidence / "backup_dr01.json").read_text(encoding="utf-8"))[
            "created_at"
        ]
    )
    disaster_at = datetime.now(timezone.utc)
    rpo_minutes = round((disaster_at - backup_created).total_seconds() / 60, 2)
    recorder.add(
        "DR-02.4",
        "RPO documentado (ventana de pérdida potencial)",
        "INFO",
        "RPO definido por la frecuencia de respaldos",
        {
            "last_backup": backup_created.isoformat(),
            "disaster_at": disaster_at.isoformat(),
            "rpo_minutes": rpo_minutes,
            "note": "Sin WAL archiving el RPO es el tiempo desde el último respaldo",
        },
        "dr02.json",
    )
    write_json(
        evidence / "rto_rpo.json",
        {"rto_seconds": elapsed, "rpo_minutes": rpo_minutes},
    )
    return {
        "rto_seconds": elapsed,
        "rpo_minutes": rpo_minutes,
        "healthy": healthy,
        "dashboard_status": status,
        "comparison": comparison,
    }


def summary_markdown(metadata: dict, recorder: Recorder) -> str:
    counts = recorder.counts()
    lines = [
        "# Resultados de pruebas DLP y DRP — Frostbase",
        "",
        f"- **Fecha de ejecución:** {metadata['generated_at']}",
        f"- **Commit:** `{metadata['commit']}`",
        f"- **Equipo:** {metadata['environment']['platform']}",
        f"- **PostgreSQL:** {metadata['environment']['postgres_version']}",
        f"- **Copia de práctica:** `{DRILL_DB}` (API aislada en el puerto {DRILL_PORT})",
        "",
        "## Resumen",
        "",
        f"| Resultado | Cantidad |",
        f"| --- | --- |",
        f"| PASS | {counts.get('PASS', 0)} |",
        f"| FAIL | {counts.get('FAIL', 0)} |",
        f"| INFO | {counts.get('INFO', 0)} |",
        f"| ERROR | {counts.get('ERROR', 0)} |",
        "",
        "## Detalle",
        "",
        "| ID | Prueba | Resultado | Observado |",
        "| --- | --- | --- | --- |",
    ]
    for item in recorder.results:
        observed = item["observed"]
        if isinstance(observed, (dict, list)):
            observed_text = json.dumps(observed, ensure_ascii=False)
        else:
            observed_text = str(observed)
        observed_text = observed_text.replace("|", "\\|")
        if len(observed_text) > 420:
            observed_text = observed_text[:417] + "..."
        lines.append(
            f"| {item['id']} | {item['name']} | **{item['status']}** | {observed_text} |"
        )
    lines.append("")
    return "\n".join(lines)


def safe(recorder: Recorder, prefix: str, function, *args, **kwargs):
    """Ejecuta una prueba y registra un ERROR sin abortar el resto del flujo."""

    try:
        return function(*args, **kwargs)
    except Exception as error:  # pragma: no cover - diagnóstico de la prueba
        recorder.add(
            prefix,
            "Error de ejecución",
            "ERROR",
            "La prueba debe ejecutarse sin excepciones",
            {"error": str(error)},
            "results.json",
        )
        return {"error": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Pruebas DLP y DRP de Frostbase")
    parser.add_argument(
        "--evidence-dir",
        default=str(REPO_ROOT / "docs" / "security" / "evidence" / "2026-11-15"),
        help="Carpeta donde se escriben las evidencias",
    )
    args = parser.parse_args()

    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    recorder = Recorder()

    postgres_version = psql_scalar("postgres", "SHOW server_version").strip()
    metadata = {
        "project": "frostbase-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "postgres_version": postgres_version,
            "db_container": DB_CONTAINER,
            "app_image": APP_IMAGE,
            "network": NETWORK,
        },
        "artifacts": {},
    }

    print("== Preparando copia de práctica ==")
    prep = setup_drill(recorder)
    with app_instance(DRILL_DB, DRILL_PORT, DRILL_APP) as base:
        baseline = database_checksums(DRILL_DB)
        write_json(evidence / "checksums_baseline.json", baseline)
        metadata["artifacts"]["baseline_digest"] = baseline["digest"]

        dr_backup = backup_database(DRILL_DB, label="dr01")
        dr_dump = dr_backup["file"]

        print("== DR-01: respaldo y restauración ==")
        dr01 = safe(recorder, "DR-01", test_dr01, recorder, baseline, evidence, dr_backup)

        print("== DLP-01: control de acceso y exfiltración ==")
        dlp01 = safe(recorder, "DLP-01", test_dlp01, recorder, dr_dump, evidence, base)

        print("== DLP-02: borrado lógico y recuperación ==")
        dlp02 = safe(recorder, "DLP-02", test_dlp02, recorder, dr_dump, evidence, base)

        print("== DR-02: desastre total y RTO ==")
        dr02 = safe(recorder, "DR-02", test_dr02, recorder, baseline, dr_dump, evidence, base)

    # Limpieza de bases desechables (la copia frostbase_drill se conserva).
    psql("postgres", f'DROP DATABASE IF EXISTS "{RESTORE_DB}" WITH (FORCE)', check=False)

    write_json(evidence / "dr01.json", dr01)
    write_json(evidence / "dlp01.json", dlp01)
    write_json(evidence / "dlp02.json", dlp02)
    write_json(evidence / "dr02.json", dr02)

    payload = {
        **metadata,
        "summary": recorder.counts(),
        "results": recorder.results,
        "details": {
            "preparation": prep,
            "dr01": dr01,
            "dlp01": dlp01,
            "dlp02": dlp02,
            "dr02": dr02,
        },
    }
    write_json(evidence / "results.json", payload)
    (evidence / "summary.md").write_text(
        summary_markdown(metadata, recorder), encoding="utf-8"
    )
    write_json(
        evidence / "environment.json",
        {
            **metadata["environment"],
            "commit": metadata["commit"],
            "generated_at": metadata["generated_at"],
        },
    )

    counts = recorder.counts()
    print("\n== Resultado final ==")
    print(json.dumps(counts, indent=2))
    print(f"Evidencias en: {evidence}")
    return 1 if counts.get("FAIL") or counts.get("ERROR") else 0


if __name__ == "__main__":
    sys.exit(main())
