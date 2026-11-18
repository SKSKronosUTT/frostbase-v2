# Guía de respaldo, verificación y recuperación

**Proyecto:** Frostbase v2
**Última actualización:** 16 de noviembre de 2026
**Scripts:** `backend/scripts/`
**Plantillas de programación:** `deploy/`

Esta guía explica cómo funciona la mecánica de respaldo/restauración de Frostbase,
qué hace cada script, cómo programarlos y cómo recuperar el servicio ante un
desastre. Sustituye al procedimiento manual descrito en
[`dlp-drp-test-plan.md`](dlp-drp-test-plan.md) para la operación diaria.

---

## 1. Resumen

La mecánica combina cuatro capas:

| Capa | Herramienta | Qué aporta |
| --- | --- | --- |
| Respaldo lógico | `db_backup.py` (`pg_dump -Fc`) | Copia consistente y portable de una base |
| Confidencialidad | AES-256-GCM + PBKDF2 | Protege la PII si el archivo se filtra |
| Integridad | Checksums por tabla + SHA-256 | Detecta corrupción y restauraciones incompletas |
| Recuperación | `db_restore.py`, `db_verify.py`, `db_recover.py` | Restaura, verifica y vuelve atrás si falla |

Flujo operativo recomendado:

```
02:15  db_backup.py --encrypt --prune --mirror-dir ... --verify
         │
         ├─ pg_dump -Fc dentro de frostbase-db
         ├─ checksums por tabla (huella del origen)
         ├─ cifrado AES-256-GCM en el host
         ├─ copia al espejo externo + verificación SHA-256
         ├─ retención (keep-last + retention-days)
         └─ restauración en frostbase_verify + comparación de digest
```

Si la verificación falla, el comando termina con código `1` y el respaldo **no**
debe considerarse válido.

---

## 2. Requisitos e instalación

### 2.1 Host

- Python 3.10 o superior.
- Docker con el contenedor `frostbase-db` en ejecución.
- El usuario que ejecuta los scripts debe poder usar `docker` (grupo `docker`
  en Linux, Docker Desktop en Windows).
- `cryptography` instalado en el Python del host:

```bash
pip install -r backend/scripts/requirements-backup.txt
# o
pip install "cryptography>=42,<46"
```

La instalación dentro del contenedor no es necesaria: `pg_dump`/`pg_restore`
corren en el contenedor y el cifrado ocurre en el host.

### 2.2 Variables y supuestos

| Variable | Valor por defecto | Uso |
| --- | --- | --- |
| `FROSTBASE_DB_CONTAINER` | `frostbase-db` | Contenedor PostgreSQL |
| `FROSTBASE_DB_NAME` | `frostbase` | Base por defecto |
| `FROSTBASE_DB_USER` | `frostbase` | Usuario PostgreSQL |
| `FROSTBASE_BACKUP_PASSPHRASE` | — | Passphrase para cifrar/descifrar |
| `FROSTBASE_APP_IMAGE` | `frostbase-v2-app:latest` | Imagen para pruebas |
| `FROSTBASE_NETWORK` | `frostbase-v2_default` | Red Docker |

Los respaldos se guardan por defecto en `db-backups/`, que está en `.gitignore`
porque contiene PII. **Nunca** versione esa carpeta.

---

## 3. Modelo de seguridad

### 3.1 Cifrado de los respaldos

Formato del archivo `.dump.enc`:

```
┌────────────┬──────────────┬──────────────┬─────────────────────────┐
│ "FROSTBK1" │ salt (16 B)  │ nonce (12 B) │ ciphertext + tag (GCM)  │
└────────────┴──────────────┴──────────────┴─────────────────────────┘
```

- **Cifra:** AES-256-GCM (confidencialidad + autenticación).
- **KDF:** PBKDF2-HMAC-SHA256 con **600 000 iteraciones** y salt aleatorio de
  16 bytes por archivo.
- **Nonce:** 12 bytes aleatorios por archivo.
- **AAD:** el magic `FROSTBK1`, que impide reinterpretar el archivo con otro
  formato.
- Una passphrase incorrecta produce el error
  `No se pudo descifrar el respaldo: passphrase incorrecta o archivo corrupto`
  y código de salida `1`.

Los parámetros de cifrado quedan registrados en `<archivo>.dump.enc.json`
(`cipher`, `kdf`, `kdf_iterations`, `salt_b64`, `nonce_b64`, `sha256`). El salt
y el nonce no son secretos; la passphrase **no** se guarda en los metadatos.

### 3.2 Manejo de la passphrase

Reglas:

1. La passphrase **nunca** se pasa por argumento de línea de comandos.
2. Se lee, en este orden, de:
   - `--passphrase-file <ruta>` (recomendado para automatización),
   - la variable `FROSTBASE_BACKUP_PASSPHRASE`,
   - prompt interactivo si la terminal es TTY.
3. Mínimo 12 caracteres; se recomiendan 32+ generados aleatoriamente.
4. El archivo debe tener permisos `600` y propietario restringido.
5. Guarde una copia de la passphrase en un gestor de secretos **fuera** del
   host de respaldos. Sin ella, los `.enc` son irrecuperables.

Generar una passphrase:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))" \
  > /etc/frostbase/backup.pass
chmod 600 /etc/frostbase/backup.pass
```

En Windows:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))" |
  Set-Content -Path C:\ProgramData\Frostbase\backup.pass -NoNewline -Encoding ascii
icacls C:\ProgramData\Frostbase\backup.pass /inheritance:r `
  /grant:r "$($env:USERNAME):M" "*S-1-5-32-544:F"
```

### 3.3 Qué contiene un respaldo

El dump incluye las 20 tablas de Frostbase, incluidas `users`, `orders`,
`stores` y `readings`. Por eso se trata como **material con PII**:

- No se versiona en Git.
- Se cifra antes de salir del host.
- El espejo externo también debe tener acceso restringido.
- Las evidencias publicadas solo incluyen hashes y conteos, nunca filas.

---

## 4. Referencia de scripts

Todos los scripts imprimen JSON y usan códigos de salida consistentes:

| Código | Significado |
| ---: | --- |
| `0` | Éxito (o simulación sin cambios) |
| `1` | Fallo de verificación, error de cifrado o error de ejecución |
| `2` | Operación destructiva no confirmada (`db_recover.py` sin `--yes`) |

### 4.1 `db_backup.py` — respaldo lógico

Genera el dump, calcula checksums del origen, cifra, espeja y verifica.

```bash
python backend/scripts/db_backup.py \
  --db frostbase \
  --label nightly \
  --out-dir db-backups \
  --encrypt \
  --passphrase-file /etc/frostbase/backup.pass \
  --mirror-dir /mnt/offsite/frostbase \
  --prune --retention-days 30 --keep-last 7 \
  --verify
```

| Opción | Descripción |
| --- | --- |
| `--db` | Base a respaldar (default `frostbase`) |
| `--label` | Etiqueta que se agrega al nombre (`frostbase_nightly_<ts>.dump`) |
| `--out-dir` | Carpeta destino (default `db-backups`) |
| `--container` | Contenedor PostgreSQL |
| `--encrypt` | Cifra con AES-256-GCM |
| `--passphrase-file` | Archivo con la passphrase |
| `--passphrase-env` | Variable de entorno alternativa |
| `--keep-plaintext` | Conserva el `.dump` en claro (no recomendado) |
| `--no-checksums` | Omite la huella del origen (más rápido, menos verificable) |
| `--mirror-dir` | Copia el `.enc` y su `.json` a otra ubicación y verifica SHA-256 |
| `--prune` | Aplica retención después del respaldo |
| `--retention-days` | Días de retención (default `30`) |
| `--keep-last` | Mínimo de respaldos a conservar (default `7`) |
| `--verify` | Restaura en una base temporal y compara checksums |
| `--temp-db` | Base temporal para `--verify` (default `frostbase_verify`) |

Salida: `<base>_<label>_<timestamp>.dump[.enc]` y su `.json` con:

- `sha256` del archivo final y `plain_sha256` del dump antes de cifrar.
- `size_bytes`, `objects`, `format`.
- `encrypted`, `encryption`, `plaintext_removed`.
- `source_checksums` (filas y checksum por tabla) y `source_checksums_stable`.
- `mirror` con la ruta y el SHA-256 verificado del espejo.

El respaldo se valida con `pg_restore --list` antes de darlo por bueno.

### 4.2 `db_restore.py` — restauración

Restaura un `.dump` o `.dump.enc` en la base destino. Descifra en un archivo
temporal que se elimina al terminar y ejecuta `pg_restore --single-transaction`.

```bash
python backend/scripts/db_restore.py \
  --dump db-backups/frostbase_nightly_20261116T021500Z.dump.enc \
  --target frostbase_restore \
  --passphrase-file /etc/frostbase/backup.pass \
  --compare docs/security/evidence/2026-11-15/checksums_baseline.json \
  --output db-backups/restore-check.json
```

| Opción | Descripción |
| --- | --- |
| `--dump` | Archivo a restaurar (obligatorio) |
| `--target` | Base destino (obligatorio) |
| `--no-drop` | No elimina la base destino antes de restaurar |
| `--passphrase-file` | Passphrase si el respaldo está cifrado |
| `--compare` | JSON de checksums de referencia |
| `--output` | Guarda el resultado en JSON |

Por defecto **elimina la base destino** (`DROP DATABASE ... WITH FORCE`). Nunca
apunte `--target` a `frostbase` salvo que sea una recuperación planificada; para
pruebas use `frostbase_restore` o `frostbase_drill`.

### 4.3 `db_verify.py` — verificación por restauración

Restaura el respaldo en una base temporal y compara el digest contra
`source_checksums` guardado en los metadatos. Es la prueba más fuerte de que un
respaldo sirve.

```bash
python backend/scripts/db_verify.py \
  --dump db-backups/frostbase_nightly_20261116T021500Z.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass \
  --temp-db frostbase_verify \
  --output db-backups/verify.json
```

| Opción | Descripción |
| --- | --- |
| `--dump` | Respaldo a verificar (obligatorio) |
| `--metadata` | Metadatos alternativos (default `<dump>.json`) |
| `--temp-db` | Base temporal (default `frostbase_verify`) |
| `--keep-temp-db` | Conserva la base temporal para inspección |
| `--output` | Guarda el resultado en JSON |

Devuelve `0` si `verified: true` y `1` si hay diferencias. La base temporal se
elimina al finalizar salvo que use `--keep-temp-db`.

### 4.4 `db_prune.py` — retención

Elimina respaldos antiguos. **Siempre** conserva los `--keep-last` más recientes
y, del resto, solo borra los que superen `--retention-days`.

```bash
# Simulación (por defecto)
python backend/scripts/db_prune.py --dir db-backups --database frostbase

# Aplicar
python backend/scripts/db_prune.py \
  --dir db-backups --database frostbase \
  --retention-days 30 --keep-last 7 --yes
```

| Opción | Descripción |
| --- | --- |
| `--dir` | Carpeta de respaldos |
| `--database` | Limita la poda por prefijo de nombre |
| `--retention-days` | Días de retención (default `30`) |
| `--keep-last` | Mínimo de respaldos a conservar (default `7`) |
| `--dry-run` | Solo muestra lo que se eliminaría |
| `--yes` | Confirma la eliminación real |

Solo considera `*.dump` y `*.dump.enc` (y sus `.json`). Es seguro ejecutarlo
varias veces.

### 4.5 `db_recover.py` — recuperación guiada

Orquesta una recuperación completa con red de seguridad y rollback.

```bash
# 1) Simular el plan
python backend/scripts/db_recover.py \
  --dump db-backups/frostbase_nightly_20261116T021500Z.dump.enc \
  --dry-run

# 2) Recuperar de verdad (base principal)
python backend/scripts/db_recover.py \
  --dump db-backups/frostbase_nightly_20261116T021500Z.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass \
  --target frostbase \
  --app-container frostbase-app \
  --health-url http://localhost:8000/api/health \
  --yes
```

Secuencia interna:

1. Respalda el estado actual como `pre_restore` (salvo `--no-pre-backup`).
2. Detiene el contenedor de la aplicación.
3. Restaura el respaldo en `--target` (destructivo).
4. Compara checksums contra los metadatos.
5. Arranca la app y espera `/api/health`.
6. Si algo falla y existe `pre_restore`, restaura ese respaldo y vuelve a
   arrancar la app (salvo `--no-rollback`).

| Opción | Descripción |
| --- | --- |
| `--dump` | Respaldo a restaurar (obligatorio) |
| `--target` | Base destino (default `frostbase`) |
| `--app-container` | Contenedor de la app (default `frostbase-app`) |
| `--health-url` | URL de health (default `http://localhost:8000/api/health`) |
| `--health-timeout` | Segundos de espera (default `60`) |
| `--skip-app` | No detiene ni arranca la app |
| `--no-pre-backup` | No crea el respaldo previo |
| `--no-rollback` | No revierte si falla |
| `--backup-dir` | Carpeta del `pre_restore` |
| `--yes` | Confirma la operación destructiva |
| `--dry-run` | Muestra el plan sin cambios |

El resultado incluye `success`, `rto_seconds`, `app_health`, `verification` y
`rollback`.

### 4.6 `db_basebackup.py` — respaldo físico

Genera una copia física del clúster con `pg_basebackup -Ft -z -X stream`. Sirve
como base para PITR cuando `archive_mode=on`, o como copia completa del clúster.

```bash
python backend/scripts/db_basebackup.py --label pre_upgrade
```

Salida: `db-backups/base/frostbase_base_<label>_<ts>.tar.gz` y `.json` con
`archive_mode`, `wal_level`, `included_files`, `pitr_ready` y SHA-256.

> **Importante:** con `archive_mode=off` el respaldo físico es completo pero
> **no** permite recuperar a un instante arbitrario. Para PITR vea la sección 8.

### 4.7 `db_checksum.py` — huella por tabla

Calcula filas y checksums deterministas de todas las tablas y puede comparar
contra una referencia.

```bash
python backend/scripts/db_checksum.py --db frostbase_drill \
  --compare docs/security/evidence/2026-11-15/checksums_baseline.json
```

Es la misma huella que usan `db_verify.py` y `db_recover.py`. Útil para auditar
una base restaurada o detectar cambios no esperados.

### 4.8 `run_dlp_drp_tests.py` — suite de pruebas

Ejecuta las 22 pruebas DLP/DRP sobre `frostbase_drill` y escribe evidencias en
`docs/security/evidence/<fecha>/`.

```bash
python backend/scripts/run_dlp_drp_tests.py
```

No se ejecuta en producción: crea/borra objetos y contenedores de prueba.

---

## 5. Flujo operativo diario

### 5.1 Respaldo

```bash
python backend/scripts/db_backup.py \
  --db frostbase --label nightly \
  --encrypt --passphrase-file /etc/frostbase/backup.pass \
  --mirror-dir /mnt/offsite/frostbase \
  --prune --retention-days 30 --keep-last 7 \
  --verify
```

Qué revisar en la salida:

- `backup.encrypted: true` y `backup.plaintext_removed: true`.
- `backup.source_checksums_stable: true` (no hubo escrituras durante el dump).
- `backup.mirror.verified: true`.
- `verification.verified: true` y `verification.comparison.match: true`.

### 5.2 Verificación independiente

La verificación diaria ya ocurre con `--verify`. Además, ejecute una
verificación semanal sobre un respaldo **antiguo** (no el recién creado), para
detectar corrupción que el respaldo diario aún no refleja:

```bash
python backend/scripts/db_verify.py \
  --dump db-backups/frostbase_nightly_<fecha-antigua>.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass
```

### 5.3 Respaldo físico semanal

```bash
python backend/scripts/db_basebackup.py --label weekly
```

Guarde también los metadatos `.json` junto al `.tar.gz`.

---

## 6. Programación

### 6.1 Linux con cron

```bash
sudo install -o root -g root -m 644 \
  deploy/cron/frostbase-backup /etc/cron.d/frostbase-backup
sudo install -o root -g frostbase -m 750 \
  deploy/cron/frostbase-backup.sh /opt/frostbase/deploy/cron/frostbase-backup.sh
sudo install -d -o root -g frostbase -m 750 /etc/frostbase
sudo install -o root -g frostbase -m 600 \
  deploy/systemd/backup.env.example /etc/frostbase/backup.env
```

Edite `/etc/frostbase/backup.env` y cree `/etc/frostbase/backup.pass` con la
passphrase. La entrada de cron usa `flock` para evitar solapamientos y escribe
en `/var/log/frostbase-backup.log`.

### 6.2 Linux con systemd

```bash
sudo install -o root -g root -m 644 \
  deploy/systemd/frostbase-backup.service /etc/systemd/system/
sudo install -o root -g root -m 644 \
  deploy/systemd/frostbase-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now frostbase-backup.timer

# Ejecución manual
sudo systemctl start frostbase-backup.service

# Estado y próxima ejecución
systemctl status frostbase-backup.timer
systemctl list-timers frostbase-backup.timer
journalctl -u frostbase-backup.service -n 100
```

El servicio es `Type=oneshot`, corre como `frostbase` y usa
`EnvironmentFile=/etc/frostbase/backup.env`. El timer se ejecuta a las 02:15 UTC
con `Persistent=true` (recupera la ventana si el servidor estuvo apagado).

### 6.3 Windows con Programador de tareas

`deploy\windows\frostbase-backup.ps1` es el script que ejecuta el respaldo; no
registra la tarea por sí solo. Para registrarla use
`deploy\windows\register-frostbase-backup.ps1`, que deduce la raíz del
repositorio, valida Python y la passphrase, y pasa todas las rutas a la tarea:

```powershell
# Primera instalación: crea la passphrase, registra la tarea y la ejecuta una vez
.\deploy\windows\register-frostbase-backup.ps1 `
  -CreatePassphrase `
  -RunNow
```

Si ya tiene la passphrase y una carpeta de respaldos:

```powershell
.\deploy\windows\register-frostbase-backup.ps1 `
  -BackupDir D:\Backups\frostbase `
  -MirrorDir E:\Offsite\frostbase `
  -PassphraseFile C:\ProgramData\Frostbase\backup.pass `
  -Force
```

La tarea se registra con el usuario actual y `-LogonType Interactive`: solo
corre con la sesión iniciada, porque Docker Desktop depende del perfil del
usuario. No use `SYSTEM`. Si `Register-ScheduledTask` devuelve "Acceso
denegado", abra PowerShell como administrador.

Para ejecutar el respaldo manualmente, sin registrar la tarea:

```powershell
.\deploy\windows\frostbase-backup.ps1 `
  -BackupDir C:\Users\<usuario>\FrostbaseBackups `
  -PassphraseFile C:\ProgramData\Frostbase\backup.pass
```

Verificar la tarea y sus ejecuciones:

```powershell
Get-ScheduledTask -TaskName "Frostbase Backup"
Get-ScheduledTaskInfo -TaskName "Frostbase Backup"
Start-ScheduledTask -TaskName "Frostbase Backup"
Get-Content C:\ProgramData\Frostbase\logs\frostbase-backup-*.log -Tail 50
```

### 6.4 Frecuencia sugerida

| Trabajo | Frecuencia | Herramienta |
| --- | --- | --- |
| Respaldo lógico cifrado + verificación | Diario | `db_backup.py --verify` |
| Verificación de respaldo antiguo | Semanal | `db_verify.py` |
| Respaldo físico | Semanal | `db_basebackup.py` |
| Prueba de recuperación completa | Trimestral | `db_recover.py` sobre `frostbase_drill` |
| Auditoría de la passphrase | Semestral | Gestor de secretos |

---

## 7. Retención y espejo externo

### 7.1 Política de retención

`db_backup.py --prune` y `db_prune.py` aplican dos reglas simultáneas:

- Se conservan siempre los **N más recientes** (`--keep-last`, default 7).
- De los restantes, se eliminan los que superen `--retention-days` (default 30).

Esto evita quedarse sin respaldos si el reloj o las fechas de archivo son
incorrectas. La poda elimina también el `.json` asociado.

### 7.2 Espejo externo

`--mirror-dir` copia el archivo final (`.enc`) y sus metadatos a otra ubicación,
recalcula SHA-256 y falla si no coincide con el registrado. No es un simple
`cp`: el comando devuelve error si la copia está corrupta.

Recomendaciones:

- Use un disco o NAS distinto del host de la base.
- Monte el espejo con permisos mínimos.
- Si usa sincronización a la nube, verifique que **no** suba archivos en claro.
- Pruebe la restauración **desde el espejo**, no solo desde el host.

---

## 8. PITR con WAL (opcional)

El overlay `docker-compose.backup.yml` habilita `archive_mode=on`,
`archive_timeout=60` y guarda el WAL en el volumen `frostbase_wal_archive`
(el nombre real lleva el prefijo del proyecto, por ejemplo
`frostbase-v2_frostbase_wal_archive`).

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml up -d db
```

Consideraciones:

1. **Requiere reiniciar PostgreSQL** para aplicar `archive_mode`.
2. El archivo WAL debe respaldarse junto con el `pg_basebackup`; sin ambos no
   hay PITR.
3. Verifique el archivado:

```bash
docker exec frostbase-db psql -U frostbase -d postgres \
  -c "SELECT * FROM pg_stat_archiver;"
docker exec frostbase-db ls -lh /var/lib/postgresql/wal-archive | tail
```

4. Para restaurar a un instante, monte el base backup y el WAL en un contenedor
   de recuperación y configure `restore_command` + `recovery_target_time`. Esta
   operación debe probarse en un entorno aislado antes de usarla en producción.

Si no necesita PITR, mantenga el overlay desactivado: el respaldo lógico diario
ya cubre RPO de 24 horas.

---

## 9. Recuperación ante desastres

### 9.1 Escenario A — pérdida lógica (tabla o base borrada)

```bash
python backend/scripts/db_recover.py \
  --dump db-backups/frostbase_nightly_<ts>.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass \
  --target frostbase --yes
```

### 9.2 Escenario B — corrupción del host

1. Aprovisione un host nuevo con Docker y el repositorio.
2. Restaure la passphrase desde el gestor de secretos.
3. Copie el respaldo desde el espejo externo.
4. Ejecute `db_recover.py` con `--target frostbase`.
5. Verifique `/api/health` y `db_checksum.py`.

### 9.3 Escenario C — ensayo sin tocar producción

Use la copia de práctica y su API aislada:

```bash
python backend/scripts/db_recover.py \
  --dump db-backups/frostbase_drill_<ts>.dump.enc \
  --target frostbase_drill \
  --app-container frostbase-drill-app \
  --health-url http://localhost:8001/api/health \
  --passphrase-file /etc/frostbase/backup.pass --yes
```

El ensayo mide el RTO real (pre-backup + restore + health). En la última prueba
fue de **20.62 s** con el volumen actual.

### 9.4 Criterios de éxito

- `success: true`.
- `verification.comparison.match: true`.
- `app_health: true`.
- `db_checksum.py` devuelve `match: true` contra la referencia.

Si falla el health o los checksums, `db_recover.py` restaura automáticamente el
`pre_restore` y lo indica en `rollback`.

---

## 10. Monitoreo y alertas

El respaldo es útil solo si alguien revisa el resultado. Mínimo:

1. **Código de salida:** cron/systemd ya envía correo si el comando falla.
   Asegure `MAILTO` o un recolector de logs.
2. **Frescura:** alerte si no hay un `.enc` nuevo en las últimas 26 horas.
3. **Tamaño:** alerte si el tamaño cae más del 50 % respecto al promedio.
4. **Verificación:** alerte si `verification.verified` es `false`.
5. **Espejo:** alerte si el SHA-256 del espejo no coincide.
6. **Espacio:** alerte si el disco de respaldos supera el 80 %.

Ejemplo de chequeo de frescura en Linux:

```bash
find /var/backups/frostbase -name '*.dump.enc' -mtime -1 | grep -q . \
  || echo "ALERTA: no hay respaldo en 24 h" | mail -s "Frostbase backup" ops@example.com
```

---

## 11. Solución de problemas

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `El cifrado de respaldos requiere el paquete 'cryptography'` | Falta la dependencia | `pip install -r backend/scripts/requirements-backup.txt` |
| `No se pudo descifrar el respaldo: passphrase incorrecta o archivo corrupto` | Passphrase errónea o archivo truncado | Verifique el archivo de passphrase y el SHA-256 del `.enc` |
| `No existe el archivo de passphrase` | Ruta incorrecta o permisos | Revise la ruta y que el usuario de la tarea pueda leerla |
| `El respaldo está cifrado y no se proporcionó passphrase` | Se ejecutó en modo no interactivo sin archivo/env | Use `--passphrase-file` |
| `Los checksums restaurados no coinciden con el respaldo` | Dump incompleto, restauración parcial o base cambiada | Repita `db_verify.py`; si falla, use un respaldo anterior |
| `La aplicación no respondió al health check` | App lenta, puerto ocupado o migraciones | Revise `docker logs <app>` y aumente `--health-timeout` |
| `pg_dump` falla por conexión | Contenedor detenido o credenciales | `docker ps`, revise `docker-compose.yml` |
| `permission denied` al usar Docker | Usuario fuera del grupo `docker` | `sudo usermod -aG docker <usuario>` y reinicie sesión |
| `destination database is being accessed by other users` | Conexiones activas | `db_restore.py` usa `DROP ... WITH FORCE`; detenga la app si persiste |
| El respaldo físico dice `pitr_ready: false` | `archive_mode=off` | Active el overlay `docker-compose.backup.yml` y reinicie la BD |
| Poda borra demasiado | `--keep-last 0` o fechas de archivo erróneas | Use `--dry-run` antes de `--yes` |

### 11.1 Diagnóstico rápido

```bash
# ¿Hay contenedores activos?
docker ps --format '{{.Names}}\t{{.Status}}'

# ¿El respaldo es legible?
python backend/scripts/db_verify.py --dump <archivo> \
  --passphrase-file /etc/frostbase/backup.pass

# ¿Los metadatos son coherentes?
python -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['encrypted'],d['source_checksums']['digest'])" \
  <archivo>.json

# ¿El espejo coincide?
sha256sum <archivo> /mnt/offsite/frostbase/<archivo>
```

---

## 12. Checklist de operación

Antes de considerar el sistema "operable":

- [ ] `cryptography` instalado en el host de respaldos.
- [ ] Passphrase de 32+ caracteres, en archivo `600` y en gestor de secretos.
- [ ] Respaldo diario programado y ejecutado al menos una vez.
- [ ] `--verify` habilitado y con `verified: true`.
- [ ] Espejo externo configurado y verificado.
- [ ] Retención definida (por defecto 30 días / 7 copias).
- [ ] Alerta de frescura y de fallo configurada.
- [ ] Prueba de recuperación trimestral sobre `frostbase_drill`.
- [ ] RTO/RPO documentados y aceptados por el negocio.
- [ ] `db-backups/` fuera de Git y del alcance de usuarios no autorizados.
- [ ] PITR evaluado (activado o descartado conscientemente).

---

## 13. Evidencias y pruebas de la fase de hardening

Los resultados de la validación de estas herramientas están en
`docs/security/evidence/2026-11-15/backup-hardening/`:

| Archivo | Contenido |
| --- | --- |
| `results.json` | Resultados de cifrado, espejo, retención, verificación, recuperación y respaldo físico |
| `summary.md` | Resumen legible con comandos y hallazgos |

Resultados principales:

- Respaldo cifrado con AES-256-GCM: `.dump` en claro eliminado.
- Espejo verificado con SHA-256 coincidente.
- `db_verify.py`: `verified: true`.
- Passphrase incorrecta: error limpio y código `1`.
- Retención: conservó el más reciente y eliminó los antiguos.
- `db_recover.py`: `success: true`, `app_health: true`, `match: true`,
  RTO **20.62 s**.
- `db_basebackup.py`: `.tar.gz` válido con `backup_manifest`, `base.tar.gz` y
  `pg_wal.tar.gz`; `pitr_ready: false` porque `archive_mode=off`.

Para reproducir la validación, vea
[`dlp-drp-test-plan.md`](dlp-drp-test-plan.md) y la sección 14 de esta guía.

---

## 14. Reproducir la validación

```bash
# 1. Dependencia
pip install -r backend/scripts/requirements-backup.txt

# 2. Passphrase de prueba (no usar en producción)
python -c "import secrets; print(secrets.token_urlsafe(32))" > db-backups/test.pass

# 3. Respaldo cifrado + espejo + retención + verificación
python backend/scripts/db_backup.py \
  --db frostbase_drill --label hardening \
  --out-dir db-backups/hardening \
  --encrypt --passphrase-file db-backups/test.pass \
  --mirror-dir db-backups/mirror \
  --prune --retention-days 30 --keep-last 7 --verify

# 4. Verificación independiente
python backend/scripts/db_verify.py \
  --dump db-backups/hardening/<archivo>.dump.enc \
  --passphrase-file db-backups/test.pass

# 5. Restauración en base de prueba
python backend/scripts/db_restore.py \
  --dump db-backups/hardening/<archivo>.dump.enc \
  --target frostbase_restore \
  --passphrase-file db-backups/test.pass

# 6. Recuperación guiada sobre la copia de práctica
python backend/scripts/db_recover.py \
  --dump db-backups/hardening/<archivo>.dump.enc \
  --target frostbase_drill \
  --app-container frostbase-drill-app \
  --health-url http://localhost:8001/api/health \
  --passphrase-file db-backups/test.pass --yes

# 7. Respaldo físico
python backend/scripts/db_basebackup.py --out-dir db-backups/base

# 8. Limpieza
rm -f db-backups/test.pass
```

---

## 15. Referencias

- [`dlp-drp-test-plan.md`](dlp-drp-test-plan.md) — pruebas DLP/DRP y hallazgos.
- [`../../README.md`](../../README.md) — inicio rápido del proyecto.
- `backend/scripts/db_tools.py` — implementación de cifrado, checksums y helpers.
- `docker-compose.backup.yml` — overlay de WAL archiving/PITR.
- `deploy/` — plantillas de cron, systemd y Windows Task Scheduler.
- `deploy/windows/register-frostbase-backup.ps1` — registra y valida la tarea diaria en Windows.
