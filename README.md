<div align="center">

<img src="frontend/assets/logo.png" alt="Frosty Dude" width="200" />

<h1>Frostbase</h1>

**Sistema de monitoreo y control de camiones refrigerados**


![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-%23009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
</div>


FrostBase es un sistema web de monitoreo para camiones refrigerados. Permite registrar camiones, dispositivos IoT y rutas de reparto, recibir lecturas de temperatura, humedad y GPS en tiempo real, evaluar umbrales configurables y generar alertas automáticas por condiciones fuera de rango o desconexión de dispositivos.

Incluye un panel con mapa en vivo, historial de lecturas, gestión de alertas, configuración global de umbrales y un simulador independiente que emula un dispositivo ESP32-S3 enviando datos por la API real.

## Inicio con Docker

1. Copie el archivo de ejemplo y complete los **secretos obligatorios**:

   ```powershell
   Copy-Item .env.example .env
   ```

   ```bash
   cp .env.example .env
   ```

   Genere `SECRET_KEY` y `DEVICE_KEY_PEPPER` con:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

2. Levante el stack (el archivo es `compose.yml`):

   ```bash
   docker compose up -d --build
   docker compose logs -f app
   ```

La aplicación queda disponible en `http://localhost:${APP_PORT}` (por defecto `http://localhost:8050`). Al arrancar, el contenedor aplica `alembic upgrade head` con un *advisory lock*, crea el administrador inicial si no existe y monta el frontend en la raíz.

> El proceso **se niega a arrancar** si falta `SECRET_KEY`, `DEVICE_KEY_PEPPER`, `ADMIN_PASSWORD` o `POSTGRES_PASSWORD`, o si los secretos no cumplen la longitud mínima. No hay credenciales por defecto.

Si el puerto `8050` está ocupado, cambie `APP_PORT` en `.env` a `8060` o `8070` y actualice `FROSTBASE_API_URL` en `iot-simulator/.env` con el mismo puerto.

Para cargar datos de demostración (ruta en Tijuana, 3 camiones y 2 dispositivos):

```bash
docker compose exec app python -m scripts.seed_demo
```

El seed imprime **una sola vez** las claves de los dispositivos. Guárdelas para el simulador.

Detener servicios:

```bash
docker compose down
```

Borrar también los datos (destructivo):

```bash
docker compose down -v
```

## Iniciar el simulador IoT

```bash
cd iot-simulator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

```powershell
cd iot-simulator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure en `iot-simulator/.env`:

```env
FROSTBASE_API_URL=http://localhost:8050/api/v1
DEVICE_ID=ESP32-FROST-001
DEVICE_KEY=<clave impresa por el seed o al crear el dispositivo>
```

Ejecute:

```bash
python simulator.py
```

El simulador envía una lectura cada 10 segundos, se desplaza sobre la geometría de la ruta asignada y genera anomalías con 1 % de probabilidad. Tolera caídas temporales del servidor y reintenta la conexión.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Instalación, variables reales, cambio y recuperación de contraseña |
| [docs/API.md](docs/API.md) | Contratos de la API administrativa e IoT |
| [docs/DATABASE.md](docs/DATABASE.md) | Esquema y relaciones |
| [docs/IOT-INTEGRATION.md](docs/IOT-INTEGRATION.md) | Integración de firmware ESP32-S3 |
| [docs/ops/BACKUP-RESTORE.md](docs/ops/BACKUP-RESTORE.md) | Respaldo, restauración probada, RPO y RTO |
| [PLAN-MEJORA.md](PLAN-MEJORA.md) | Auditoría técnica y plan de remediación por fases |

## Seguridad

- El arranque valida `SECRET_KEY`, `DEVICE_KEY_PEPPER` y `ADMIN_PASSWORD` (fail-fast, sin defaults).
- Las contraseñas de administrador se almacenan con Argon2.
- Las claves de dispositivo se almacenan hasheadas y se comparan de forma segura.
- Los JWT se envían en cookies `HttpOnly`; en producción `COOKIE_SECURE=true` y HTTPS son obligatorios.
- El cambio de contraseña incrementa `token_version` y revoca los JWT anteriores.
- Si la base existía antes de la migración `0002_admin_auth_policy`, se fuerza un cambio de contraseña en el primer login.
- Recuperación de acceso: `docker compose exec app python -m scripts.reset_admin`.
- No incluya `.env`, dumps ni claves reales en el repositorio.

## Plan de mejora

El repositorio tiene una auditoría técnica con un plan de remediación vigente en **[PLAN-MEJORA.md](PLAN-MEJORA.md)** (3 etapas, 4 fases, 39 tareas con criterios de aceptación y registro de progreso).

Si vas a contribuir —o eres un agente de IA de desarrollo— lee ese documento antes de modificar código y trabaja únicamente sobre la etapa y tarea asignadas.

> ✅ **Tareas de la Fase 1 completadas:** configuración segura y fail-fast, `.env` regenerado, Alembic gobernando el esquema, política de contraseña con revocación de JWT e higiene de respaldos. Queda pendiente la regresión manual del gate F1 (navegador + simulador). Consulte el registro de progreso en `PLAN-MEJORA.md` §9 para el estado de las fases restantes.
