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
