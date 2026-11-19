<div align="center">

<img src="frontend/assets/logo.png" alt="Frosty Dude" width="200" />

<h1>Frostbase</h1>

**Sistema de monitoreo y control de camiones refrigerados**

![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-%23009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

</div>

FrostBase es un panel web para monitorear camiones refrigerados. Permite registrar camiones, dispositivos IoT y rutas; recibe lecturas de temperatura, humedad y GPS; genera alertas cuando un valor sale de rango o un dispositivo se desconecta; y muestra todo en un mapa en vivo.

Incluye un simulador que emula un dispositivo ESP32-S3. No necesitas hardware real para probar el sistema.

---

## ¿Qué necesitas para empezar?

La forma recomendada es **Docker**: levanta la base de datos y la aplicación con un solo comando. Para ejecutar el panel no necesitas instalar Python, PostgreSQL ni Node.js en tu computadora.

| Requisito | Para qué | Cómo comprobarlo |
|---|---|---|
| **Docker Desktop** (Windows/macOS) o **Docker Engine** (Linux) | Ejecutar la aplicación y la base de datos | `docker --version` y `docker compose version` |
| **Git** (opcional) | Descargar y actualizar el proyecto | `git --version` |
| **Python 3.12+** (opcional) | Solo si vas a usar el simulador o desarrollar sin Docker | `python --version` |

> Si `docker --version` falla, instala [Docker Desktop](https://www.docker.com/products/docker-desktop/) (o Docker Engine en Linux) y ábrelo antes de continuar. En Windows y macOS debe estar iniciado y mostrando el estado **Running**.

---

## Inicio rápido con Docker (ruta recomendada)

> **Resumen:** copiar `.env.example` a `.env`, completar cuatro valores, ejecutar `docker compose up -d --build` y abrir `http://localhost:8050`. Los detalles están en los pasos siguientes.

Sigue los pasos en orden. Al final tendrás el panel funcionando en `http://localhost:8050`.

### Paso 1 · Descargar el proyecto

Con Git:

```bash
git clone https://github.com/SKSKronosUTT/frostbase-v2.git
cd frostbase-v2
```

Si no tienes Git, descarga el ZIP desde GitHub, descomprímelo y abre una terminal dentro de esa carpeta.

> Todos los comandos de esta guía se ejecutan **desde la carpeta raíz del proyecto** (donde está `compose.yml`).

### Paso 2 · Crear el archivo de configuración

El proyecto necesita un archivo `.env` con contraseñas y claves propias. No hay credenciales por defecto: si falta algo, la aplicación **no arranca** y te dice qué falta.

**2.1.** Copia el archivo de ejemplo:

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

**2.2.** Genera los cuatro valores obligatorios con este comando:

```bash
python -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24)); print('SECRET_KEY=' + secrets.token_urlsafe(64)); print('DEVICE_KEY_PEPPER=' + secrets.token_urlsafe(64)); print('ADMIN_PASSWORD=' + secrets.token_urlsafe(18))"
```

En macOS/Linux usa `python3` si `python` no existe. Si no tienes Python instalado, puedes ejecutar el mismo comando con Docker:

```bash
docker run --rm python:3.12-slim python -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24)); print('SECRET_KEY=' + secrets.token_urlsafe(64)); print('DEVICE_KEY_PEPPER=' + secrets.token_urlsafe(64)); print('ADMIN_PASSWORD=' + secrets.token_urlsafe(18))"
```

Obtendrás cuatro líneas parecidas a estas (los valores serán distintos):

```env
POSTGRES_PASSWORD=una-cadena-larga
SECRET_KEY=otra-cadena-de-64-o-mas-caracteres
DEVICE_KEY_PEPPER=otra-cadena-de-64-o-mas-caracteres
ADMIN_PASSWORD=una-contrasena-de-12-o-mas-caracteres
```

**2.3.** Abre `.env` con tu editor (Notepad, VS Code, etc.) y pega cada valor en su línea. Las líneas clave deben quedar así:

```env
POSTGRES_DB=frostbase
POSTGRES_USER=frostbase
POSTGRES_PASSWORD=<pega aquí el valor generado>
DATABASE_URL=postgresql+psycopg://frostbase:REEMPLAZAR@localhost:5432/frostbase
SECRET_KEY=<pega aquí el valor generado>
DEVICE_KEY_PEPPER=<pega aquí el valor generado>
ADMIN_PASSWORD=<pega aquí el valor generado>
```

Notas importantes:

- `DATABASE_URL` **puede quedarse como está** si vas a usar Docker: Compose construye la URL real apuntando al contenedor de base de datos.
- No uses los textos de ejemplo `cambia-...` ni `dev-only-...`: el arranque los rechaza a propósito.
- `ADMIN_PASSWORD` solo se usa cuando la base de datos está vacía y se crea el primer administrador. Si ya existe un administrador, cambia su contraseña con `scripts/reset_admin` (ver [Operación diaria](#operación-diaria)).
- No compartas el `.env` ni lo subas a Git. Ya está excluido por `.gitignore`.

**2.4.** Guarda el archivo como `.env` **en la raíz del proyecto**, junto a `compose.yml`. Si lo guardas en otra carpeta, Docker no lo encontrará.

Comprueba que la configuración se puede leer (no arranca nada, solo valida):

```bash
docker compose config --quiet
```

- Si no muestra nada, todo está correcto.
- Si muestra un error como `required variable SECRET_KEY is missing`, revisa el Paso 2 y completa ese valor.

### Paso 3 · Levantar la aplicación

```bash
docker compose up -d --build
```

La primera vez tarda varios minutos porque descarga y construye la imagen. Cuando termine, comprueba que todo esté sano:

```bash
docker compose ps
```

Deberías ver dos servicios, `frostbase-v4-db` y `frostbase-v4-app`, con estado **healthy** o **running**. Si quieres ver el arranque en vivo:

```bash
docker compose logs -f app
```

> `Ctrl+C` sale de los logs, pero **no detiene** la aplicación.

### Paso 4 · Abrir el panel e iniciar sesión

Abre en tu navegador:

**http://localhost:8050**

Usa estas credenciales:

| Campo | Valor |
|---|---|
| Usuario | `admin` |
| Contraseña | El valor que pusiste en `ADMIN_PASSWORD` dentro de `.env` |

Si la base de datos ya tenía un administrador creado antes de la actualización de seguridad (migración `0002_admin_auth_policy`), el panel mostrará un **modal obligatorio** para cambiar la contraseña. La nueva contraseña debe tener **12 caracteres o más**, ser distinta de la actual y no contener el nombre de usuario. En una instalación nueva no aparece ese modal.

### Paso 5 (opcional) · Cargar datos de demostración

Para tener camiones, rutas y dispositivos de ejemplo:

```bash
docker compose exec app python -m scripts.seed_demo
```

El comando crea una ruta en Tijuana, 3 camiones y 2 dispositivos. **Imprime las claves de los dispositivos una sola vez**: cópialas si vas a usar el simulador.

> Ejecutar el seed varias veces no duplica camiones ni dispositivos, pero sí puede crear rutas nuevas (se corrige en la Fase 4 del plan).

---

## ¿Todo funciona?

Haz estas tres comprobaciones rápidas:

1. **Servicios activos:**

   ```bash
   docker compose ps
   ```

   Ambos servicios deben aparecer como `healthy` o `running`.

2. **API viva:**

   ```bash
   curl http://localhost:8050/health
   ```

   Respuesta esperada:

   ```json
   {"status":"ok","service":"FrostBase"}
   ```

3. **Panel visible:** abre `http://localhost:8050` y entra con `admin` y tu `ADMIN_PASSWORD`.

Si algo falla, revisa [Problemas comunes](#problemas-comunes) o los logs:

```bash
docker compose logs --tail 100 app
```

---

## Usar el simulador IoT (opcional)

El simulador envía una lectura cada 10 segundos y mueve un camión sobre la ruta asignada. Sirve para ver el panel con datos en vivo sin un ESP32 real.

**Requisitos:** Python 3.12 o superior y los datos de demostración cargados (Paso 5).

### Windows (PowerShell)

```powershell
cd iot-simulator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python simulator.py
```

Si PowerShell bloquea la activación del entorno virtual, ejecuta una vez:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### macOS / Linux

```bash
cd iot-simulator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python simulator.py
```

### Contenido de `iot-simulator/.env`

```env
FROSTBASE_API_URL=http://localhost:8050/api/v1
DEVICE_ID=ESP32-FROST-001
DEVICE_KEY=<la clave que imprimió el seed>
```

- Si cambiaste `APP_PORT`, actualiza también `FROSTBASE_API_URL` (por ejemplo, `http://localhost:8060/api/v1`).
- Si perdiste la clave del dispositivo, genera una nueva desde el panel (Flota → dispositivo → rotar clave) o con `POST /api/v1/devices/{id}/rotate-key`.

Cuando el simulador arranque, verás una lectura cada 10 segundos y el camión aparecerá en el mapa. Para detenerlo, `Ctrl+C`.

---

## Operación diaria

| Quiero… | Comando |
|---|---|
| Ver los logs de la aplicación | `docker compose logs -f app` |
| Detener sin borrar datos | `docker compose down` |
| Volver a arrancar | `docker compose up -d` |
| Reiniciar tras cambiar código | `docker compose up -d --build` |
| Actualizar desde Git | `git pull` y luego `docker compose up -d --build` |
| Ver el estado | `docker compose ps` |
| Restablecer la contraseña del admin | `docker compose exec app python -m scripts.reset_admin` |
| Respaldar la base de datos | Ver [docs/ops/BACKUP-RESTORE.md](docs/ops/BACKUP-RESTORE.md) |

> ⚠️ **Borrar todos los datos** (camiones, lecturas, alertas y usuarios) es destructivo:
>
> ```bash
> docker compose down -v
> ```
>
> Úsalo solo si quieres empezar de cero. Al volver a arrancar, el administrador se crea de nuevo con `ADMIN_PASSWORD`.

### Cambiar la contraseña del administrador

Desde el panel: **Configuración → Cuenta de administrador → Cambiar contraseña**.

Si no puedes entrar, restablece la contraseña desde la terminal:

```bash
docker compose exec app python -m scripts.reset_admin
```

Ese comando usa `ADMIN_PASSWORD` del `.env`, invalida las sesiones activas y obliga a cambiarla en el siguiente login. Si quieres conservar exactamente esa contraseña sin el cambio forzado:

```bash
docker compose exec app python -m scripts.reset_admin --clear-must-change
```

### Cambiar el puerto

Si el puerto `8050` está ocupado, edita `.env`:

```env
APP_PORT=8060
```

Luego reinicia:

```bash
docker compose up -d
```

No olvides actualizar `FROSTBASE_API_URL` en `iot-simulator/.env` si usas el simulador.

---

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `required variable SECRET_KEY is missing` | Falta un valor en `.env` | Completa `SECRET_KEY`, `DEVICE_KEY_PEPPER`, `ADMIN_PASSWORD` y `POSTGRES_PASSWORD`. |
| `debe ser aleatoria y de al menos 64 caracteres` | Se dejó un texto de ejemplo o una clave corta | Genera una clave nueva con el comando del Paso 2. |
| `Cannot connect to the Docker daemon` | Docker Desktop no está iniciado | Abre Docker Desktop y espera a que esté **Running**. |
| `port is already allocated` | El puerto `8050` está ocupado | Cambia `APP_PORT` en `.env` (por ejemplo, `8060`) y reinicia. |
| La página no carga | La aplicación aún está arrancando | Espera unos segundos y revisa `docker compose ps` y `docker compose logs app`. |
| La aplicación se reinicia en bucle | Error de configuración al arrancar | Revisa `docker compose logs app`; corrige el valor indicado en `.env` y ejecuta `docker compose up -d`. |
| `AUTO_CREATE_TABLES debe ser false en producción` | `ENVIRONMENT=production` con creación automática de tablas | Mantén `AUTO_CREATE_TABLES=false`; el esquema lo aplica Alembic al arrancar. |
| Login devuelve error 401 | La contraseña no coincide con la del administrador existente | Ejecuta `docker compose exec app python -m scripts.reset_admin`. |
| `password authentication failed for user "frostbase"` | Cambiaste `POSTGRES_PASSWORD` después del primer arranque | Vuelve a poner la contraseña anterior en `.env` o rota la contraseña dentro de PostgreSQL (ver abajo). |
| El login “funciona” pero luego vuelve al login | Estás accediendo por una IP de red con HTTP y `COOKIE_SECURE=true` | Usa `http://localhost` o, solo para pruebas en red, pon `COOKIE_SECURE=false` y reinicia. En producción usa HTTPS. |
| El simulador recibe 401 | `DEVICE_KEY` incorrecta o dispositivo eliminado | Rota la clave del dispositivo desde el panel y actualiza `iot-simulator/.env`. |
| El simulador no conecta | Puerto distinto o API URL incorrecta | Revisa `FROSTBASE_API_URL` en `iot-simulator/.env`. |
| El seed no imprime claves | Los dispositivos ya existían | Rota la clave desde el panel; el seed solo imprime claves al crearlas. |

### Si cambiaste la contraseña de PostgreSQL después del primer arranque

El volumen de PostgreSQL conserva la contraseña con la que se creó. Si actualizas `POSTGRES_PASSWORD` en `.env`, la aplicación no podrá conectarse. Tienes dos opciones:

1. **Volver a la contraseña anterior** en `.env` (lo más simple si no recuerdas la nueva).
2. **Rotar la contraseña dentro de PostgreSQL** y luego reiniciar:

   ```bash
   docker compose exec db psql -U frostbase -d postgres -c "ALTER USER frostbase WITH PASSWORD 'NUEVA_CONTRASENA';"
   ```

   Después actualiza `POSTGRES_PASSWORD` en `.env` y ejecuta `docker compose up -d`.

---

## Desarrollo local sin Docker (avanzado)

<details>
<summary>Mostrar instrucciones para ejecutar el backend con Python y PostgreSQL locales</summary>

**Requisitos:** Python 3.12+, PostgreSQL 16 en `localhost:5432` y las herramientas de compilación de Python.

1. Crea la base de datos y el usuario (ajusta la contraseña):

   ```bash
   psql -U postgres -c "CREATE USER frostbase WITH PASSWORD 'TU_CONTRASENA';"
   psql -U postgres -c "CREATE DATABASE frostbase OWNER frostbase;"
   ```

2. Copia las variables **dentro de `backend/`** (el backend lee `.env` desde su directorio de trabajo):

   ```bash
   cp .env.example backend/.env
   ```

   ```powershell
   Copy-Item .env.example backend\.env
   ```

3. Edita `backend/.env` y ajusta al menos:

   ```env
   DATABASE_URL=postgresql+psycopg://frostbase:TU_CONTRASENA@localhost:5432/frostbase
   SECRET_KEY=<clave de 64+ caracteres>
   DEVICE_KEY_PEPPER=<clave de 64+ caracteres>
   ADMIN_PASSWORD=<contraseña de 12+ caracteres>
   POSTGRES_PASSWORD=<contraseña de la base>
   ENVIRONMENT=development
   COOKIE_SECURE=false
   ```

   En desarrollo local puedes usar `ENVIRONMENT=development` y `COOKIE_SECURE=false` porque no hay HTTPS. **No uses esa combinación en producción.**

4. Instala dependencias, aplica migraciones y arranca:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8050
   ```

5. Abre `http://localhost:8050`. El frontend se sirve automáticamente desde `../frontend`.

> El esquema lo controla Alembic. Mantén `AUTO_CREATE_TABLES=false`; `create_all` solo se usa en pruebas automatizadas.
>
> Para detener el servidor: `Ctrl+C`. Para volver a arrancar: activa el entorno virtual y ejecuta `uvicorn app.main:app --reload`.

</details>

---

## ¿Qué hay dentro del proyecto?

| Carpeta / archivo | Contenido |
|---|---|
| `compose.yml` | Servicios de Docker: aplicación y PostgreSQL. |
| `.env.example` | Plantilla de configuración. Copiar a `.env` y completar. |
| `backend/` | API en FastAPI, modelos, servicios, migraciones Alembic y scripts. |
| `frontend/` | Panel web en HTML, CSS y JavaScript (sin build). |
| `iot-simulator/` | Simulador del dispositivo ESP32-S3. |
| `docs/` | Instalación, API, base de datos, integración IoT y respaldos. |
| `PLAN-MEJORA.md` | Auditoría técnica y plan de mejora por fases. |

Flujo simplificado:

```text
Navegador  →  FastAPI (backend)  →  PostgreSQL
                    ↑
        Simulador / ESP32-S3 (API IoT)
```

---

## Documentación

| Documento | Cuándo consultarlo |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Instalación detallada, variables, cambio y recuperación de contraseña. |
| [docs/API.md](docs/API.md) | Endpoints, ejemplos de peticiones y respuestas. |
| [docs/DATABASE.md](docs/DATABASE.md) | Tablas, relaciones y columnas. |
| [docs/IOT-INTEGRATION.md](docs/IOT-INTEGRATION.md) | Integración de firmware ESP32-S3. |
| [docs/ops/BACKUP-RESTORE.md](docs/ops/BACKUP-RESTORE.md) | Respaldo, restauración probada, RPO y RTO. |
| [PLAN-MEJORA.md](PLAN-MEJORA.md) | Estado de la remediación técnica y tareas pendientes. |

---

## Seguridad

- El arranque falla si faltan `SECRET_KEY`, `DEVICE_KEY_PEPPER`, `ADMIN_PASSWORD` o `POSTGRES_PASSWORD`.
- Las contraseñas se guardan con Argon2 y las claves de dispositivo se almacenan hasheadas.
- Los JWT viajan en cookies `HttpOnly`; en producción se exige `COOKIE_SECURE=true` y HTTPS.
- Cambiar la contraseña incrementa `token_version` y revoca los JWT anteriores.
- Nunca subas `.env`, respaldos ni claves reales al repositorio.
- Para exponer la aplicación fuera de `localhost`, usa HTTPS y un proxy inverso; revisa la sección de producción en [docs/INSTALLATION.md](docs/INSTALLATION.md).

---

## Contribuir y plan de mejora

Antes de modificar código, lee **[PLAN-MEJORA.md](PLAN-MEJORA.md)**. Allí están las fases, dependencias, criterios de aceptación y el registro de progreso.

- Trabaja sobre la rama de la fase correspondiente (`feat/f1-secure-config`, `feat/f2-auth-iot-integrity`, etc.).
- No adelantes tareas de fases posteriores.
- Actualiza el registro §9 del plan al terminar una tarea.

> ✅ **Tareas de la Fase 1 completadas:** configuración segura y fail-fast, `.env` regenerado, Alembic gobernando el esquema, política de contraseña con revocación de JWT e higiene de respaldos. Queda pendiente la regresión manual del gate F1 (navegador + simulador). El estado de las fases restantes está en `PLAN-MEJORA.md` §9.
