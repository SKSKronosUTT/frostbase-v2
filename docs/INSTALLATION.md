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

## 2. Variables de entorno

Copie el archivo de ejemplo y edítelo:

```bash
cp .env.example .env
```

Variables principales:

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `POSTGRES_DB` | Nombre de la base | `frostbase` |
| `POSTGRES_USER` | Usuario de PostgreSQL | `frostbase` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | — |
| `DATABASE_URL` | URL SQLAlchemy (uso local) | `postgresql+psycopg://...` |
| `SECRET_KEY` | Clave para firmar JWT (mín. 64 caracteres) | — |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración de la sesión | `720` |
| `COOKIE_SECURE` | Cookie solo por HTTPS | `false` |
| `COOKIE_SAMESITE` | Política SameSite de la cookie | `lax` |
| `ADMIN_USERNAME` | Usuario administrador inicial | `admin` |
| `ADMIN_EMAIL` | Correo del administrador | `admin@frostbase.local` |
| `ADMIN_PASSWORD` | Contraseña inicial | `ChangeMe123!` |
| `APP_PORT` | Puerto publicado del contenedor | `8000` |
| `ENVIRONMENT` | Entorno (`development`/`production`) | `development` |
| `AUTO_CREATE_TABLES` | Crear tablas al iniciar (sin Alembic) | `true` |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma | localhost |
| `DEVICE_OFFLINE_SECONDS` | Umbral de desconexión (segundos) | `60` |
| `DASHBOARD_FRESH_MINUTES` | Ventana de vigencia del panel | `10` |
| `DISCONNECT_CHECK_SECONDS` | Frecuencia del detector de desconexiones | `30` |
| `OSRM_BASE_URL` | Servidor de ruteo | `https://router.project-osrm.org` |
| `WEATHER_CITY` | Ciudad para el clima | `Tijuana` |
| `WEATHER_LATITUDE` / `WEATHER_LONGITUDE` | Coordenadas del clima | Tijuana |
| `WEATHER_CACHE_SECONDS` | Caché de clima | `600` |
| `FRONTEND_DIR` | Ruta alternativa del frontend | autodetectado |

Genere una clave secreta:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

> En Docker Compose, la `DATABASE_URL` del contenedor se construye automáticamente con el host `db`. La variable del `.env` se usa para ejecución local.

## 3. Arranque con Docker Compose

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

Secuencia de arranque:

1. `db` inicia PostgreSQL 16 y espera el healthcheck.
2. `app` ejecuta `alembic upgrade head`.
3. Se crea el administrador si la tabla está vacía.
4. Uvicorn escucha en el puerto `8000` interno, publicado como `APP_PORT`.
5. El frontend se sirve en `/`.

Acceso: `http://localhost:${APP_PORT}`.

Si el puerto está ocupado, ajuste `APP_PORT` en `.env` y reinicie:

```bash
docker compose up -d
```

## 4. Datos de demostración

```bash
docker compose exec app python -m scripts.seed_demo
```

Crea:

- Ruta **Villa Fontana - Playas de Tijuana** con geometría OSRM y 3 puntos.
- Camiones `ABC-123-A` (en ruta), `JKL-456-B` (disponible) y `XYZ-789-C` (mantenimiento).
- Dispositivos `ESP32-FROST-001` y `ESP32-FROST-002` con claves impresas una sola vez.

El seed es idempotente para camiones/dispositivos por placa/ID, aunque crea una ruta nueva en cada ejecución.

## 5. Ejecución local

Requisitos: PostgreSQL 16 en `localhost:5432` y base `frostbase`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
# Edite DATABASE_URL si es necesario

cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

El backend resuelve `FRONTEND_DIR` o busca `../frontend` relativo al paquete. En desarrollo puede servir el frontend con `python -m http.server` dentro de `frontend/`, pero entonces deberá ajustar `CORS_ORIGINS` y la base de la API.

## 6. Migraciones y respaldos

```bash
# Nueva migración (desde backend/)
alembic revision --autogenerate -m "cambio"
alembic upgrade head
alembic downgrade -1

# Respaldo de datos
docker compose exec -T db pg_dump -U frostbase frostbase > respaldo.sql

# Restauración
cat respaldo.sql | docker compose exec -T db psql -U frostbase -d frostbase
```

## 7. Verificación rápida

```bash
# Estado de servicios
docker compose ps

# Salud de la API (Swagger)
curl -o /dev/null -w "%{http_code}\n" http://localhost:8000/docs

# Login
curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin","password":"ChangeMe123!"}'

# Resumen del panel
curl -s -b cookies.txt http://localhost:8000/api/v1/dashboard/summary
```

## 8. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `port is already allocated` | Puerto ocupado | Cambie `APP_PORT` en `.env` |
| `connection refused` al iniciar | PostgreSQL aún no listo | Compose espera el healthcheck; revise `docker compose logs db` |
| Login devuelve 401 | Contraseña distinta a la del seed | El admin solo se crea con la BD vacía; reinicie el volumen o actualice la contraseña en BD |
| Ruta sin geometría | OSRM no disponible | La ruta se guarda con advertencia; use “Recalcular” más tarde |
| Simulador con 401 | `DEVICE_KEY` incorrecta o dispositivo eliminado | Genere una nueva clave con `POST /devices/{id}/rotate-key` |
| Alertas de desconexión constantes | `DEVICE_OFFLINE_SECONDS` muy bajo | Ajuste el valor en `.env` o en Configuración |
| Clima no disponible | Open-Meteo inaccesible | El panel muestra el estado no disponible; no bloquea el resto |

## 9. Producción

- Use HTTPS y configure `COOKIE_SECURE=true` y `COOKIE_SAMESITE=lax` (o `strict`).
- Cambie todas las contraseñas por defecto y `SECRET_KEY`.
- No exponga PostgreSQL fuera de la red interna.
- Configure respaldos periódicos del volumen `frostbase_v3_pgdata`.
- Coloque FrostBase detrás de un proxy inverso (Nginx, Caddy, Traefik) con TLS.
