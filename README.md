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

```bash
docker compose up -d --build
docker compose logs -f app
```

La aplicación queda disponible en `http://localhost:${APP_PORT}` (por defecto `http://localhost:8050`). Al arrancar se ejecuta `alembic upgrade head`, se crea el administrador inicial si no existe y se monta el frontend en la raíz.

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


## Seguridad

- Las contraseñas de administrador se almacenan con Argon2.
- Las claves de dispositivo se almacenan hasheadas y se comparan de forma segura.
- Los JWT se envían en cookies `HttpOnly`; en producción configure `COOKIE_SECURE=true` y use HTTPS.
- No incluya `.env` ni claves reales en el repositorio.

## Plan de mejora

El repositorio tiene una auditoría técnica con un plan de remediación vigente en **[PLAN-MEJORA.md](PLAN-MEJORA.md)** (3 etapas, 4 fases, 39 tareas con criterios de aceptación y registro de progreso).

Si vas a contribuir —o eres un agente de IA de desarrollo— lee ese documento antes de modificar código y trabaja únicamente sobre la etapa y tarea asignadas.

> ⚠️ El estado actual arranca con secretos y credenciales por defecto. Antes de exponer la aplicación fuera de `localhost`, complete la **Fase 1** del plan.
