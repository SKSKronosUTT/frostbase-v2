# Resultados de pruebas DLP y DRP — Frostbase

- **Fecha de ejecución:** 2026-11-16T04:05:52+00:00
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
| PREP-01 | Copia de práctica frostbase_drill creada | **PASS** | {"source_database": "frostbase", "drill_database": "frostbase_drill", "source_dump": "C:\\Users\\dell\\Documents\\GitHub\\frostbase-v2\\db-backups\\frostbase_drill_source_20261116T040553Z.dump", "source_sha256": "f604eaf491a55c7a2979ede0820d01729a764d411c4a7982303be4839907cbfd", "restore_seconds": 0.53} |
| DR-01.1 | Respaldo lógico íntegro y verificable | **PASS** | {"file": "C:\\Users\\dell\\Documents\\GitHub\\frostbase-v2\\db-backups\\frostbase_drill_dr01_20261116T040611Z.dump", "size_bytes": 57921, "sha256": "ab027831924f65ede07324325cbbe85a0dad87c68c60e6ffd13b97eb001d7b38", "objects": 98} |
| DR-01.2 | Restauración completa sin diferencias | **PASS** | {"restore_seconds": 1.1, "expected_digest": "5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6", "actual_digest": "5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6", "differences": []} |
| DR-01.3 | La base restaurada es funcional para la aplicación | **PASS** | {"server_ok": true, "login_ok": true, "dashboard_status": 200} |
| DLP-01.1 | Acceso anónimo bloqueado en endpoints de datos | **PASS** | {"/api/users": 401, "/api/orders": 401, "/api/readings": 401, "/api/dashboard/summary": 401, "/api/stores": 401, "/api/trucks": 401} |
| DLP-01.2 | Un conductor no puede enumerar usuarios ni ver PII | **FAIL** | {"http_status": 200, "users_returned": 11, "pii_exposed": true, "password_hash_exposed": false, "redacted_sample": [{"email": "a***@logisticarf.com", "phone": "***0207", "birthDate": "***", "isAdmin": false}, {"email": "a***@logisticarf.com", "phone": "***0103", "birthDate": "***", "isAdmin": true}, {"email": "c***@logisticarf.com", "phone": "***0102", "birthDate": "***", "isAdmin": true}]} |
| DLP-01.3 | RBAC en endpoints exclusivos de administrador | **PASS** | {"endpoint": "POST /api/simulator/check", "http_status": 403} |
| DLP-01.4 | Token manipulado rechazado | **PASS** | {"http_status": 401} |
| DLP-01.5 | Documentación de API no expuesta sin autenticación | **FAIL** | {"endpoint": "/openapi.json", "http_status": 200} |
| DLP-01.6 | Base de datos no accesible desde el host con credenciales por defecto | **FAIL** | {"host_db_access": true, "rows_read": "11", "port": 5433} |
| DLP-01.7 | Los respaldos contienen PII en texto claro y sin cifrar | **FAIL** | {"rows_with_email_in_dump": 11, "backup_encrypted": false, "backup_file": "C:\\Users\\dell\\Documents\\GitHub\\frostbase-v2\\db-backups\\frostbase_drill_dr01_20261116T040611Z.dump", "inspection_error": null} |
| DLP-02.1 | Cancelar un pedido es un borrado lógico y queda en bitácora | **PASS** | {"http_status": 200, "order_id": "5cdf1686fc43492193712fdb", "state_after": "CO", "order_logs_before": 1, "order_logs_after": 2, "cancelled_by": "rol conductor"} |
| DLP-02.2 | Usuario, tienda, ruta y camión se desactivan sin borrar la fila | **PASS** | {"user": {"id": "f714121dd8214580a4f83752", "active_after_delete": "false"}, "store": {"id": "0f9afc7d33f54ee5a44ad680", "active_after_delete": "false"}, "route": {"id": "13f88abdf0b7484abb2e9e94", "active_after_delete": "false"}, "truck": {"id": "2e04e432e36b4f75a73ee239", "state_after_delete": "OS", "truck_logs": 2}} |
| DLP-02.3 | Los endpoints HTTP no ejecutan borrados físicos | **FAIL** | {"delete_from_occurrences": [{"file": "backend/app/routers/routes.py", "line": 20, "statement": "execute(conn, \"DELETE FROM route_stores WHERE route_id = %s\", (route_id,))"}], "scope_note": "El único caso es el reemplazo transaccional de route_stores en la actualización de rutas; no conserva historial de asignaciones."} |
| DLP-02.4 | Las bitácoras identifican al actor de cada cambio | **FAIL** | {"actor_columns_found": "", "audit_log_table": null, "gap": "No se registra quién canceló, desactivó o modificó el dato"} |
| DLP-02.5 | La integridad referencial impide borrar un pedido con bitácora | **PASS** | {"order_id": "06526aec166d47b4992b5566", "blocked": true, "error": "ERROR:  update or delete on table \"orders\" violates foreign key constraint \"order_logs_id_order_fkey\" on table \"order_logs\"\nDETAIL:  Key (id)=(06526aec166d47b4992b5566) is still referenced from table \"order_logs\"."} |
| DLP-02.6 | Un borrado físico deliberado sí destruye la información | **FAIL** | {"order_id": "06526aec166d47b4992b5566", "rows_after_hard_delete": 0} |
| DLP-02.7 | El dato destruido se recupera desde el respaldo | **PASS** | {"order_id": "06526aec166d47b4992b5566", "recovered": true, "restore_seconds": 0.56, "matches_original": true} |
| DR-02.1 | Simulación de pérdida total de la base de práctica | **PASS** | {"database": "frostbase_drill", "exists_after_drop": false} |
| DR-02.2 | Recuperación completa del servicio y de los datos | **PASS** | {"healthy": true, "dashboard_status": 200, "checksums_match": true, "restore_seconds": 1.05, "differences": []} |
| DR-02.3 | RTO medido dentro de la meta | **PASS** | {"rto_seconds": 2.6, "target_seconds": 120} |
| DR-02.4 | RPO documentado (ventana de pérdida potencial) | **INFO** | {"last_backup": "2026-11-16T04:06:22+00:00", "disaster_at": "2026-11-16T04:06:51.064350+00:00", "rpo_minutes": 0.48, "note": "Sin WAL archiving el RPO es el tiempo desde el último respaldo"} |
