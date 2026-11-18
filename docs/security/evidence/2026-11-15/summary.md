# Resultados de pruebas DLP y DRP — Frostbase

- **Fecha de ejecución:** 2026-11-16T01:49:26+00:00
- **Commit:** `77d7bc8`
- **Equipo:** Windows-11-10.0.26200-SP0
- **PostgreSQL:** 16.14 (Debian 16.14-1.pgdg13+1)
- **Copia de práctica:** `frostbase_drill` (API aislada en el puerto 8001)

## Resumen

| Resultado | Cantidad |
| --- | --- |
| PASS | 14 |
| FAIL | 7 |
| INFO | 1 |
| ERROR | 0 |

## Detalle

| ID | Prueba | Resultado | Observado |
| --- | --- | --- | --- |
| PREP-01 | Copia de práctica frostbase_drill creada | **PASS** | {"source_database": "frostbase", "drill_database": "frostbase_drill", "source_dump": "C:\\Users\\dell\\Documents\\GitHub\\frostbase-v2\\db-backups\\frostbase_drill_source_20261116T014927Z.dump", "source_sha256": "84cbf084173c5e587854bd68304747f8bd0f6bdb4721fdbf7c1c7b5aa147112f", "restore_seconds": 0.58} |
| DR-01.1 | Respaldo lógico íntegro y verificable | **PASS** | {"file": "C:\\Users\\dell\\Documents\\GitHub\\frostbase-v2\\db-backups\\frostbase_drill_dr01_20261116T014937Z.dump", "size_bytes": 57921, "sha256": "2d08ca48c4c7392a1e92ba6c2fc2aad62542ac5c0793a71d4983923cd311f6b9", "objects": 98} |
| DR-01.2 | Restauración completa sin diferencias | **PASS** | {"restore_seconds": 0.62, "expected_digest": "5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6", "actual_digest": "5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6", "differences": []} |
| DR-01.3 | La base restaurada es funcional para la aplicación | **PASS** | {"server_ok": true, "login_ok": true, "dashboard_status": 200} |
| DLP-01.1 | Acceso anónimo bloqueado en endpoints de datos | **PASS** | {"/api/users": 401, "/api/orders": 401, "/api/readings": 401, "/api/dashboard/summary": 401, "/api/stores": 401, "/api/trucks": 401} |
| DLP-01.2 | Un conductor no puede enumerar usuarios ni ver PII | **FAIL** | {"http_status": 200, "users_returned": 11, "pii_exposed": true, "password_hash_exposed": false, "redacted_sample": [{"email": "a***@logisticarf.com", "phone": "***0207", "birthDate": "***", "isAdmin": false}, {"email": "a***@logisticarf.com", "phone": "***0103", "birthDate": "***", "isAdmin": true}, {"email": "c***@logisticarf.com", "phone": "***0102", "birthDate": "***", "isAdmin": true}]} |
| DLP-01.3 | RBAC en endpoints exclusivos de administrador | **PASS** | {"endpoint": "POST /api/simulator/check", "http_status": 403} |
| DLP-01.4 | Token manipulado rechazado | **PASS** | {"http_status": 401} |
| DLP-01.5 | Documentación de API no expuesta sin autenticación | **FAIL** | {"endpoint": "/openapi.json", "http_status": 200} |
| DLP-01.6 | Base de datos no accesible desde el host con credenciales por defecto | **FAIL** | {"host_db_access": true, "rows_read": "11", "port": 5433} |
| DLP-01.7 | Los respaldos contienen PII en texto claro y sin cifrar | **FAIL** | {"rows_with_email_in_dump": 11, "backup_encrypted": false, "backup_file": "C:\\Users\\dell\\Documents\\GitHub\\frostbase-v2\\db-backups\\frostbase_drill_dr01_20261116T014937Z.dump", "inspection_error": null} |
| DLP-02.1 | Cancelar un pedido es un borrado lógico y queda en bitácora | **PASS** | {"http_status": 200, "order_id": "528798793b204af1be5cf9bf", "state_after": "CO", "order_logs_before": 1, "order_logs_after": 2, "cancelled_by": "rol conductor"} |
| DLP-02.2 | Usuario, tienda, ruta y camión se desactivan sin borrar la fila | **PASS** | {"user": {"id": "e55158ec2b8648da8ce21493", "active_after_delete": "false"}, "store": {"id": "3c3c8db301ca4e0383fa1ab9", "active_after_delete": "false"}, "route": {"id": "3c6a21121d0e465aa114b8d6", "active_after_delete": "false"}, "truck": {"id": "63578b825f694c5a8fb7f10e", "state_after_delete": "OS", "truck_logs": 2}} |
| DLP-02.3 | Los endpoints HTTP no ejecutan borrados físicos | **FAIL** | {"delete_from_occurrences": [{"file": "backend/app/routers/routes.py", "line": 20, "statement": "execute(conn, \"DELETE FROM route_stores WHERE route_id = %s\", (route_id,))"}], "scope_note": "El único caso es el reemplazo transaccional de route_stores en la actualización de rutas; no conserva historial de asignaciones."} |
| DLP-02.4 | Las bitácoras identifican al actor de cada cambio | **FAIL** | {"actor_columns_found": "", "audit_log_table": null, "gap": "No se registra quién canceló, desactivó o modificó el dato"} |
| DLP-02.5 | La integridad referencial impide borrar un pedido con bitácora | **PASS** | {"order_id": "06526aec166d47b4992b5566", "blocked": true, "error": "ERROR:  update or delete on table \"orders\" violates foreign key constraint \"order_logs_id_order_fkey\" on table \"order_logs\"\nDETAIL:  Key (id)=(06526aec166d47b4992b5566) is still referenced from table \"order_logs\"."} |
| DLP-02.6 | Un borrado físico deliberado sí destruye la información | **FAIL** | {"order_id": "06526aec166d47b4992b5566", "rows_after_hard_delete": 0} |
| DLP-02.7 | El dato destruido se recupera desde el respaldo | **PASS** | {"order_id": "06526aec166d47b4992b5566", "recovered": true, "restore_seconds": 0.54, "matches_original": true} |
| DR-02.1 | Simulación de pérdida total de la base de práctica | **PASS** | {"database": "frostbase_drill", "exists_after_drop": false} |
| DR-02.2 | Recuperación completa del servicio y de los datos | **PASS** | {"healthy": true, "dashboard_status": 200, "checksums_match": true, "restore_seconds": 0.96, "differences": []} |
| DR-02.3 | RTO medido dentro de la meta | **PASS** | {"rto_seconds": 2.45, "target_seconds": 120} |
| DR-02.4 | RPO documentado (ventana de pérdida potencial) | **INFO** | {"last_backup": "2026-11-16T01:49:37+00:00", "disaster_at": "2026-11-16T01:50:05.332158+00:00", "rpo_minutes": 0.47, "note": "Sin WAL archiving el RPO es el tiempo desde el último respaldo"} |
