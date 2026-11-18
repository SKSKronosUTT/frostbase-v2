<div align="center">

<img src="frontend/assets/frosty-logo.png" alt="Cooffy Logo" width="200" />

**Sistema Monitoreo y Gestión de Camiones Refrigerados**




![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-%23009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
</div>

Plataforma de control de cadena de frío para flotillas refrigeradas. Frostbase combina telemetría en vivo de temperatura y humedad, pedidos de entrega, planificación semanal de rutas, gestión de tiendas y un mapa de flotilla en tiempo real en un solo espacio de trabajo.

Tecnologías:
- **Backend:** FastAPI + PostgreSQL
- **Frontend:** HTML, CSS y JavaScript vanilla
- **Despliegue:** Docker Compose con una base de datos PostgreSQL


## Inicio con Docker

```bash
cp .env.example .env
docker compose up --build
```

Abrir en http://localhost:8000.

La API está disponible en http://localhost:8000/api y la documentación en http://localhost:8000/docs.


### Credenciales de demostración

| Rol | Correo | Contraseña |
| --- | --- | --- |
| Administrador | `mgonzalez@logisticarf.com` | `admin123` |
| Conductor | `rsilva@logisticarf.com` | `driver001` |

## Desarrollo local

### 1. Base de datos

```bash
docker compose up -d db
```


### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed.py --force
uvicorn app.main:app --reload --port 8000
```

La aplicación ejecuta las migraciones del esquema y precarga los datos de referencia al iniciar. Define `AUTO_SEED=false` para desactivar la precarga.

### 3. Frontend

El backend sirve el frontend desde `/` mediante `StaticFiles`. Con `uvicorn` en ejecución, abre http://localhost:8000. No se requiere un paso de compilación separado para el frontend.

## Seguridad, respaldos y recuperación

La guía completa de operación está en [`docs/security/backup-restore-guide.md`](docs/security/backup-restore-guide.md): explica cifrado, retención, espejo externo, verificación, recuperación, programación y solución de problemas.

```bash
# Instalar la dependencia de cifrado en el host
pip install -r backend/scripts/requirements-backup.txt

# Respaldo lógico cifrado (AES-256-GCM), con retención, espejo y verificación
python backend/scripts/db_backup.py --db frostbase --label nightly \
  --encrypt --passphrase-file /etc/frostbase/backup.pass \
  --mirror-dir /mnt/offsite/frostbase \
  --prune --retention-days 30 --keep-last 7 --verify

# Verificación por restauración en una base temporal
python backend/scripts/db_verify.py \
  --dump db-backups/<archivo>.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass

# Restauración en una base de verificación
python backend/scripts/db_restore.py \
  --dump db-backups/<archivo>.dump.enc --target frostbase_restore \
  --passphrase-file /etc/frostbase/backup.pass

# Recuperación guiada con respaldo previo y rollback automático
python backend/scripts/db_recover.py \
  --dump db-backups/<archivo>.dump.enc \
  --passphrase-file /etc/frostbase/backup.pass --yes

# Retención y respaldo físico del clúster
python backend/scripts/db_prune.py --dir db-backups --database frostbase
python backend/scripts/db_basebackup.py --label weekly

# Verificación de integridad por tabla
python backend/scripts/db_checksum.py --db frostbase

# Suite DLP + DRP sobre una copia de práctica (frostbase_drill)
python backend/scripts/run_dlp_drp_tests.py

# Ejecutar la suite y preparar los cuatro bloques de evidencia + manifiesto SHA-256
.\backend\scripts\capture_evidence.ps1 -EvidenceDir docs\security\evidence\2026-11-16-demo
```

Plantillas de programación: [`deploy/cron/`](deploy/cron/), [`deploy/systemd/`](deploy/systemd/) y [`deploy/windows/`](deploy/windows/). En Windows, `deploy\windows\register-frostbase-backup.ps1` valida la passphrase y registra la tarea diaria en el Programador de tareas. Para PITR opcional use el overlay `docker-compose.backup.yml`.

El procedimiento de pruebas, los resultados de la última ejecución y las acciones correctivas están en [`docs/security/dlp-drp-test-plan.md`](docs/security/dlp-drp-test-plan.md). Las evidencias se guardan en `docs/security/evidence/`. Los respaldos van a `db-backups/`, que está excluido de Git porque contiene datos personales y se almacena cifrado.

Para las capturas de pantalla use `backend/scripts/capture_evidence.ps1`: ejecuta la suite una sola vez, deja los bloques DLP-01, DLP-02, DR-01 y DR-02 listos en `captures\`, y genera `manifest.json` y `hashes.txt`. Después de capturar los PNG, vuelva a ejecutarlo con `-SkipRun` para incorporarlos al manifiesto.
