# Pruebas de Prevención de Pérdida de Datos (DLP) y Plan de Recuperación ante Desastres (DRP)

**Proyecto:** Frostbase v2 — Sistema de monitoreo y gestión de camiones refrigerados
**Fecha de ejecución:** 15 de noviembre de 2026 (UTC: 2026-11-16)
**Commit analizado:** `77d7bc8`
**Entorno:** Windows 11, Docker Desktop, PostgreSQL 16.14, FastAPI
**Copia de práctica:** base de datos `frostbase_drill` + API aislada temporal en `http://localhost:8001` (el contenedor se elimina al finalizar; la base se conserva para inspección)

---

## 1. Objetivo y alcance

El objetivo es comprobar, con evidencia reproducible, que Frostbase cuenta con procedimientos para:

1. **Proteger la información** frente a accesos no autorizados, exposición de datos personales y destrucción accidental (DLP).
2. **Restaurar la información y el servicio** después de una pérdida total o parcial de la base de datos (DRP).

El alcance cubre el backend FastAPI, el esquema PostgreSQL, la configuración de Docker Compose y el procedimiento de respaldo/restauración. Las pruebas se ejecutaron sobre una **copia de práctica** para no alterar la base principal `frostbase`.

### Fuera de alcance

- Pruebas de penetración sobre la red perimetral o el host.
- Cifrado en reposo a nivel de disco/volumen (no implementado en el proyecto).
- Recuperación punto en el tiempo (PITR) con WAL archiving (no implementada).
- Pruebas de carga, disponibilidad multizona o replicación.

---

## 2. Entorno de ejecución

| Elemento | Valor |
| --- | --- |
| Contenedor de base de datos | `frostbase-db` (`postgres:16`) |
| Contenedor de aplicación | `frostbase-app` (`frostbase-v2-app:latest`) |
| Volumen de datos | `frostbase-v2_frostbase_pgdata` |
| Red Docker | `frostbase-v2_default` |
| Base principal | `frostbase` (solo lectura para el respaldo inicial) |
| Base de práctica | `frostbase_drill` |
| API de práctica | `frostbase-drill-app`, puerto `8001`, `AUTO_SEED=false` |
| API de verificación de restore | `frostbase-restore-app`, puerto `8002`, `AUTO_SEED=false` |
| Credenciales de prueba | Administrador `mgonzalez@logisticarf.com`; conductor `rsilva@logisticarf.com` |

> `AUTO_SEED=false` es obligatorio en las instancias de prueba: si la base quedara vacía, el arranque normal volvería a sembrar datos de demostración y podría **enmascarar una restauración fallida**.

---

## 3. Arquitectura de la prueba

```
┌──────────────────────────┐        pg_dump -Fc        ┌──────────────────────────┐
│  frostbase (principal)   │ ────────────────────────► │  db-backups/*.dump       │
│  contenedor frostbase-db │                           │  SHA-256 + metadatos     │
└──────────────────────────┘                           └────────────┬─────────────┘
                                                                     │ pg_restore
                                                                     ▼
┌──────────────────────────┐        puerto 8001         ┌──────────────────────────┐
│  frostbase-drill-app     │ ◄───────────────────────── │  frostbase_drill         │
│  API aislada de pruebas  │                            │  copia desechable        │
└──────────────────────────┘                            └──────────────────────────┘
                                                                     │
                                             DROP DATABASE ──────────┘
                                                                     │ pg_restore
                                                                     ▼
                                                            recuperación + RTO
```

La copia `frostbase_drill` se creó restaurando un respaldo de `frostbase`. Todas las pruebas destructivas (borrados, `DROP DATABASE`) se ejecutaron únicamente sobre la copia. La base principal solo recibió operaciones de lectura (`pg_dump` y un `SELECT count(*)` para comprobar la exposición del puerto 5433).

---

## 4. Resumen ejecutivo

| Resultado | Cantidad |
| --- | ---: |
| **PASS** | 14 |
| **FAIL** | 7 |
| **INFO** | 1 |
| **ERROR** | 0 |
| **Total** | 22 |

### Conclusión

- **DRP:** el respaldo lógico y la restauración **funcionan** y son verificables. La restauración completa reprodujo exactamente las 20 tablas (mismo digest y mismos checksums) y la base restaurada fue funcional para la API (health, login y dashboard). El RTO medido fue de **2.45 segundos** para el volumen actual y el RPO de la práctica fue de **0.47 minutos** porque el respaldo se tomó inmediatamente antes del desastre.
- **DLP:** existen controles sólidos de autenticación, hashing de contraseñas, bloqueo de acceso anónimo, borrado lógico y bitácoras de cambios. Sin embargo, se identificaron **7 pruebas FAIL** (brechas y riesgos), entre ellas la exposición de PII a cualquier usuario autenticado, el acceso directo a PostgreSQL con credenciales por defecto y la ausencia de cifrado en los respaldos.
- **Riesgo principal:** el proyecto **no tiene todavía un procedimiento operativo de respaldos programados, retención, cifrado y restauración documentado**. Los scripts entregados cubren la mecánica, pero falta incorporarlos a una operación real (cron/scheduler, almacenamiento externo, monitoreo y pruebas periódicas).

---

## 5. Pruebas DLP

### DLP-01 — Control de acceso y exfiltración de información

**Objetivo:** verificar que la información solo es accesible a usuarios autorizados y que no se filtran credenciales, PII ni la base de datos.

**Procedimiento ejecutado:**

1. Consultar sin token los endpoints `/api/users`, `/api/orders`, `/api/readings`, `/api/dashboard/summary`, `/api/stores` y `/api/trucks`.
2. Autenticarse como conductor (`rsilva@logisticarf.com`) y solicitar `GET /api/users`.
3. Con el token del conductor, invocar `POST /api/simulator/check` (endpoint exclusivo de administrador).
4. Alterar el cuerpo firmado del token y llamar `GET /api/auth/me`.
5. Consultar `GET /openapi.json` sin autenticación.
6. Desde un contenedor externo al stack, conectarse a PostgreSQL a través del puerto publicado en el host (`localhost:5433`) con las credenciales por defecto (`frostbase`/`frostbase`) y leer `users`.
7. Inspeccionar el respaldo con `pg_restore` y contar cuántos correos electrónicos contiene en texto claro.

**Resultados:**

| ID | Prueba | Resultado | Evidencia |
| --- | --- | --- | --- |
| DLP-01.1 | Acceso anónimo bloqueado en endpoints de datos | **PASS** — los 6 endpoints respondieron `401` | `dlp01.json` |
| DLP-01.2 | Un conductor no puede enumerar usuarios ni ver PII | **FAIL** — `GET /api/users` respondió `200` y devolvió 11 usuarios con `email`, `phone` y `birthDate` | `dlp01_users_sample.json` |
| DLP-01.3 | RBAC en endpoints exclusivos de administrador | **PASS** — `POST /api/simulator/check` respondió `403` | `dlp01.json` |
| DLP-01.4 | Token manipulado rechazado | **PASS** — `GET /api/auth/me` respondió `401` | `dlp01.json` |
| DLP-01.5 | Documentación de API no expuesta sin autenticación | **FAIL** — `/openapi.json` respondió `200` | `dlp01.json` |
| DLP-01.6 | Base de datos no accesible desde el host con credenciales por defecto | **FAIL** — conexión exitosa al puerto `5433` y lectura de 11 filas de `users` | `dlp01.json` |
| DLP-01.7 | Los respaldos contienen PII en texto claro y sin cifrar | **FAIL** — 11 correos legibles en el dump, respaldo sin cifrar | `backup_dr01.json` |

**Datos observados (redactados):**

```json
{
  "http_status": 200,
  "users_returned": 11,
  "pii_exposed": true,
  "password_hash_exposed": false,
  "redacted_sample": [
    {"email": "a***@logisticarf.com", "phone": "***0207", "birthDate": "***", "isAdmin": false},
    {"email": "a***@logisticarf.com", "phone": "***0103", "birthDate": "***", "isAdmin": true}
  ]
}
```

**Análisis:**

- El control de autenticación es correcto: sin token no se accede a datos y un token alterado se rechaza.
- El `password_hash` **no** se expone (correcto), pero el endpoint devuelve PII completa a cualquier rol.
- El endpoint de simulación sí está protegido por rol, pero el resto de escrituras no (ver DLP-02).
- La base está publicada en `0.0.0.0:5433` y usa la contraseña por defecto de `docker-compose.yml`. Cualquier proceso del host o de la red local puede volcar toda la base.
- Los respaldos son útiles para DR, pero al no estar cifrados se convierten en un nuevo vector de fuga de PII.

---

### DLP-02 — Borrado lógico, integridad y trazabilidad

**Objetivo:** comprobar que las operaciones destructivas no eliminan información de forma irreversible y que queda un registro atribuible.

**Procedimiento ejecutado:**

1. Crear un pedido como conductor y cancelarlo con `DELETE /api/orders/{id}`. Verificar la fila y `order_logs`.
2. Crear y eliminar (como conductor) un usuario, una tienda, una ruta y un camión. Verificar que las filas permanecen con `active=false` o estado `OS`.
3. Buscar sentencias `DELETE FROM` en `backend/app/routers`.
4. Consultar si las bitácoras guardan el actor (`user_id`/`actor`) o si existe una tabla `audit_log`.
5. Intentar un `DELETE FROM orders` directo sobre un pedido con bitácora, para comprobar la protección de llave foránea.
6. Borrar deliberadamente la bitácora y el pedido (simulación de pérdida).
7. Restaurar el respaldo en `frostbase_restore_recovery` y verificar que el pedido reaparece idéntico.

**Resultados:**

| ID | Prueba | Resultado | Evidencia |
| --- | --- | --- | --- |
| DLP-02.1 | Cancelar un pedido es borrado lógico y queda en bitácora | **PASS** — `200`, estado `CO`, fila conservada, `order_logs` pasó de 1 a 2 | `dlp02.json` |
| DLP-02.2 | Usuario, tienda, ruta y camión se desactivan sin borrar la fila | **PASS** — `active=false` / estado `OS`, filas conservadas | `dlp02_entities.json` |
| DLP-02.3 | Los endpoints HTTP no ejecutan borrados físicos | **FAIL** — 1 `DELETE FROM route_stores` en `routes.py:20` | `dlp02.json` |
| DLP-02.4 | Las bitácoras identifican al actor de cada cambio | **FAIL** — no hay columnas de actor ni tabla `audit_log` | `dlp02.json` |
| DLP-02.5 | La integridad referencial impide borrar un pedido con bitácora | **PASS** — PostgreSQL bloqueó el `DELETE` por FK `order_logs_id_order_fkey` | `dlp02.json` |
| DLP-02.6 | Un borrado físico deliberado sí destruye la información | **FAIL** — tras borrar `order_logs` y `orders`, la fila desapareció | `dlp02.json` |
| DLP-02.7 | El dato destruido se recupera desde el respaldo | **PASS** — la fila restaurada coincidió exactamente con la original | `dlp02.json` |

**Análisis:**

- El borrado lógico está bien implementado en las entidades principales (`users`, `stores`, `routes`, `orders`, `trucks`).
- La llave foránea de `order_logs` protege contra un borrado accidental de pedidos, pero **no sustituye un respaldo**: un usuario con acceso SQL puede borrar primero la bitácora y luego el pedido.
- El único borrado físico en routers es el reemplazo transaccional de `route_stores` al actualizar una ruta. No destruye la ruta, pero **pierde el historial de asignaciones**; severidad baja.
- La brecha más relevante es la **falta de atribución**: las bitácoras no registran quién realizó el cambio. Tampoco se auditan cambios de usuarios, tiendas ni parámetros.
- La recuperación desde respaldo funcionó, lo que demuestra que el respaldo es el control compensatorio efectivo.

---

## 6. Pruebas DRP

### DR-01 — Respaldo lógico y restauración completa

**Objetivo:** demostrar que un respaldo íntegro permite reconstruir exactamente la base de datos y que la aplicación funciona sobre ella.

**Procedimiento ejecutado:**

1. Calcular la línea base de las 20 tablas: filas y checksum MD5 determinista, más un digest global.
2. Generar el respaldo con `pg_dump -Fc`, copiarlo al host y validarlo con `pg_restore --list`.
3. Calcular SHA-256 y registrar tamaño, fecha y número de objetos.
4. Restaurar el respaldo en la base `frostbase_restore` con `--single-transaction --no-owner --no-acl`.
5. Comparar checksums de las 20 tablas contra la línea base.
6. Levantar `frostbase-restore-app` (puerto 8002, `AUTO_SEED=false`) contra la base restaurada y validar `/api/health`, login de administrador y `/api/dashboard/summary`.

**Resultados:**

| ID | Prueba | Resultado | Evidencia |
| --- | --- | --- | --- |
| DR-01.1 | Respaldo lógico íntegro y verificable | **PASS** — 57 921 bytes, 98 objetos, SHA-256 `2d08ca48…11f6b9`, validado con `pg_restore --list` | `backup_dr01.json` |
| DR-01.2 | Restauración completa sin diferencias | **PASS** — digest `5a0341b9…92e6` idéntico, 0 diferencias en 20 tablas, restore en 0.62 s | `checksums_restored_dr01.json` |
| DR-01.3 | La base restaurada es funcional para la aplicación | **PASS** — health 200, login OK, dashboard 200 | `dr01.json` |

**Comparación de checksums:**

```text
Digest línea base:   5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6
Digest restaurado:   5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6
Diferencias:         0
```

**Análisis:** el respaldo y la restauración son correctos y deterministas. La aplicación no depende de estado en memoria ni de configuraciones externas distintas a `DATABASE_URL`, por lo que una base restaurada es plenamente funcional.

---

### DR-02 — Pérdida total de la base y recuperación del servicio

**Objetivo:** simular un desastre que elimina por completo la base de práctica, medir el tiempo de recuperación (RTO) y documentar la ventana de pérdida (RPO).

**Procedimiento ejecutado:**

1. Registrar el instante `T0`.
2. Ejecutar `DROP DATABASE frostbase_drill WITH (FORCE)` y confirmar que la base ya no existe.
3. Restaurar el respaldo `dr01` en `frostbase_drill`.
4. Esperar `/api/health`, autenticar al administrador y consultar `/api/dashboard/summary`.
5. Comparar los checksums restaurados contra la línea base.
6. Registrar `T1` y calcular `RTO = T1 − T0`; documentar `RPO` como tiempo desde el último respaldo.

**Resultados:**

| ID | Prueba | Resultado | Evidencia |
| --- | --- | --- | --- |
| DR-02.1 | Simulación de pérdida total de la base de práctica | **PASS** — `frostbase_drill` eliminada (`WITH FORCE`) | `dr02.json` |
| DR-02.2 | Recuperación completa del servicio y de los datos | **PASS** — health 200, dashboard 200, checksums idénticos, restore en 0.96 s | `checksums_restored_dr02.json` |
| DR-02.3 | RTO medido dentro de la meta | **PASS** — **2.45 s** (meta: 120 s) | `dr02.json` |
| DR-02.4 | RPO documentado | **INFO** — 0.47 min en la práctica; sin WAL archiving el RPO real es la frecuencia de respaldo | `rto_rpo.json` |

**Lectura correcta del RTO/RPO:**

- El **RTO de 2.45 s** corresponde a este volumen de práctica (≈58 KB de dump, 20 tablas, 300 lecturas) y a un entorno local. No debe extrapolarse a producción sin una prueba de carga y almacenamiento real.
- El **RPO de 0.47 min** es artificial: el respaldo se tomó justo antes del desastre para la prueba. En operación, el RPO será **el intervalo entre respaldos** (por ejemplo, 24 h si es diario) mientras `archive_mode=off`.
- Para reducir el RPO a minutos u horas se requiere **WAL archiving + base backup** (PITR), que hoy no está configurado.

---

## 7. Scripts entregados

Todos los scripts están en `backend/scripts/` y usan la CLI de Docker, por lo que no requieren un cliente PostgreSQL instalado en el host.

### 7.1 `db_tools.py`

Utilidades compartidas:

- `psql()` / `psql_scalar()`: ejecuta SQL dentro del contenedor.
- `database_checksums()`: calcula filas y checksum MD5 por tabla + digest global.
- `backup_database()`: `pg_dump -Fc`, checksums del origen, copia al host, valida con `pg_restore --list`, cifra opcionalmente con AES-256-GCM, espeja a una ubicación externa y escribe metadatos `.json`.
- `restore_database()`: descifra si es necesario y restaura en una base destino con `--single-transaction`.
- `verify_backup()`: restaura en una base temporal y compara el digest contra la huella del origen.
- `prune_backups()`: aplica retención por antigüedad y cantidad mínima.
- `compare_checksums()`: compara dos conjuntos de checksums y reporta diferencias.
- `encrypt_backup()` / `decrypt_backup()`: AES-256-GCM con PBKDF2-HMAC-SHA256 (600 000 iteraciones).

### 7.2 `db_backup.py`

```bash
# Respaldo simple
python backend/scripts/db_backup.py --db frostbase --label nightly

# Respaldo endurecido: cifrado, retención, espejo y verificación
python backend/scripts/db_backup.py --db frostbase --label nightly \
  --encrypt --passphrase-file /etc/frostbase/backup.pass \
  --mirror-dir /mnt/offsite/frostbase \
  --prune --retention-days 30 --keep-last 7 --verify
```

Salida: `db-backups/frostbase_nightly_<timestamp>.dump[.enc]` + `.json` con SHA-256, tamaño, objetos, fecha, `encrypted`, `source_checksums` y `mirror`. Con `--encrypt` el `.dump` en claro se elimina por defecto.

### 7.3 `db_checksum.py`

```bash
python backend/scripts/db_checksum.py --db frostbase_drill \
  --output docs/security/evidence/2026-11-15/checksums_baseline.json

python backend/scripts/db_checksum.py --db frostbase_restore \
  --compare docs/security/evidence/2026-11-15/checksums_baseline.json
```

Devuelve código de salida `1` si la comparación no coincide (útil para CI).

### 7.4 `db_restore.py`

```bash
python backend/scripts/db_restore.py \
  --dump db-backups/frostbase_drill_dr01_20261116T014937Z.dump \
  --target frostbase_restore \
  --compare docs/security/evidence/2026-11-15/checksums_baseline.json
```

### 7.5 `run_dlp_drp_tests.py`

```bash
python backend/scripts/run_dlp_drp_tests.py \
  --evidence-dir docs/security/evidence/2026-11-15
```

Orquesta las cuatro pruebas, prepara la copia de práctica, genera las evidencias y devuelve código de salida `1` si hay `FAIL` o `ERROR`. Es el comando reproducible que produjo este documento.

**Requisitos:** Docker en ejecución, contenedor `frostbase-db` arriba, imagen `frostbase-v2-app:latest` construida y red `frostbase-v2_default` disponible. Si los nombres cambian, se ajustan con las variables `FROSTBASE_DB_CONTAINER`, `FROSTBASE_APP_IMAGE` y `FROSTBASE_NETWORK`.

### 7.6 `db_verify.py`

```bash
python backend/scripts/db_verify.py \
  --dump db-backups/frostbase_nightly_<ts>.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass
```

Restaura el respaldo en una base temporal (`frostbase_verify`) y compara el digest contra `source_checksums`. Devuelve `0` si `verified: true` y `1` si hay diferencias. Es la verificación más fuerte: no solo comprueba que el archivo se lea, sino que reconstruye exactamente el estado del origen.

### 7.7 `db_prune.py`

```bash
python backend/scripts/db_prune.py --dir db-backups --database frostbase
python backend/scripts/db_prune.py --dir db-backups --database frostbase \
  --retention-days 30 --keep-last 7 --yes
```

Conserva siempre los más recientes y elimina los que superan la retención. Por defecto simula; `--yes` aplica los cambios.

### 7.8 `db_recover.py`

```bash
python backend/scripts/db_recover.py \
  --dump db-backups/frostbase_nightly_<ts>.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass \
  --target frostbase --yes
```

Recuperación guiada: respaldo previo (`pre_restore`), parada de la app, restauración, comparación de checksums, arranque y health check. Si falla, revierte automáticamente al respaldo previo. `--dry-run` muestra el plan y `--yes` confirma la operación destructiva.

### 7.9 `db_basebackup.py`

```bash
python backend/scripts/db_basebackup.py --label weekly
```

Respaldo físico con `pg_basebackup -Ft -z -X stream`. Genera `.tar.gz` + `.json` con `archive_mode`, `wal_level` y `pitr_ready`. Con `archive_mode=off` es una copia física completa, pero no habilita PITR; para eso use `docker-compose.backup.yml`.

### 7.10 Plantillas de programación

- `deploy/cron/frostbase-backup` + `deploy/cron/frostbase-backup.sh`
- `deploy/systemd/frostbase-backup.service` + `.timer` + `backup.env.example`
- `deploy/windows/frostbase-backup.ps1` + `deploy/windows/register-frostbase-backup.ps1`

La operación completa se documenta en [`backup-restore-guide.md`](backup-restore-guide.md).

### 7.11 `capture_evidence.ps1`

```powershell
# Ejecutar la suite y preparar los bloques de captura
.\backend\scripts\capture_evidence.ps1 -EvidenceDir docs\security\evidence\2026-11-16-demo

# Tras capturar los PNG, regenerar bloques y manifiesto sin repetir la suite
.\backend\scripts\capture_evidence.ps1 -EvidenceDir docs\security\evidence\2026-11-16-demo -SkipRun
```

Ejecuta la suite una sola vez, guarda `run.log`, filtra los bloques DLP-01, DLP-02, DR-01 y DR-02 en `captures\*.txt` y genera `manifest.json` y `hashes.txt` con SHA-256 de toda la evidencia. Cada bloque incluye fecha UTC, commit, comando y hash de `results.json`, de modo que las cuatro capturas se pueden vincular a la misma ejecución. `-AutoScreenshot` captura la ventana en primer plano; `-SkipRun` reutiliza el log y regenera bloques y manifiesto, incorporando los PNG añadidos manualmente. El código de salida `1` de la suite no se considera un error del script: indica que hay hallazgos `FAIL`.

---

## 8. Hallazgos y acciones correctivas

| # | Hallazgo | Severidad | Evidencia | Acción recomendada |
| --- | --- | --- | --- | --- |
| 1 | PostgreSQL expuesto en `0.0.0.0:5433` con contraseña por defecto `frostbase` | **Crítica** | DLP-01.6 | Publicar solo en `127.0.0.1:5433`, cambiar `POSTGRES_PASSWORD` y eliminar el valor por defecto de `docker-compose.yml` |
| 2 | Cualquier usuario autenticado puede enumerar todos los usuarios y ver PII | **Alta** | DLP-01.2 | Restringir `GET /api/users` a administradores y usar DTOs mínimos para conductores |
| 3 | Respaldos sin cifrar con PII en texto claro | **Alta** | DLP-01.7 | **Mitigado:** `db_backup.py --encrypt` usa AES-256-GCM con PBKDF2; el `.dump` en claro se elimina (sección 14) |
| 4 | Sin procedimiento operativo de respaldo, retención y restauración | **Alta** | DR-01 / DR-02 | **Mitigado:** retención, espejo verificado, `db_verify.py`, `db_recover.py` y plantillas de programación en `deploy/` (sección 14) |
| 5 | Bitácoras sin actor ni tabla de auditoría | **Media** | DLP-02.4 | Añadir `audit_log(actor_id, action, entity, entity_id, before, after, ip, at)` y registrar login/cambios |
| 6 | Escrituras sin rol administrador (conductores pueden crear/editar/borrar) | **Media** | DLP-02.1 / DLP-02.2 | Exigir `current_admin` en POST/PUT/DELETE de usuarios, tiendas, camiones, rutas y parámetros |
| 7 | `DELETE FROM route_stores` sin historial | **Baja** | DLP-02.3 | Mantener historial de asignaciones o marcar el reemplazo como operación auditada |
| 8 | `/docs` y `/openapi.json` públicos | **Baja** | DLP-01.5 | Deshabilitar en producción o proteger con autenticación |
| 9 | Sin PITR (`archive_mode=off`) | **Media** | DR-02.4 | Activar WAL archiving y base backups programados para RPO de minutos |
| 10 | Un borrado físico con acceso SQL destruye datos | **Inherente** | DLP-02.6 | Mitigado por respaldos verificados y principio de mínimo privilegio; separar credenciales de aplicación y DBA |

### Prioridad sugerida

1. **Inmediata:** hallazgos 1 y 4 (exposición de BD y ausencia de respaldos operativos).
2. **Corto plazo:** hallazgos 2, 3, 5 y 6.
3. **Mediano plazo:** hallazgos 7, 8 y 9.

---

## 9. Procedimiento operativo recomendado

### 9.1 Respaldo programado

```bash
# Flujo endurecido (ver deploy/ para cron, systemd y Windows)
python backend/scripts/db_backup.py --db frostbase --label nightly \
  --encrypt --passphrase-file /etc/frostbase/backup.pass \
  --mirror-dir /mnt/offsite/frostbase \
  --prune --retention-days 30 --keep-last 7 --verify
```

Buenas prácticas:

- Cifrar siempre antes de copiar fuera del host; el comando elimina el `.dump` en claro.
- Conservar 7 respaldos diarios y 4 semanales (ajustar a la política).
- Copiar a almacenamiento externo (S3/MinIO/NAS) con credenciales separadas.
- Verificar semanalmente con `db_verify.py` sobre un respaldo antiguo.
- Ejecutar un ensayo de recuperación trimestral con `db_recover.py` sobre `frostbase_drill`.
- Alertar si el respaldo falla, si `verified` es `false` o si no hay archivos nuevos en 26 h.

### 9.2 Restauración en producción

La recuperación completa se hace con un solo comando; el script crea el
`pre_restore`, detiene la app, restaura, compara checksums, arranca y valida el
health. Si algo falla, revierte automáticamente.

```bash
# 1. Simular el plan
python backend/scripts/db_recover.py \
  --dump db-backups/frostbase_nightly_<timestamp>.dump.enc --dry-run

# 2. Recuperar
python backend/scripts/db_recover.py \
  --dump db-backups/frostbase_nightly_<timestamp>.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass \
  --target frostbase --yes

# 3. Validación adicional
python backend/scripts/db_checksum.py --db frostbase \
  --compare docs/security/evidence/2026-11-15/checksums_baseline.json
```

> **Importante:** `AUTO_SEED=true` puede repoblar datos de demostración si la restauración deja `users` vacío. Durante una recuperación, usar siempre `AUTO_SEED=false` y validar con checksums, no solo con “la aplicación arrancó”.

### 9.3 Simulación periódica

Ejecutar mensualmente:

```bash
python backend/scripts/run_dlp_drp_tests.py \
  --evidence-dir docs/security/evidence/$(date +%Y-%m-%d)
```

Registrar RTO/RPO, comparar contra la meta y adjuntar la evidencia al informe de continuidad.

---

## 10. Reproducción de las pruebas

```bash
# 1. Requisitos
docker compose up -d db app
docker image ls frostbase-v2-app

# 2. Ejecutar la suite completa (crea frostbase_drill y las evidencias)
python backend/scripts/run_dlp_drp_tests.py \
  --evidence-dir docs/security/evidence/2026-11-15

# 3. Revisar resultados
cat docs/security/evidence/2026-11-15/summary.md
cat docs/security/evidence/2026-11-15/results.json
```

Salida esperada de la última ejecución:

```text
PASS: 14
FAIL: 7
INFO: 1
ERROR: 0
```

Los `FAIL` son hallazgos reales, no errores del ejecutor. El código de salida es `1` para que un pipeline de CI los detecte.

Para inspeccionar manualmente la copia después de la suite:

```bash
docker run -d --name frostbase-drill-app \
  --network frostbase-v2_default \
  -e DATABASE_URL=postgresql://frostbase:frostbase@db:5432/frostbase_drill \
  -e AUTO_SEED=false \
  -p 8001:8000 frostbase-v2-app:latest
```

La copia `frostbase_drill` queda restaurada al estado de la línea base. Los contenedores `frostbase-drill-app` y `frostbase-restore-app`, así como las bases `frostbase_restore` y `frostbase_restore_recovery`, se eliminan al finalizar.

---

## 11. Índice de evidencias

Directorio: `docs/security/evidence/2026-11-15/`

| Archivo | Contenido |
| --- | --- |
| `summary.md` | Resumen legible con las 22 pruebas y su resultado |
| `results.json` | Resultado completo, metadatos, entorno y detalles |
| `environment.json` | Versión de PostgreSQL, plataforma, commit, contenedores |
| `checksums_baseline.json` | Filas y checksums de las 20 tablas de `frostbase_drill` |
| `checksums_restored_dr01.json` | Checksums de la restauración DR-01 |
| `checksums_restored_dr02.json` | Checksums de la restauración DR-02 |
| `backup_dr01.json` | SHA-256, tamaño, objetos y ruta del respaldo |
| `dr01.json` | Detalle de respaldo, restore y prueba funcional |
| `dlp01.json` | Respuestas de acceso anónimo, RBAC, token, OpenAPI y BD |
| `dlp01_users_sample.json` | Muestra redactada de PII devuelta al conductor |
| `dlp02.json` | Borrado lógico, `DELETE FROM`, auditoría, FK y recuperación |
| `dlp02_entities.json` | Estado de usuario, tienda, ruta y camión tras el borrado |
| `dr02.json` | Desastre, restauración, checksums y RTO |
| `rto_rpo.json` | RTO y RPO medidos |
| `backup-hardening/results.json` | Resultados de cifrado, retención, espejo, verificación, recuperación y respaldo físico |
| `backup-hardening/summary.md` | Resumen legible de la fase de endurecimiento |

Los respaldos `.dump` se guardan en `db-backups/`, que está en `.gitignore` porque contienen PII y no deben versionarse. En operación se almacenan cifrados (`.dump.enc`).

La carpeta `docs/security/evidence/2026-11-16-demo/` sigue el mismo esquema y añade `context.json`, `manifest.json`, `hashes.txt`, `capture-guide.md` y `captures/` con los cuatro bloques listos para captura. Se genera con `backend/scripts/capture_evidence.ps1` (sección 7.11).

---

## 12. Limitaciones

1. Las pruebas se ejecutaron en un entorno local con Docker Desktop y un volumen de ≈58 KB; el RTO no es representativo de producción.
2. La prueba de exfiltración de BD se hizo contra `frostbase` (solo lectura) para comprobar la exposición real del puerto; no se modificó la base principal.
3. No se probó PITR porque `archive_mode=off`.
4. No se probó la recuperación ante corrupción física del volumen; DR-02 simuló la pérdida lógica total de la base (`DROP DATABASE`), que es equivalente para validar el procedimiento de restore.
5. Las pruebas DLP se centran en la API y la configuración de Docker; no cubren malware, ingeniería social ni controles de red perimetral.
6. La evidencia contiene rutas y hashes, pero la muestra de PII está redactada deliberadamente.

---

## 13. Conclusión

Frostbase **sí cuenta con la mecánica necesaria para proteger y restaurar la información**: autenticación sólida, hashing de contraseñas, borrado lógico, integridad referencial, respaldos verificables y una restauración completa que reproduce la base con checksums idénticos. Las pruebas DR-01 y DR-02 demuestran que el procedimiento de recuperación funciona y que el RTO es bajo para el volumen actual.

Sin embargo, **todavía no cuenta con un procedimiento operativo completo de DLP/DRP**: los respaldos no están programados, cifrados ni almacenados fuera del host; la base está expuesta con credenciales por defecto; la PII se comparte con cualquier usuario autenticado; y no hay auditoría atribuible. Los scripts y este documento cubren la brecha técnica; las acciones de la sección 8 deben priorizarse para que el proyecto pase de “recuperable en laboratorio” a “operable y auditado en producción”.

---

## 14. Fase de endurecimiento de respaldos (2026-11-16)

Después de la ejecución inicial se implementaron las mejoras que cierran los
hallazgos 3 y 4 de la sección 8. La guía operativa completa está en
[`backup-restore-guide.md`](backup-restore-guide.md).

### 14.1 Cambios implementados

| Componente | Cambio |
| --- | --- |
| Cifrado | AES-256-GCM + PBKDF2-HMAC-SHA256 (600 000 iteraciones); el `.dump` en claro se elimina |
| Passphrase | Solo por archivo o `FROSTBASE_BACKUP_PASSPHRASE`; nunca por argumento |
| Metadatos | Checksums del origen (`source_checksums`) para verificar restauraciones |
| Espejo | `--mirror-dir` copia y verifica SHA-256 del archivo y sus metadatos |
| Retención | `--prune`, `--retention-days`, `--keep-last` y `db_prune.py` |
| Verificación | `db_verify.py`: restaura en base temporal y compara digest |
| Recuperación | `db_recover.py`: pre-backup, restore, checksums, health y rollback automático |
| Respaldo físico | `db_basebackup.py` con `pg_basebackup` |
| PITR | Overlay `docker-compose.backup.yml` con WAL archiving |
| Programación | Plantillas en `deploy/cron`, `deploy/systemd` y `deploy/windows` |

### 14.2 Resultados de validación

Todas las pruebas se ejecutaron sobre `frostbase_drill`; la base principal
`frostbase` solo se usó para lecturas.

| Prueba | Resultado | Evidencia |
| --- | --- | --- |
| Respaldo cifrado + espejo + retención + verificación | `encrypted: true`, `plaintext_removed: true`, `mirror.verified: true` | `backup.json` |
| Verificación independiente | `verified: true`, digest `5a0341b9…92e6` | `verify.json` |
| Passphrase incorrecta | Error limpio, código `1` | `verify-wrong-passphrase.json` |
| Restauración cifrada | `encrypted: true`, `match: true`, 0.54 s | `restore.json` |
| Retención | Conservó el más reciente y eliminó 2 antiguos | `prune.json` |
| Recuperación guiada | `success: true`, `app_health: true`, `match: true`, RTO **20.62 s** | `recover.json` |
| Respaldo físico | `.tar.gz` de 6 283 121 bytes con `backup_manifest`, `base.tar.gz` y `pg_wal.tar.gz`; `pitr_ready: false` (`archive_mode=off`) | `basebackup.json` |

Hashes de referencia:

- Respaldo cifrado: `96cd58a73ba86f1d826464b9d04a8563660c97556985ad9f10aa54fb1aa286a9`.
- Respaldo físico: `9733bdcb9a74d5e62b78d86e22da58f9be3bab466375011f207f08fd630c35d2`.
- Digest de la base de práctica: `5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6`.

### 14.3 Estado de los hallazgos

- **Hallazgo 3 (respaldos sin cifrar): mitigado.** El flujo por defecto cifra y
  borra el texto claro; las pruebas confirman que una passphrase incorrecta no
  permite descifrar.
- **Hallazgo 4 (sin procedimiento operativo): mitigado a nivel de herramienta.**
  Existen retención, espejo, verificación, recuperación y plantillas de
  programación. Queda pendiente **desplegar** la programación en el entorno
  real, definir el almacenamiento externo y custodiar la passphrase en un gestor
  de secretos.
- **PITR:** disponible mediante overlay, pero no activado. Requiere reiniciar
  PostgreSQL y respaldar el volumen WAL; mientras no se active, el RPO real
  sigue siendo el intervalo entre respaldos lógicos.

Las evidencias de esta fase están en
`docs/security/evidence/2026-11-15/backup-hardening/`.
