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

Deberías ver tres servicios: `frostbase-v4-db`, `frostbase-v4-app` y `frostbase-v4-watcher`, con estado **healthy** o **running**. La aplicación corre con un usuario **no root** y el contenedor incluye un `HEALTHCHECK` contra `/health/ready`. Si quieres ver el arranque en vivo:

```bash
docker compose logs -f app
docker compose logs -f watcher
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

### Paso 5 · Datos de demostración (automáticos)

Con `SEED_DEMO_DATA=true` (valor por defecto en `.env.example`), **el primer arranque siembra solo** un conjunto demo completo y coherente: 4 camiones, 4 conductores, 3 tiendas, 4 rutas, lecturas de las últimas 24 h, viajes (uno en curso), alertas y eventos de puerta. No hay que ejecutar nada.

Para explorar la demo:

| Rol | Credenciales |
|---|---|
| Administrador | `admin` + tu `ADMIN_PASSWORD` |
| Conductor con viaje en curso | `carlos.rivera@demo.frostbase.local` / `Demo1234!` |
| Conductor listo para iniciar viaje | `ana.morales@demo.frostbase.local` / `Demo1234!` |
| Conductor bloqueado (sin ruta hoy) | `luis.hernandez@demo.frostbase.local` / `Demo1234!` |

> Las contraseñas demo son fijas y **solo para desarrollo/demostración**. El
> arranque falla si `SEED_DEMO_DATA=true` con `ENVIRONMENT=production`.

El seed es **idempotente**: reiniciar el stack no duplica datos. Las claves de
los dispositivos demo se imprimen **una sola vez** en los logs del arranque;
para el simulador:

```bash
# Ver la clave de ESP32-DEMO-001 en los logs del primer arranque
docker compose logs app | Select-String "DEMO DEVICE KEY"
```

Opciones útiles:

```bash
# Volver a sembrar desde cero (borra SOLO los datos demo, no los reales)
docker compose exec app python -m scripts.seed_demo --reset-demo

# Mostrar las claves generadas en esta ejecución (solo en la primera creación)
docker compose exec app python -m scripts.seed_demo --print-keys

# Datos extra para pruebas de carga
docker compose exec app python -m scripts.seed_demo --trucks 50 --devices 50

# Arrancar sin datos demo: SEED_DEMO_DATA=false en .env y recrear la app
docker compose up -d --force-recreate app
```

También puede lanzarse con `.\tasks.ps1 seed` (o `.\tasks.ps1 seed -Reset`) y
`make seed` en Linux/macOS.

---

## ¿Todo funciona?

Haz estas tres comprobaciones rápidas:

1. **Servicios activos:**

   ```bash
   docker compose ps
   ```

   Deben aparecer `frostbase-v4-db`, `frostbase-v4-app` y
   `frostbase-v4-watcher` como `healthy` o `running`.

2. **API y esquema listos:**

   ```bash
   curl http://localhost:8050/health/ready
   ```

   Respuesta esperada:

   ```json
   {"status":"ready","service":"FrostBase","schema":"0010_trips_orders_door"}
   ```

   `/health/live` solo comprueba el proceso; `/health/ready` verifica PostgreSQL y
   que Alembic esté en la última revisión.

3. **Panel visible:** abre `http://localhost:8050` y entra con `admin` y tu `ADMIN_PASSWORD`.

Si algo falla, revisa [Problemas comunes](#problemas-comunes) o los logs:

```bash
docker compose logs --tail 100 app
```

---

## Módulo de conductores

Además del panel del administrador, FrostBase incluye un **portal para conductores** (`http://localhost:8050/driver.html`), pensado para el celular del conductor:

- **Contenedor en vivo**: temperatura, humedad y estado de la **puerta** (abierta/cerrada) con umbrales efectivos del camión, refresco cada 5 s.
- **Ruta de hoy** con calendario semanal por conductor.
- **Viajes**: iniciar viaje (con motivo claro si está bloqueado), entregar orden por orden, marcar no entregadas con motivo obligatorio, finalizar con confirmación e historial.
- **Alertas** de cadena de frío (temperatura, humedad, desconexión) y de **apertura de puerta no autorizada** durante el viaje; el conductor puede reconocerlas.

El administrador gestiona conductores desde **Conductores** en el panel: alta con contraseña temporal visible una sola vez, edición, baja lógica (que invalida sus sesiones de inmediato), reset de contraseña y asignación de camión. Cada ruta pertenece a un conductor con días de la semana (0 = domingo).

La documentación de endpoints está en `docs/API.md`; la revisión de seguridad y la prueba de carga (999 usuarios) en `docs/ops/`.

---

## Asistente IA (opcional)

El panel incluye un apartado **Asistente IA** (`/ai.html`) para consultar la
flota en lenguaje natural. El agente corre en un **ESP32-S3 con ESP-Claw** y el
backend actúa de proxy (el navegador nunca habla con el dispositivo).

Requisitos:

1. El ESP32 debe estar en la misma red que el backend (LAN) o accesible por su
   AP. Se recomienda la IP de la LAN.
2. En `.env`:
   ```env
   AI_AGENT_ENABLED=true
   AI_AGENT_URL=http://192.168.100.52
   ```
3. Recrear la app: `docker compose up -d --force-recreate app`.
4. En la consola del ESP32: habilitar `cap_http_request` (Capabilities) y
   permitir el host del backend en *Network Requests* si se usará el modo
   *pull*.

El asistente responde con un resumen de datos actuales (alertas, flota, viajes
y rutas). Las **sugerencias rápidas** se calculan en el servidor sin LLM
(respuesta instantánea y sin consumir cuota) y se etiquetan «Datos del sistema».
Las consultas libres pasan por el modelo externo configurado en el ESP32
(DeepSeek) y el texto del chat no se guarda en el servidor. Detalles técnicos en
`docs/AI-AGENT.md` (incluye los endpoints `agent-read` con token de solo lectura
para que el agente consulte datos frescos). El uso se audita sin guardar el
texto del chat y se resume en `GET /api/v1/ai/metrics`.

---

## Usar el simulador IoT (opcional)

El simulador envía una lectura cada 10 segundos y mueve un camión sobre la ruta asignada. Sirve para ver el panel con datos en vivo sin un ESP32 real.

**Requisitos:** Python 3.12 o superior y los datos de demostración cargados (Paso 5).

> ⚠️ **`DEVICE_KEY` no es la placa del camión.** `ABC-123-A` es la matrícula. La clave es una cadena larga (≈43 caracteres) que el seed imprime **una sola vez** al crear el dispositivo.

### 1. Obtener la clave del dispositivo

- Si acabas de arrancar la app con datos demo, busca la línea `DEMO DEVICE KEY ESP32-DEMO-001: ...` en `docker compose logs app` y copia la cadena larga.
- Si no tienes la clave o perdiste la salida del seed, genera una nueva:

  ```bash
  docker compose exec app python -m scripts.rotate_device_key --device-id ESP32-DEMO-001
  ```

  El comando imprime una línea `DEVICE_KEY=...` **una sola vez**. La clave anterior deja de funcionar.
- También puedes rotarla desde el panel: **Flota → dispositivo → Rotar clave**.

### 2. Configurar y arrancar

#### Windows (PowerShell)

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

#### macOS / Linux

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
DEVICE_ID=ESP32-DEMO-001
DEVICE_KEY=<cadena larga de ~43 caracteres; NO es la placa ABC-123-A>
```

- Si cambiaste `APP_PORT`, actualiza también `FROSTBASE_API_URL` (por ejemplo, `http://localhost:8060/api/v1`).
- Si perdiste la clave del dispositivo, usa el comando de rotación de arriba.
- Para simular la **puerta del contenedor** (Reed Switch), agrega
  `DOOR_OPEN_PROBABILITY=0.2` al `.env`: el simulador abrirá la puerta al azar
  y la cerrará tras `DOOR_OPEN_CYCLES` lecturas (por defecto 3). Si el camión
  está en un viaje sin entrega en curso, se generará la alerta de apertura no
  autorizada tras el periodo de gracia (30 s por defecto).

### Si el simulador muestra `401 Unauthorized`

Significa que `DEVICE_KEY` no corresponde a `DEVICE_ID` (por ejemplo, porque se copió la placa `ABC-123-A` o una clave antigua). Para corregirlo:

1. Rota la clave con el comando de la sección 1.
2. Copia el valor de `DEVICE_KEY=...` en `iot-simulator/.env`.
3. Detén y vuelve a arrancar `python simulator.py`; el `.env` se lee al iniciar.

Comprobación rápida en macOS/Linux:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8050/api/v1/iot/config \
  -H "X-Device-Id: ESP32-DEMO-001" \
  -H "X-Device-Key: <tu clave>"
```

Debe responder `200`. En Windows usa `curl.exe` (PowerShell puede interpretar `curl` como alias).

Cuando el simulador arranque, verás una lectura cada 10 segundos y el camión aparecerá en el mapa. Para detenerlo, `Ctrl+C`.

---

## Pruebas automatizadas (opcional)

La suite usa un PostgreSQL 16 real y recrea el esquema con Alembic. Requiere Python 3.12+.

```bash
docker compose -f compose.test.yml up -d --wait

cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
pytest --cov=app --cov-report=term-missing
```

Resultado esperado: **195 passed** y cobertura **≥ 70 %** (actual: 85 %). Para limpiar la base de pruebas:

```bash
docker compose -f compose.test.yml down
```

---

## Operación diaria

| Quiero… | Comando |
|---|---|
| Ver los logs de la aplicación | `docker compose logs -f app` |
| Ver los logs del watcher | `docker compose logs -f watcher` |
| Detener sin borrar datos | `docker compose down` |
| Volver a arrancar | `docker compose up -d` |
| Reiniciar tras cambiar código | `docker compose up -d --build` |
| Actualizar desde Git | `git pull` y luego `docker compose up -d --build` |
| Ver el estado | `docker compose ps` |
| Restablecer la contraseña del admin | `docker compose exec app python -m scripts.reset_admin` |
| Rotar la clave de un dispositivo | `docker compose exec app python -m scripts.rotate_device_key --device-id ESP32-DEMO-001` |
| Respaldar la base de datos | `.\tasks.ps1 backup` (Linux: `make backup`) — ver [docs/ops/BACKUP-RESTORE.md](docs/ops/BACKUP-RESTORE.md) |
| Prueba de carga del portal | `python -m scripts.loadtest_portal --users 999 --duration 60` (ver [docs/ops/perf-baseline.md](docs/ops/perf-baseline.md)) |

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
| El simulador recibe 401 | `DEVICE_KEY` es la placa (`ABC-123-A`), una clave antigua o el dispositivo no existe | Rota la clave: `docker compose exec app python -m scripts.rotate_device_key --device-id ESP32-DEMO-001`; copia el valor en `iot-simulator/.env` y reinicia. |
| El simulador no conecta | Puerto distinto o API URL incorrecta | Revisa `FROSTBASE_API_URL` en `iot-simulator/.env`. |
| El seed no imprime claves | Los dispositivos ya existían | Rota la clave con `scripts.rotate_device_key` o desde el panel. |
| Quiero empezar sin datos demo | `SEED_DEMO_DATA=true` en el arranque | Pon `SEED_DEMO_DATA=false` en `.env`, recrea la app y borra la base si ya se sembró (`docker compose down -v`). |

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

5. Abre `http://localhost:8050`. El frontend se sirve automáticamente desde `../frontend` o, si existe, desde `../frontend/build`.

> Para probar el build de producción en local:
>
> ```bash
> cd frontend
> npm ci
> npm run build
> ```
>
> El backend detecta `frontend/build/index.html` y sirve los assets hasheados con caché inmutable. Sin build sirve el código fuente.

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
| `frontend/` | Panel web en HTML, CSS y JavaScript. `npm run build` genera `frontend/build` con assets hasheados. |
| `frontend/tests/e2e/` | Flujos críticos con Playwright (login, flota, rutas, alertas, configuración). |
| `iot-simulator/` | Simulador del dispositivo ESP32-S3. |
| `deploy/nginx.conf` | Proxy inverso de referencia con TLS, gzip y rate limit. |
| `tasks.ps1` / `Makefile` | Tareas `dev`, `test`, `lint`, `build`, `seed` y `e2e`. |
| `docs/` | Instalación, API, base de datos, integración IoT, runbook y respaldos. |
| `PLAN-MEJORA.md` | Auditoría técnica y plan de mejora por fases. |

Flujo simplificado:

```text
Navegador  →  FastAPI (backend)  →  PostgreSQL
                    ↑
        Simulador / ESP32-S3 (API IoT)
```

### Tareas de desarrollo

```powershell
.\tasks.ps1 dev      # docker compose up -d --build
.\tasks.ps1 test     # PostgreSQL de test + pytest con cobertura
.\tasks.ps1 lint     # ruff, mypy, ESLint, Prettier y checks de CSS/HTML
.\tasks.ps1 build    # frontend/build con assets hasheados
.\tasks.ps1 seed     # datos demo (idempotente; -Reset para recrearlos)
.\tasks.ps1 seed -Reset -PrintKeys -Trucks 20 -Devices 10
.\tasks.ps1 e2e      # Playwright (requiere navegadores instalados)
.\tasks.ps1 backup   # respaldo pg_dump con retención
```

En macOS/Linux use el `Makefile` equivalente (`make test`, `make lint`, `make build`).

---

## Documentación

| Documento | Cuándo consultarlo |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Instalación detallada, variables, cambio y recuperación de contraseña. |
| [docs/API.md](docs/API.md) | Endpoints, ejemplos de peticiones y respuestas. |
| [docs/DATABASE.md](docs/DATABASE.md) | Tablas, relaciones y columnas. |
| [docs/IOT-INTEGRATION.md](docs/IOT-INTEGRATION.md) | Integración de firmware ESP32-S3. |
| [docs/ops/BACKUP-RESTORE.md](docs/ops/BACKUP-RESTORE.md) | Respaldo, restauración probada, RPO y RTO. |
| [docs/ops/RUNBOOK.md](docs/ops/RUNBOOK.md) | Arranque, incidentes, rotación de secretos y retención. |
| [docs/ops/perf-baseline.md](docs/ops/perf-baseline.md) | EXPLAIN, índices y tiempos del dashboard (Fase 3). |
| [docs/ops/load-test.md](docs/ops/load-test.md) | Prueba de carga IoT y criterios p95 (Fase 4). |
| [docs/api/openapi.json](docs/api/openapi.json) | Contrato OpenAPI versionado; CI detecta cambios. |
| [PLAN-MEJORA.md](PLAN-MEJORA.md) | Estado de la remediación técnica y tareas pendientes. |

---

## Seguridad

- El arranque falla si faltan `SECRET_KEY`, `DEVICE_KEY_PEPPER`, `ADMIN_PASSWORD` o `POSTGRES_PASSWORD`.
- Las contraseñas se guardan con Argon2 y las claves de dispositivo se almacenan hasheadas (HMAC-SHA256 en claves nuevas y Argon2 en las legacy).
- El login tiene rate limit por IP e identificador, bloqueo progresivo y mensajes genéricos.
- La ingesta IoT tiene rate limit por dispositivo e IP, ingesta atómica e idempotencia por `(device_id, timestamp)`.
- Los JWT viajan en cookies `HttpOnly` (60 min) y se renuevan con `POST /auth/refresh`; las mutaciones por cookie exigen `X-CSRF-Token` (doble cookie `frostbase_csrf`).
- El backend envía cabeceras de seguridad (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`) y **CSP activa** (`default-src 'self'`, sin CDN ni scripts inline).
- Los assets (Leaflet, Font Awesome y Outfit) se sirven localmente desde `frontend/assets`; el panel funciona sin Internet salvo los tiles del mapa y las APIs externas.
- Cambiar la contraseña incrementa `token_version` y revoca los JWT anteriores.
- Nunca subas `.env`, respaldos ni claves reales al repositorio.
- Para exponer la aplicación fuera de `localhost`, usa HTTPS y un proxy inverso; revisa la sección de producción en [docs/INSTALLATION.md](docs/INSTALLATION.md).

---

## Contribuir y plan de mejora

Antes de modificar código, lee **[PLAN-MEJORA.md](PLAN-MEJORA.md)**. Allí están las fases, dependencias, criterios de aceptación y el registro de progreso.

- Trabaja sobre la rama de la fase correspondiente (`feat/f1-secure-config`, `feat/f2-auth-iot-integrity`, etc.).
- No adelantes tareas de fases posteriores.
- Actualiza el registro §9 del plan al terminar una tarea.

> ✅ **Tareas de la Fase 1 completadas:** configuración segura y fail-fast, `.env` regenerado, Alembic gobernando el esquema, política de contraseña con revocación de JWT e higiene de respaldos.
>
> ✅ **Tareas de la Fase 2 completadas:** rate limiting, login en tiempo constante con lockout, claves de dispositivo HMAC, ingesta IoT atómica e idempotente y arnés de pruebas con PostgreSQL real.
>
> ✅ **Tareas de la Fase 3 completadas:** índices y caché del dashboard, watcher SQL fuera del proceso web, I/O externo asíncrono con circuit breaker, paginación keyset, placa reutilizable tras borrado lógico, UnitOfWork transaccional, contenedor no-root, `/health/ready`, logging JSON, CSRF/refresh, limpieza de configuración y CI con ruff/mypy/cobertura.
>
> ✅ **Tareas de la Fase 4 completadas:** assets locales con CSP activa, cliente HTTP con timeout/backoff, paginación server-side, estados de carga/error homogéneos, CSS consolidado, accesibilidad con axe sin violaciones graves, build hasheado con caché inmutable, retención de datos, runbook/OpenAPI, seed idempotente y E2E + load test.
>
> Queda pendiente la regresión manual §10, la validación de Lighthouse ≥ 90 y el p95 de 50 dispositivos en el runner Linux (Nightly). El estado de las fases restantes está en `PLAN-MEJORA.md` §9.
