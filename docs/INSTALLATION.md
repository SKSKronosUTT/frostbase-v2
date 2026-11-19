# Instalación y operación

## 1. Requisitos

| Componente | Versión mínima |
|---|---|
| Docker Engine | 24 |
| Docker Compose | v2 |
| Python (solo local/simulador) | 3.12 |
| PostgreSQL (solo local) | 16 |

Verifique:

```bash
docker --version
docker compose version
python3 --version
```

```powershell
docker --version
docker compose version
python --version
```

## 2. Secretos obligatorios

El arranque **falla de forma deliberada** si falta cualquiera de estos valores o si
no cumple la política mínima. No existen credenciales por defecto.

| Secreto | Regla | Cómo generarlo |
|---|---|---|
| `SECRET_KEY` | ≥ 64 caracteres aleatorios; no puede empezar por `dev-only` ni `cambia-` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DEVICE_KEY_PEPPER` | ≥ 64 caracteres aleatorios; mismas restricciones | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ADMIN_PASSWORD` | ≥ 12 caracteres; distinta de `ChangeMe123!` | Use un gestor de contraseñas |
| `POSTGRES_PASSWORD` | Contraseña de la base de datos | Use un gestor de contraseñas |

> Rotar `DEVICE_KEY_PEPPER` invalida las claves de dispositivo basadas en HMAC
> (a partir de la Fase 2 del plan). Hasta entonces, mantenga el valor estable.

## 3. Variables de entorno

Copie el archivo de ejemplo y edítelo:

```bash
cp .env.example .env
```

```powershell
Copy-Item .env.example .env
```

Variables que el código lee actualmente:

| Variable | Obligatoria | Default | Descripción |
|---|:--:|---|---|
| `SECRET_KEY` | ✅ | — | Firma de JWT. ≥ 64 caracteres. |
| `DEVICE_KEY_PEPPER` | ✅ | — | Secreto independiente para HMAC de dispositivos. |
| `DEVICE_KEY_FAST_PATH` | — | `true` | Cachea 300 s el acierto Argon2 de dispositivos legacy. |
| `ADMIN_PASSWORD` | ✅ | — | Contraseña inicial del administrador. ≥ 12 caracteres. |
| `POSTGRES_DB` | — | `frostbase` | Nombre de la base. |
| `POSTGRES_USER` | — | `frostbase` | Usuario de PostgreSQL. |
| `POSTGRES_PASSWORD` | ✅ | — | Contraseña de PostgreSQL (obligatoria en Compose). |
| `DATABASE_URL` | — | autodetectada | URL SQLAlchemy para ejecución local fuera de Docker. |
| `ENVIRONMENT` | — | `production` en Compose | Activa las validaciones de coherencia. |
| `COOKIE_SECURE` | — | `true` | Obligatorio `true` en producción. |
| `COOKIE_SAMESITE` | — | `lax` | `lax` o `strict` en producción. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `720` | Duración de la sesión. |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` | — | `admin` / `admin@frostbase.local` | Solo se usan si no existe ningún administrador. |
| `APP_PORT` | — | `8050` | Puerto publicado del contenedor. |
| `AUTO_CREATE_TABLES` | — | `false` | Solo desarrollo/tests. En producción debe ser `false`. |
| `RATE_LIMIT_BACKEND` | — | `memory` | Reservado para la Fase 2 (`memory` o `redis`). |
| `REDIS_URL` | — | `""` | Reservado para la Fase 2. |
| `CORS_ORIGINS` | — | localhost 8050/8060/8070 | Orígenes permitidos, separados por coma. Sin `*`. |
| `DASHBOARD_FRESH_MINUTES` | — | `10` | Ventana de vigencia del promedio del panel. |
| `DISCONNECT_CHECK_SECONDS` | — | `30` | Frecuencia del detector de desconexiones. |
| `OSRM_BASE_URL` | — | `https://router.project-osrm.org` | Servidor de ruteo. |
| `OSRM_TIMEOUT_SECONDS` | — | `15` | Timeout de OSRM. |
| `WEATHER_CACHE_SECONDS` | — | `600` | TTL de la caché de clima. |
| `FRONTEND_DIR` | — | autodetectado | Ruta alternativa del frontend. |

Las variables `DEVICE_OFFLINE_SECONDS`, `WEATHER_CITY`, `WEATHER_LATITUDE` y
`WEATHER_LONGITUDE` **ya no se documentan ni se inyectan**: el código no las lee.
El umbral de desconexión se configura en el panel (`offline_timeout_seconds`).

> Con `RATE_LIMIT_BACKEND=memory` y más de un worker, cada proceso mantiene su
> propio contador: la protección es parcial. Para producción multi-worker use
> `RATE_LIMIT_BACKEND=redis` con `REDIS_URL` o `limit_req` en el proxy inverso.

> En Docker Compose, la `DATABASE_URL` del contenedor se construye automáticamente
> con el host `db`. La variable del `.env` se usa para ejecución local.

## 4. Arranque con Docker Compose

El archivo se llama ahora **`compose.yml`** (antes `docker-compose.yml`). Docker
Compose v2 lo detecta automáticamente; no hace falta pasar `-f`.

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

Secuencia de arranque:

1. `db` inicia PostgreSQL 16 y espera el healthcheck.
2. `app` ejecuta `python -m scripts.migrate`: toma un *advisory lock* de
   PostgreSQL y aplica `alembic upgrade head`. Varias réplicas pueden arrancar a
   la vez sin pisarse.
3. Se crea el administrador si la tabla está vacía.
4. Uvicorn escucha en el puerto `8050` interno, publicado como `APP_PORT`.
5. El frontend se sirve en `/`.
6. El `healthcheck` del servicio consulta `/health`.

Acceso: `http://localhost:${APP_PORT}`.

Si el puerto está ocupado, ajuste `APP_PORT` en `.env` (por ejemplo `8060`, luego
`8070`) y reinicie. Si usa el simulador, actualice también `FROSTBASE_API_URL` en
`iot-simulator/.env`:

```env
APP_PORT=8060
FROSTBASE_API_URL=http://localhost:8060/api/v1
```

## 5. Datos de demostración

```bash
docker compose exec app python -m scripts.seed_demo
```

```powershell
docker compose exec app python -m scripts.seed_demo
```

Crea:

- Ruta **Villa Fontana - Playas de Tijuana** con geometría OSRM y 3 puntos.
- Camiones `ABC-123-A` (en ruta), `JKL-456-B` (disponible) y `XYZ-789-C` (mantenimiento).
- Dispositivos `ESP32-FROST-001` y `ESP32-FROST-002` con claves impresas una sola vez.

El seed es idempotente para camiones/dispositivos por placa/ID, aunque crea una
ruta nueva en cada ejecución (corregido en la Fase 4 del plan).

## 6. Ejecución local

Requisitos: PostgreSQL 16 en `localhost:5432` y base `frostbase`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
# Edite DATABASE_URL y los secretos obligatorios

cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8050
```

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Copy-Item .env.example .env
# Edite DATABASE_URL y los secretos obligatorios

cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8050
```

El backend resuelve `FRONTEND_DIR` o busca `../frontend` relativo al paquete.

## 7. Migraciones y respaldos

```bash
# Nueva migración (desde backend/)
alembic revision --autogenerate -m "cambio"
alembic upgrade head
alembic downgrade -1
```

```powershell
# Nueva migración (desde backend/)
alembic revision --autogenerate -m "cambio"
alembic upgrade head
alembic downgrade -1
```

El arranque en contenedor aplica las migraciones con
`docker compose exec app python -m scripts.migrate`. Para respaldo, restauración
probada, RPO y RTO consulte **[docs/ops/BACKUP-RESTORE.md](ops/BACKUP-RESTORE.md)**.

## 7.1 Pruebas automatizadas

Las pruebas usan un PostgreSQL 16 real (índices parciales y `ON CONFLICT` no
existen en SQLite) y recrean el esquema con Alembic en cada ejecución.

```bash
# 1. Base de datos de test (puerto 55432)
docker compose -f compose.test.yml up -d

# 2. Dependencias de desarrollo
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 3. Ejecutar
pytest -q

# 4. Limpiar (opcional)
docker compose -f compose.test.yml down
```

Si usa otra base, defina `TEST_DATABASE_URL` antes de `pytest`. La suite fija
`SECRET_KEY`, `DEVICE_KEY_PEPPER` y `ADMIN_PASSWORD` de test antes de importar
`app`.

## 8. Cambio de contraseña inicial

1. Inicie sesión con `ADMIN_USERNAME` y la `ADMIN_PASSWORD` definida en `.env`.
2. Si la base ya existía antes de la migración `0002_admin_auth_policy`, el
   administrador tendrá `must_change_password = true`: el panel muestra un modal
   obligatorio y no permite continuar hasta definir una contraseña nueva.
3. La nueva contraseña debe tener **≥ 12 caracteres**, ser distinta de la actual y
   no contener el nombre de usuario.
4. Al cambiarla se incrementa `token_version`: los JWT emitidos antes dejan de ser
   válidos de inmediato.

También puede cambiarla desde **Configuración → Cuenta de administrador →
Cambiar contraseña**.

## 9. Recuperación de acceso

Si se perdió la contraseña del administrador:

```bash
# Restablece la contraseña desde ADMIN_PASSWORD (sin imprimirla)
docker compose exec app python -m scripts.reset_admin

# O indique otra contraseña explícitamente
docker compose exec app python -m scripts.reset_admin --username admin --password 'NuevaClaveSegura123'
```

```powershell
docker compose exec app python -m scripts.reset_admin
docker compose exec app python -m scripts.reset_admin --username admin --password "NuevaClaveSegura123"
```

El script incrementa `token_version` e invalida las sesiones activas. Por defecto
mantiene `must_change_password = true`, de modo que el siguiente login obliga a
definir una contraseña nueva; añada `--clear-must-change` solo si desea conservar
la contraseña indicada. Si prefiere no usar el contenedor:

```bash
cd backend
python -m scripts.reset_admin --username admin
```

## 10. Verificación rápida

```bash
# Estado de servicios (debe mostrar healthy)
docker compose ps

# Salud de la API
curl -o /dev/null -w "%{http_code}\n" http://localhost:8050/health

# Login (use la contraseña real; no la escriba en el historial de shell en producción)
curl -s -c cookies.txt -X POST http://localhost:8050/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin","password":"<ADMIN_PASSWORD>"}'

# Resumen del panel
curl -s -b cookies.txt http://localhost:8050/api/v1/dashboard/summary
```

```powershell
docker compose ps
Invoke-WebRequest -UseBasicParsing http://localhost:8050/health | Select-Object StatusCode
Invoke-RestMethod -Method Post http://localhost:8050/api/v1/auth/login `
  -ContentType "application/json" `
  -Body (@{ identifier = "admin"; password = $env:ADMIN_PASSWORD } | ConvertTo-Json) `
  -SessionVariable session
Invoke-RestMethod http://localhost:8050/api/v1/dashboard/summary -WebSession $session
```

## 11. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Define SECRET_KEY (>=64 chars) en .env` | Falta una variable obligatoria | Complete `.env` antes de `docker compose up`. |
| `debe ser aleatoria y de al menos 64 caracteres` | Secreto débil o con prefijo `dev-only`/`cambia-` | Genere uno nuevo con `secrets.token_urlsafe(64)`. |
| `port is already allocated` | Puerto ocupado | Cambie `APP_PORT` en `.env`. |
| `connection refused` al iniciar | PostgreSQL aún no listo | Compose espera el healthcheck; revise `docker compose logs db`. |
| Login devuelve 401 | Contraseña distinta a la del seed | Use `scripts/reset_admin.py` (ver §9). |
| Ruta sin geometría | OSRM no disponible | La ruta se guarda con advertencia; use “Recalcular” más tarde. |
| Simulador con 401 | `DEVICE_KEY` incorrecta o dispositivo eliminado | Genere una nueva clave con `POST /devices/{id}/rotate-key`. |
| Alertas de desconexión constantes | Umbral muy bajo | Ajuste `offline_timeout_seconds` en **Configuración**. |
| Clima no disponible | Open-Meteo inaccesible | El panel muestra el estado no disponible; no bloquea el resto. |

## 12. Producción

- Use HTTPS y mantenga `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax` (o `strict`) y
  `ENVIRONMENT=production`.
- No use credenciales por defecto: el arranque las rechaza.
- No exponga PostgreSQL fuera de la red interna.
- Configure respaldos periódicos **fuera del repositorio** y cifrados
  (ver [docs/ops/BACKUP-RESTORE.md](ops/BACKUP-RESTORE.md)).
- Coloque FrostBase detrás de un proxy inverso (Nginx, Caddy, Traefik) con TLS.
- El esquema se migra solo con Alembic (`AUTO_CREATE_TABLES=false`).
