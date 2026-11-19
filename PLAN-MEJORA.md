# PLAN-MEJORA.md · FrostBase

> **Documento maestro de remediación técnica.** Fuente única de verdad para el trabajo de mejora del repositorio.
> Generado a partir de la auditoría técnica del 2026-11-18 sobre el commit `4598891`.
> **Los agentes de IA de desarrollo deben leer este archivo completo antes de tocar código y trabajar únicamente sobre la etapa y tarea que se les asigne.**

| Metadato | Valor |
|---|---|
| Versión del plan | 1.0 |
| Fecha de auditoría | 2026-11-18 |
| Commit auditado | `4598891` (`fix: change default 8000 port to 8050`) |
| Alcance | `backend/` (sin `.venv`), `frontend/`, `iot-simulator/`, `docs/`, configuración raíz |
| Etapas | 3 (Inmediato · Corto plazo · Mediano plazo) |
| Fases de trabajo | 4 (F1 · F2 · F3 · F4) |
| Tareas totales | 39 |
| Esfuerzo estimado | 132–164 h |
| Estado global | 🟨 F1 tareas completadas · gate manual pendiente · F2–F4 pendientes |

---

## 0. Protocolo para agentes de IA de desarrollo

### 0.1 Cómo recibir y ejecutar una asignación

Una asignación válida tiene esta forma:

```
ETAPA: 1 (Inmediato)
FASE:  F1
TAREA: T1.1
```

o bien `FASE: F3, TAREAS: T3.2, T3.3` (varias tareas de la misma fase).

**Flujo obligatorio:**

1. **Leer** este documento completo (§1 contexto, §4 reglas transversales, la ficha de la tarea y sus dependencias en §0.3).
2. **Verificar dependencias:** si alguna tarea marcada como `Depende de` no está en estado ✅ en el registro (§9), **detenerse y reportar el bloqueo**. No improvisar la dependencia.
3. **Verificar el gate de la fase anterior** (§7). No se trabaja en F3 si F2 no cerró su gate.
4. **Crear la rama** de la fase si no existe (§4.1) y trabajar solo en ella.
5. **Leer los archivos reales** antes de editar. Los números de línea de este plan son del commit auditado y pueden haberse desplazado: localizar el código por su contenido, no por el número.
6. **Implementar exactamente el alcance de la ficha.** Nada de refactors oportunistas fuera de la lista de archivos.
7. **Escribir/actualizar los tests** que la ficha exige.
8. **Ejecutar la verificación** de la ficha + el checklist de regresión (§10) si la tarea toca flujo de usuario.
9. **Actualizar el registro de progreso (§9)**: estado, commit, fecha, notas. Es la única fuente de verdad del estado.
10. **Reportar** con el formato de §0.4.

### 0.2 Reglas duras (no negociables)

- ❌ **No** modificar `backend/.venv/`, `node_modules/`, `db-backups/` ni archivos ignorados por git salvo que la tarea lo indique explícitamente (T1.3, T1.7).
- ❌ **No** escribir secretos reales en archivos versionados. Solo `.env.example` con marcadores.
- ❌ **No** ejecutar `DROP`, `TRUNCATE`, `DELETE` masivos ni `docker compose down -v` sin respaldo previo verificado y confirmación humana.
- ❌ **No** renombrar ni eliminar campos de respuestas JSON existentes. Los cambios de contrato son **aditivos** hasta la fase F4B.
- ❌ **No** saltarse un gate de fase ni marcar ✅ sin haber ejecutado la verificación.
- ❌ **No** introducir dependencias nuevas sin declararlas en la ficha y en `backend/requirements.txt` (o el gestor frontend que aplique).
- ❌ **No** dejar `commit()` dentro de repositorios después de T3.8.
- ✅ **Sí** crear migración Alembic reversible para todo cambio de esquema, con la numeración reservada en §4.2.
- ✅ **Sí** mantener el feature flag indicado cuando la ficha lo especifica, para poder volver al comportamiento anterior sin revertir código.
- ✅ **Sí** detenerse y preguntar si el código real contradice lo que describe la ficha.

### 0.3 Dependencias entre tareas (grafo)

```
T1.1 ──┬─> T1.2 ──> T1.3 ──> T1.4
       └─> T1.5 (mig 0002)
T1.4 ──> T2.3 (mig 0003) ──> T2.6
T2.1 ──> T2.2
T2.1 ──> T2.6
T2.4 ──> T2.5 (mig 0004) ──> T3.8
T2.7 ──> T3.1 ──> (todas las tareas de F3 y F4)
T3.3 (mig 0005) ──> T3.4 ──> T3.9
T3.10 ──> T4.1
T4.2 ──> T4.3
T4.5 ──> T4.6 ──> T4.8
```

### 0.4 Formato de reporte al terminar una tarea

```markdown
## Tarea T<id> — <título>
- Estado: ✅ completada | 🟨 parcial | ⛔ bloqueada
- Rama / commit: feat/f1-secure-config @ abc1234
- Archivos modificados: <lista>
- Migraciones: 000x_<nombre> (upgrade/downgrade probados: sí/no)
- Tests añadidos: <lista> · Resultado: pytest -q → N passed
- Verificación ejecutada: <comandos y salida resumida>
- Criterios de aceptación: 1 ✅ 2 ✅ 3 ✅
- Regresión manual (§10): ejecutada / no aplica
- Desviaciones respecto al plan: <ninguna | detalle y motivo>
- Riesgos pendientes / follow-ups: <detalle>
```

### 0.5 Definición de Hecho (DoD) por tarea

Código implementado **+** tests automatizados en verde **+** criterios de aceptación verificados con evidencia **+** documentación afectada actualizada **+** `ruff check` y `mypy` limpios (obligatorio desde T3.1) **+** registro §9 actualizado **+** reporte §0.4 emitido.

---

## 1. Contexto del repositorio

### 1.1 Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 (síncrono) · Pydantic v2 · Alembic · PyJWT · pwdlib[argon2] · httpx |
| Base de datos | PostgreSQL 16 (driver `psycopg` v3) |
| Frontend | HTML5 + CSS3 + JavaScript ES Modules (vanilla, sin build) · Leaflet 1.9.4 · FontAwesome 6.6.0 |
| IoT | `iot-simulator/simulator.py` (requests) emulando ESP32-S3 |
| Despliegue | Docker + docker compose · uvicorn · frontend servido por `StaticFiles` en `/` |

### 1.2 Flujo de datos

```
Navegador (HTML + ES Modules)
  js/core/api.js  --fetch credentials:same-origin-->  /api/v1/*
      FastAPI (app/main.py) → app/api/v1/router.py → endpoints/*.py (Pydantic)
        → services/*.py (reglas de negocio + commit)
        → repositories/*.py (SQLAlchemy 2.0)
        → PostgreSQL 16 (Alembic 0001_initial)

ESP32 / simulator.py  --X-Device-Key (+X-Device-Id en /config)-->  /api/v1/iot/*
      deps.authenticate_device_or_401 → device_service (verificación de clave)
        → reading_service.ingest_reading → alert_service.evaluate_reading

Tarea periódica: _disconnect_watcher (asyncio en main.py, cada DISCONNECT_CHECK_SECONDS)
Terceros en el request path: OSRM (services/routing.py) · Open-Meteo (services/weather_service.py)
```

### 1.3 Mapa de archivos clave

```
backend/app/
  main.py                     arranque, CORS, watcher, montaje del frontend
  core/{config,database,security}.py
  api/deps.py                 DbSession, CurrentAdmin, autenticación de dispositivos
  api/v1/endpoints/*.py       auth, dashboard, trucks, devices, routes, readings, alerts, settings, iot
  services/*.py               auth, device, reading, alert, dashboard, truck, route, settings, weather, routing, serializers, bootstrap
  repositories/*.py           admin, devices, readings, alerts, trucks, routes, settings
  models/*.py                 admin, device, reading, alert, truck, route, setting
  schemas/*.py                contratos Pydantic
backend/alembic/versions/0001_initial.py
backend/scripts/seed_demo.py
frontend/js/core/{api,auth,app,helpers,notifications,theme}.js
frontend/js/components/{map,sidebar}.js
frontend/js/pages/{login,dashboard,trucks,truck-detail,routes,route-detail,alerts,settings}.js
frontend/css/{variables,global,components,layout,bauhaus}.css + css/pages/*.css
```

### 1.4 Comandos de trabajo

**Windows PowerShell (entorno actual del repo):**

```powershell
# Levantar el stack
docker compose up -d --build
docker compose logs -f app

# Datos de demo (imprime claves de dispositivos una sola vez)
docker compose exec app python -m scripts.seed_demo

# Migraciones
docker compose exec app alembic current
docker compose exec app alembic upgrade head

# Simulador IoT
cd iot-simulator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # editar DEVICE_KEY
python simulator.py

# Tests / lint (disponibles desde T2.7 / T3.1)
cd backend
pytest -q
ruff check . ; ruff format --check .
mypy app
```

**Linux/macOS:**

```bash
docker compose up -d --build
docker compose exec app python -m scripts.seed_demo
cd iot-simulator && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env && python simulator.py
cd backend && pytest -q && ruff check . && mypy app
```

---

## 2. Resumen ejecutivo y puntuación

La arquitectura por capas (`endpoints → services → repositories → models`) es correcta y coherente, con Pydantic v2, SQLAlchemy 2.0 tipado, inyección de dependencias y **cero SQL concatenado** (no hay inyección SQL viable). El frontend usa ES Modules, una capa `api.js` centralizada y `escapeHtml()` aplicado con disciplina (no se halló XSS explotable en las plantillas).

El problema no es la estructura, sino la **postura de seguridad y el gobierno de calidad**: el stack arranca con `SECRET_KEY` y contraseña de administrador por defecto, no hay rate limiting en login ni en la ingesta IoT, `main.py` solo registra un error ante una clave insegura, no existe ni un test, ni CI, ni linter, ni lockfile; hay patrones N+1 y consultas sin índice en rutas que se ejecutan cada 10 s por pestaña; y existe deriva documental (el `.env` local pertenece a otro proyecto y `docs/security/evidence/` describe otra aplicación).

| Área | Nota (1-10) |
|---|:--:|
| Estructura | 7 |
| Backend | 6 |
| Frontend | 6 |
| Seguridad | 4 |
| Mantenibilidad | 4 |
| **Global** | **5.4** |

**Objetivo del plan:** llevar Seguridad y Mantenibilidad a ≥ 8 sin romper la funcionalidad actual, y dejar el sistema operable en producción con datos reales.

---

## 3. Índice de hallazgos

Severidad: 🔴 Crítico · 🟠 Alto · 🟡 Medio · 🟢 Bajo.
Las líneas corresponden al commit auditado `4598891`.

| ID | Sev. | Hallazgo | Evidencia principal | Tarea |
|---|:--:|---|---|---|
| C1 | 🔴 | `SECRET_KEY` y admin por defecto permiten takeover | `docker-compose.yml:27,31,33`; `core/config.py:24,32`; `main.py:41-42` | T1.1, T1.2, T1.5 |
| C2 | 🔴 | `.env` local de otro proyecto → defaults inseguros silenciosos | `.env` (raíz); `core/config.py:11` (`extra="ignore"`) | T1.3 |
| C3 | 🔴 | Login sin rate limiting + oráculo de tiempo | `endpoints/auth.py:12-31`; `auth_service.py:37-45` | T2.1, T2.2 |
| C4 | 🔴 | Argon2 por cada lectura IoT → DoS de CPU | `core/security.py:50-55`; `device_service.py:134-142`; `endpoints/iot.py:13-21` | T2.3, T2.6 |
| C5 | 🔴 | Ingesta no transaccional + `timestamp` sin límites | `reading_service.py:40-60`; `schemas/iot.py:9-15`; `repositories/readings.py:28-34` | T2.4, T2.5 |
| C6 | 🔴 | `AUTO_CREATE_TABLES=true` convive con Alembic | `services/bootstrap.py:12-16`; `core/config.py:22`; `Dockerfile:18` | T1.4 |
| A1 | 🟠 | Conteo de alertas carga todas las alertas activas | `truck_service.py:104-117`; `repositories/alerts.py:55-63` | T3.2 |
| A2 | 🟠 | Watcher N+1 y duplicado por worker | `alert_service.py:116-147`; `main.py:23-33,43` | T3.4 |
| A3 | 🟠 | Dashboard: 8 queries + `max(received_at)` sin índice + geometría completa | `dashboard_service.py:23-98`; `repositories/readings.py:37-38`; `serializers.py:77-82` | T3.3 |
| A4 | 🟠 | httpx síncrono 10–15 s dentro del request | `weather_service.py:84-103`; `routing.py:23-31` | T3.5 |
| A5 | 🟠 | CDNs sin SRI, sin CSP, handlers inline | `dashboard.html:8-12,19-26,150`; `sidebar.js:30-31`; `login.html:38-39` | T3.10, T4.1 |
| A6 | 🟠 | `fetch` sin timeout; polling se congela; 401 no redirige | `core/api.js:27-48`; `core/app.js:13-44`; `core/auth.js:16-29` | T4.2 |
| A7 | 🟠 | `page_size=100` fijo y búsqueda solo en cliente | `pages/routes.js:529,544,251`; `pages/trucks.js:280-290`; `pages/alerts.js:185` | T4.3 |
| A8 | 🟠 | Borrado lógico + `plate` único impide reutilizar placa | `models/truck.py:24,27-29`; `truck_service.py:120-123,188-198`; `0001_initial.py:75-76` | T3.7 |
| A9 | 🟠 | Contenedor root, sin healthcheck, 1 worker, migraciones en CMD | `Dockerfile:1-18`; `docker-compose.yml:18-42` | T3.9 |
| A10 | 🟠 | 0 tests, 0 CI, 0 linters, dependencias sin lock | repositorio completo | T2.7, T3.1 |
| M1 | 🟡 | Config documentada que el código no lee | `core/config.py:40,47-50`; `.env.example:26-28`; `INSTALLATION.md:47,51-52` | T1.2, T3.12 |
| M2 | 🟡 | Código muerto | `repositories/alerts.py:114-121`; `routes.py:79-85`; `devices.py:77-88`; `serializers.py:169-170`; `truck_service.py:201-209`; `schemas/common.py:15`; `endpoints/dashboard.py:8` | T3.12 |
| M3 | 🟡 | Docs desincronizadas + evidencia de otra app | `INSTALLATION.md:176` (`v3` vs `v4`); `docs/security/evidence/*/run.log`; `README.md:55-75` | T1.6, T4.10 |
| M4 | 🟡 | Capa CSS de override duplicada + doble tipografía | `css/bauhaus.css` (802 líneas); `css/variables.css:1`; `dashboard.html:10` | T4.5 |
| M5 | 🟡 | Accesibilidad y SEO incompletos | `dashboard.html:86`; `pages/trucks.js:47-57`; `pages/alerts.js:33-41` | T4.6 |
| M6 | 🟡 | Duplicación de utilidades frontend | `components/sidebar.js:87-91`; paginación en `trucks.js:59-85`, `alerts.js:112-139`, `truck-detail.js:327-350` | T4.4, T4.7 |
| M7 | 🟡 | Sin idempotencia ni retención de lecturas | `reading_service.py:22-60`; `models/reading.py:15-41` | T2.5, T4.9 |
| M8 | 🟡 | `/health` no verifica dependencias; sin observabilidad | `main.py:75-77` | T3.10 |
| M9 | 🟡 | `commit()` disperso y escritura en lecturas | `repositories/settings.py:10-17`; `device_service.py:117,129,148`; `truck_service.py:141,175,197` | T2.4, T3.8 |
| M10 | 🟡 | No existe cambio de contraseña de administrador | `endpoints/auth.py:1-49`; `INSTALLATION.md:165` | T1.5 |
| M11 | 🟡 | Cookies/CORS/CSRF/JWT sin endurecer ni revocar | `docker-compose.yml:33-34,40`; `main.py:64-70`; `endpoints/auth.py:22-30`; `core/security.py:39-43` | T1.5, T3.10, T3.11 |
| M12 | 🟡 | `OFFSET` sin tope; `ilike` sin escapar comodines | `endpoints/*.py` (`page ge=1`); `repositories/trucks.py:36-41`, `devices.py:43-45` | T3.6 |
| B1 | 🟢 | Líneas > 88 caracteres, sin formateador | `endpoints/devices.py:41,53,63`; `trucks.py:40,52,62`; `0001_initial.py:26,39,54-56` | T3.1 |
| B2 | 🟢 | `count()` con aritmética booleana | `repositories/admin.py:32-33` | T3.12 |
| B3 | 🟢 | `dependencies=[]` residual | `endpoints/dashboard.py:7-9` | T3.12 |
| B4 | 🟢 | `started_at` de desconexión usa el umbral | `alert_service.py:138` | T3.4 |
| B5 | 🟢 | `seed_demo` crea ruta nueva en cada ejecución | `scripts/seed_demo.py:69-88` | T4.11 |
| B6 | 🟢 | Dumps con hashes/PII sin cifrar en el árbol de trabajo | `db-backups/` | T1.7 |
| B7 | 🟢 | `@import` de fuente y CSS sin minificar | `css/variables.css:1`; `dashboard.html:13-18` | T4.5, T4.8 |
| B8 | 🟢 | Imágenes sin `width`/`height` (CLS) | `login.html:38-39`; `sidebar.js:30-31` | T4.6 |
| B9 | 🟢 | README sin arquitectura/tests/variables | `README.md` | T4.10 |
| B10 | 🟢 | Dependencias sin lock ni auditoría | `backend/requirements.txt:1-10` | T3.1 |

---

## 4. Reglas transversales

### 4.1 Ramas y commits

| Fase | Rama |
|---|---|
| F1 | `feat/f1-secure-config` |
| F2 | `feat/f2-auth-iot-integrity` |
| F3 | `feat/f3-perf-platform` |
| F4 | `feat/f4-frontend-dx` |

- Un commit por tarea: `tipo(ámbito): T<id> descripción corta`.
- Tipos: `fix`, `feat`, `perf`, `refactor`, `test`, `docs`, `build`, `chore`.
- Ejemplos: `fix(security): T1.1 fail-fast de secretos en Settings`, `perf(db): T3.3 índices y caché del resumen`.
- Prohibido `git push --force` sobre `main`/`master`. Merge de fase solo tras su gate.

### 4.2 Migraciones Alembic (numeración reservada)

| Revisión | Contenido | Tarea | `down_revision` |
|---|---|---|---|
| `0002_admin_auth_policy` | `admins.must_change_password`, `admins.token_version` | T1.5 | `0001_initial` |
| `0003_device_key_scheme` | `devices.key_scheme` (`argon2` \| `hmac`) | T2.3 | `0002_admin_auth_policy` |
| `0004_readings_idempotency` | dedupe + `uq_readings_device_timestamp` | T2.5 | `0003_device_key_scheme` |
| `0005_perf_indexes` | `ix_readings_received_at`, `ix_alerts_truck_status` | T3.3 | `0004_readings_idempotency` |
| `0006_trucks_plate_partial_unique` | `uq_trucks_plate_active` (parcial) | T3.7 | `0005_perf_indexes` |
| `0007_route_geometry_status` | `routes.geometry_status` (opcional, flag) | T3.5 | `0006_trucks_plate_partial_unique` |

Reglas: toda migración con `downgrade()` probado; los borrados de datos (0004) requieren respaldo previo verificado y modo `--dry-run` con conteo; nada de `op.execute` con SQL interpolado desde variables de usuario.

### 4.3 Feature flags

| Flag | Default | Tarea | Efecto al desactivar |
|---|---|---|---|
| `AUTO_CREATE_TABLES` | `false` | T1.4 | Vuelve a `create_all` (solo desarrollo/tests) |
| `RATE_LIMIT_BACKEND` | `memory` | T2.1 | `redis` en producción |
| `DEVICE_KEY_FAST_PATH` | `true` | T2.3 | Vuelve a Argon2 puro por lectura |
| `ENABLE_INPROCESS_WATCHER` | `false` | T3.4 | Watcher dentro del proceso web (desarrollo) |
| `ROUTE_GEOMETRY_ASYNC` | `false` | T3.5 | OSRM síncrono en el guardado de ruta |

### 4.4 Compatibilidad de contrato

- Solo campos **aditivos** en respuestas (`duplicate`, `reading_id`, `geometry_status`, `must_change_password`).
- Ningún campo existente se renombra/elimina antes de F4B.
- Códigos HTTP nuevos permitidos: `429` (rate limit), `403` (CSRF), `503` (ready/proveedor).
- Todo cambio de contrato se refleja en `docs/API.md` en el mismo commit.

### 4.5 Respaldo antes de cada fase

```powershell
# Fuera del repositorio y cifrado (ver T1.7)
docker compose exec -T db pg_dump -U frostbase -Fc frostbase > $env:USERPROFILE\backups\frostbase_pre_f<N>.dump
```

---

## 5. Fases y tareas

### FASE 1 · Cimientos seguros: configuración, secretos y arranque

**Etapa 1 (Inmediato) · Días 1–2 · 16–20 h · Cierra C1, C2, C6, M10, M3 (parcial), B6**

---

#### T1.1 · Validación fail-fast de `Settings`

| Campo | Valor |
|---|---|
| Cierra | C1 |
| Depende de | — |
| Bloquea a | T1.2, T1.5 |
| Archivos | `backend/app/core/config.py` |
| Estimación | 3 h |

**Pasos**
1. Eliminar los defaults de `secret_key` y `admin_password` (pasan a obligatorios).
2. Añadir `device_key_pepper: str` (secreto independiente para HMAC de dispositivos, T2.3), `rate_limit_backend: Literal["memory","redis"] = "memory"`, `redis_url: str = ""`.
3. `field_validator` de `secret_key` y `device_key_pepper`: longitud ≥ 64 y rechazo de prefijos `dev-only` / `cambia-`.
4. `field_validator` de `admin_password`: ≥ 12 caracteres y rechazo de `ChangeMe123!`.
5. `model_validator(mode="after")`: si `is_production` → exigir `cookie_secure=True`, `cookie_samesite in {"lax","strict"}`, `auto_create_tables=False`, `cors_origin_list` sin `*`.
6. **Conservar** el singleton `settings = get_settings()` (lo importan ~8 módulos). Documentar que los tests fijan el entorno antes del import (T2.7).

**Código de referencia**
```python
class Settings(BaseSettings):
    secret_key: str
    admin_password: str
    device_key_pepper: str
    auto_create_tables: bool = False
    cookie_secure: bool = True

    @field_validator("secret_key", "device_key_pepper")
    @classmethod
    def _strong_secret(cls, v: str) -> str:
        if len(v) < 64 or v.startswith(("dev-only", "cambia-")):
            raise ValueError("debe ser aleatoria y de al menos 64 caracteres")
        return v

    @model_validator(mode="after")
    def _production_coherence(self) -> "Settings":
        if self.is_production:
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE debe ser true en producción")
            if self.auto_create_tables:
                raise ValueError("AUTO_CREATE_TABLES debe ser false en producción")
            if "*" in self.cors_origin_list:
                raise ValueError("CORS_ORIGINS no admite '*' con credenciales")
        return self
```

**Aceptación**
- Sin `SECRET_KEY` el proceso termina con error legible y código ≠ 0.
- `ENVIRONMENT=production` + `COOKIE_SECURE=false` también falla.
- Con configuración válida el arranque es idéntico al actual.

**Verificación**
```powershell
docker compose run --rm app python -c "import app.main"   # con y sin variables
```

**Rollback:** revertir el commit; el `.env` nuevo (T1.3) sigue siendo válido.

---

#### T1.2 · Endurecer `compose.yml`

| Campo | Valor |
|---|---|
| Cierra | C1, M1 (parcial) |
| Depende de | T1.1 |
| Bloquea a | T1.3 |
| Archivos | `docker-compose.yml` → renombrar a `compose.yml`; `.env.example` |
| Estimación | 2 h |

**Pasos**
1. Variables obligatorias con `${VAR:?mensaje}`: `SECRET_KEY`, `DEVICE_KEY_PEPPER`, `ADMIN_PASSWORD`.
2. `COOKIE_SECURE` por defecto `true`; `ENVIRONMENT` por defecto `production`.
3. Eliminar `DEVICE_OFFLINE_SECONDS`, `WEATHER_CITY`, `WEATHER_LATITUDE`, `WEATHER_LONGITUDE` (config que el código no lee).
4. Añadir `RATE_LIMIT_BACKEND` y, si aplica, `REDIS_URL`.
5. `AUTO_CREATE_TABLES: "false"`.
6. `healthcheck` del servicio `app` contra `/health` (cambiar a `/health/ready` en T3.10).

```yaml
    environment:
      SECRET_KEY: ${SECRET_KEY:?Define SECRET_KEY (>=64 chars) en .env}
      DEVICE_KEY_PEPPER: ${DEVICE_KEY_PEPPER:?Define DEVICE_KEY_PEPPER en .env}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?Define ADMIN_PASSWORD en .env}
      COOKIE_SECURE: ${COOKIE_SECURE:-true}
      ENVIRONMENT: ${ENVIRONMENT:-production}
```

**Aceptación:** `docker compose config` falla si falta cualquiera de las tres variables obligatorias; con `.env` correcto el stack levanta igual que antes.
**Verificación:** `docker compose config` (probar borrando temporalmente una variable en un `.env` de prueba).
**Rollback:** restaurar el archivo; actualizar README/INSTALLATION en T1.6 por el renombrado.

---

#### T1.3 · Regenerar `.env` y `.env.example`

| Campo | Valor |
|---|---|
| Cierra | C2, M1 (parcial) |
| Depende de | T1.2 |
| Bloquea a | T1.4 |
| Archivos | `.env` (local, ignorado), `.env.example`, `backend/app/main.py` (log de configuración) |
| Estimación | 2 h |

**Pasos**
1. Respaldar el `.env` actual **fuera del repo**: contiene claves de otro proyecto (`FROSTBASE_SECRET`, `AUTO_SEED`, Postgres en 5433, CORS en 8000) que `Settings` ignora por `extra="ignore"`.
2. Generar dos secretos: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
3. `DATABASE_URL` coherente (`db:5432` en contenedor, `localhost:5432` en local); `CORS_ORIGINS` con los puertos reales 8050/8060/8070.
4. Depurar `.env.example`: solo claves que `Settings` lee, más las nuevas.
5. Log de arranque con la configuración efectiva **sin secretos** (`environment`, `cors`, `cookie_secure`, `auto_create_tables`, `rate_limit_backend`).
6. Crear `backend/scripts/reset_admin.py` (restablece la contraseña del admin desde variables de entorno, para recuperación documentada).

**Aceptación:** los logs muestran la configuración efectiva y ningún secreto; login operativo con la nueva `ADMIN_PASSWORD`; `reset_admin.py` probado.
**Rollback:** restaurar el `.env` respaldado (solo para desarrollo).

---

#### T1.4 · Esquema gobernado solo por Alembic + entrypoint con lock

| Campo | Valor |
|---|---|
| Cierra | C6 |
| Depende de | T1.3 |
| Bloquea a | T2.3, T3.9 |
| Archivos | `backend/app/services/bootstrap.py`, `backend/app/core/config.py`, `backend/scripts/migrate.py` (nuevo), `docker/entrypoint.sh` (nuevo), `Dockerfile` |
| Estimación | 4 h |

**Pasos**
1. `auto_create_tables` por defecto `False`; `ensure_schema()` restringido a tests y, si se activa, ejecuta `alembic stamp head` después de `create_all`.
2. `scripts/migrate.py`: `pg_advisory_lock` antes de `alembic upgrade head` (evita carreras con varios workers/réplicas).
3. `docker/entrypoint.sh`: `python -m scripts.migrate && exec uvicorn … --proxy-headers`.
4. Retirar `alembic upgrade head` del `CMD` del Dockerfile.

```python
# backend/scripts/migrate.py
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from app.core.database import engine

LOCK_KEY = 7712026

def main() -> None:
    cfg = Config("alembic.ini")
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_KEY})
        try:
            command.upgrade(cfg, "head")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
```

**Aceptación:** dos réplicas arrancando a la vez no producen errores de migración; una BD creada antes con `create_all` queda estampada; `alembic current == head`.
**Verificación:** `docker compose exec app alembic current`; arranque simultáneo de dos instancias.

---

#### T1.5 · Política de contraseña, cambio obligatorio y revocación de JWT

| Campo | Valor |
|---|---|
| Cierra | C1 (parcial), M10, M11 (parcial) |
| Depende de | T1.1 |
| Bloquea a | T3.11 |
| Archivos | `backend/app/models/admin.py`, `schemas/auth.py`, `services/auth_service.py`, `api/v1/endpoints/auth.py`, `api/deps.py`, `core/security.py`, `alembic/versions/0002_admin_auth_policy.py`, `frontend/settings.html`, `frontend/js/pages/settings.js`, `frontend/js/core/app.js` |
| Estimación | 4 h |
| Migración | `0002_admin_auth_policy` |

**Pasos**
1. Migración: `must_change_password BOOLEAN NOT NULL DEFAULT false`, `token_version INTEGER NOT NULL DEFAULT 1`; en `upgrade()` poner `must_change_password = true` a todos los admins existentes (rotación única forzada).
2. `PasswordChangeRequest`: ≥ 12 caracteres, distinta de la actual, sin contener el username.
3. `POST /auth/change-password`: verifica la actual, hashea la nueva, incrementa `token_version`, limpia `must_change_password`.
4. `create_access_token` añade el claim `tv`; `get_current_admin` rechaza si `payload["tv"] != admin.token_version` (revocación real).
5. `AdminOut` expone `must_change_password`; el frontend muestra un modal obligatorio mientras sea `true`.

**Aceptación:** tras login con la contraseña por defecto se fuerza el cambio; los JWT emitidos antes del cambio devuelven 401; el flujo del panel no se rompe para un admin ya rotado.
**Rollback:** `alembic downgrade -1` + revert (las sesiones activas se invalidan: es esperado y debe avisarse).

---

#### T1.6 · Corrección documental crítica

| Campo | Valor |
|---|---|
| Cierra | M3 (parcial) |
| Depende de | T1.2, T1.3, T1.5 |
| Archivos | `README.md`, `docs/INSTALLATION.md`, `docs/API.md`; eliminar `docs/security/evidence/**` |
| Estimación | 2 h |

**Pasos**
1. `INSTALLATION.md:176`: `frostbase_v3_pgdata` → `frostbase_v4_pgdata`.
2. Sincronizar la tabla de variables con `Settings` real (quitar `DEVICE_OFFLINE_SECONDS` y `WEATHER_*`).
3. Añadir comandos PowerShell junto a los de bash; documentar el renombrado a `compose.yml`.
4. Eliminar `docs/security/evidence/` (describe otra aplicación: MongoDB, `/api/users`, `/api/orders`, `backend/app/routers/routes.py`).
5. Añadir secciones "Secretos obligatorios", "Cambio de contraseña inicial" y "Recuperación de acceso".
6. Enlazar este `PLAN-MEJORA.md` y `docs/` desde el README.

**Aceptación:** un tercero levanta el stack siguiendo solo el README, sin credenciales por defecto y sin preguntas.

---

#### T1.7 · Higiene de datos locales y respaldos

| Campo | Valor |
|---|---|
| Cierra | B6 |
| Depende de | — |
| Archivos | `.gitignore`, `docs/ops/BACKUP-RESTORE.md` (nuevo); mover `db-backups/` fuera del repo |
| Estimación | 1 h |

**Pasos**
1. Mover `db-backups/` a una ruta externa (p. ej. `%USERPROFILE%\backups\frostbase`) y cifrar (`age`/GPG).
2. Añadir `*.dump`, `*.tar.gz`, `*.sql` al `.gitignore`.
3. Documentar respaldo, restauración **probada y cronometrada**, RPO y RTO.

**Aceptación:** `git status --ignored` no muestra dumps dentro del repo; existe un restore verificado con tiempo medido.

---

### FASE 2 · Identidad, control de abuso e integridad de la ingesta IoT

**Etapa 1 (Inmediato) · Días 3–6 · 26–32 h · Cierra C3, C4, C5, M7 (parcial), M9 (parcial)**

---

#### T2.1 · Infraestructura de rate limiting

| Campo | Valor |
|---|---|
| Cierra | C3 (parcial), C4 (parcial) |
| Depende de | T1.1 |
| Bloquea a | T2.2, T2.6 |
| Archivos | `backend/app/core/ratelimit.py` (nuevo), `backend/requirements.txt`, `backend/app/core/config.py` |
| Estimación | 4 h |

**Pasos**
1. Sliding window con backend intercambiable: `memory` (por proceso) y `redis` (`REDIS_URL`).
2. Dependencia `RateLimit(scope, limit, window_seconds, key_fn)` → **429** con `Retry-After`.
3. Límites iniciales: login 5/min por IP y 10/15 min por identificador; IoT 30/min por `device_id` y 120/min por IP; `rotate-key` 10/h por admin.
4. Documentar que con `--workers > 1` el backend `memory` es parcial → Redis o `limit_req` del proxy (T3.9).

**Aceptación:** 20 logins fallidos en 60 s → los últimos devuelven 429 con `Retry-After`; el simulador (1 lectura/10 s) nunca es limitado.
**Verificación:** `backend/scripts/loadcheck.py` (nuevo) que lanza N peticiones y reporta la distribución de códigos.

---

#### T2.2 · Login en tiempo constante, lockout y auditoría

| Campo | Valor |
|---|---|
| Cierra | C3 |
| Depende de | T2.1 |
| Archivos | `backend/app/services/auth_service.py`, `backend/app/api/v1/endpoints/auth.py` |
| Estimación | 3 h |

**Pasos**
1. Hash *dummy* calculado una vez al importar el módulo; verificación siempre ejecutada.
2. Registro estructurado de intentos fallidos (IP, identificador, resultado) **sin contraseñas**.
3. Lockout progresivo por identificador apoyado en T2.1.
4. Mensaje genérico idéntico en ambos casos + `WWW-Authenticate`.

```python
_DUMMY_HASH = hash_password(secrets.token_urlsafe(24))

def authenticate(db, identifier, password):
    admin = admin_repo.get_by_identifier(db, identifier)
    ok = verify_password(password, admin.password_hash if admin else _DUMMY_HASH)
    if admin is None or not ok:
        logger.warning("login_failed identifier=%s", identifier)
        raise AuthenticationError("Usuario o contraseña incorrectos")
```

**Aceptación:** la latencia media de "usuario inexistente" vs "contraseña incorrecta" difiere < 15 % (50 muestras por caso).

---

#### T2.3 · Claves de dispositivo: HMAC + fast-path sin romper el parque existente

| Campo | Valor |
|---|---|
| Cierra | C4 |
| Depende de | T1.4 |
| Bloquea a | T2.6 |
| Archivos | `backend/app/core/security.py`, `services/device_service.py`, `models/device.py`, `alembic/versions/0003_device_key_scheme.py`, `backend/scripts/rotate_all_device_keys.py` (nuevo) |
| Estimación | 6 h |
| Migración | `0003_device_key_scheme` |
| Flag | `DEVICE_KEY_FAST_PATH` |

**Pasos**
1. Migración: `devices.key_scheme VARCHAR(16) NOT NULL DEFAULT 'argon2'`.
2. `device_fingerprint(secret) = HMAC-SHA256(device_key_pepper, secret)`; comparar con `hmac.compare_digest`.
3. Dispositivos **nuevos** y **rotaciones** → `key_scheme='hmac'` (verificación O(1), sin KDF).
4. Dispositivos **existentes** (`argon2`) → Argon2 solo la primera vez; cachear el acierto en `TTLCache` (clave = fingerprint del secreto presentado, valor = `device.id`, TTL 300 s, máx. 4096). **Nunca cachear fallos.**
5. Rate limit por `device_id` **antes** de cualquier hash (T2.6).
6. Script opcional `rotate_all_device_keys.py` para migrar todo el parque a `hmac` (imprime el mapa una sola vez).

**Aceptación:** el simulador con su clave actual sigue funcionando sin cambios; una lectura repetida no ejecuta Argon2 (verificable con contador); `rotate-key` autentica en < 1 ms de CPU.
**Nota crítica:** rotar `DEVICE_KEY_PEPPER` invalida las claves `hmac` → procedimiento documentado (rotar claves de dispositivos en la misma ventana).
**Rollback:** `DEVICE_KEY_FAST_PATH=false` vuelve a Argon2 puro.

---

#### T2.4 · Ingesta IoT atómica

| Campo | Valor |
|---|---|
| Cierra | C5 (parcial), M9 (parcial) |
| Depende de | T2.3 |
| Bloquea a | T2.5, T3.8 |
| Archivos | `backend/app/api/deps.py`, `api/v1/endpoints/iot.py`, `services/reading_service.py`, `services/alert_service.py`, `repositories/settings.py` |
| Estimación | 5 h |

**Pasos**
1. Nueva dependencia **acotada a `/iot/*`**: `TransactionalSession` (una transacción por petición).
2. Quitar `db.commit()` de `reading_service.ingest_reading` y de `alert_service.evaluate_reading` → `db.flush()`.
3. `settings_repo.get_or_create` deja de insertar en lecturas: `SELECT` y, si no existe, objeto en memoria con defaults (la fila se crea solo en bootstrap).
4. Capturar `IntegrityError` del índice único parcial de alertas y reintentar la evaluación una vez.
5. El resto de servicios conserva sus commits hasta T3.8.

```python
# deps.py
def get_tx_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        with db.begin():
            yield db

TxSession = Annotated[Session, Depends(get_tx_db)]
```

**Aceptación:** si la evaluación de alertas falla, **no queda ninguna lectura persistida** (test que fuerza el fallo); desaparecen los 500 con filas huérfanas.

---

#### T2.5 · Ventana de `timestamp` e idempotencia de lecturas

| Campo | Valor |
|---|---|
| Cierra | C5, M7 (parcial) |
| Depende de | T2.4 |
| Bloquea a | T3.8 |
| Archivos | `backend/app/schemas/iot.py`, `services/reading_service.py`, `services/alert_service.py`, `alembic/versions/0004_readings_idempotency.py`, `docs/API.md`, `docs/IOT-INTEGRATION.md` |
| Estimación | 5 h |
| Migración | `0004_readings_idempotency` |

**Pasos**
1. Validador de `timestamp`: naive → UTC; rechazar `> now + 5 min` o `< now − 7 días` (422 con mensaje claro).
2. Migración en dos pasos: (a) deduplicar históricos conservando `MIN(id)` por `(device_id, reading_timestamp)`; (b) `CREATE UNIQUE INDEX uq_readings_device_timestamp`.
3. Inserción con `postgresql.insert(...).on_conflict_do_nothing(...).returning(Reading.id)`; si no hay fila, recuperar la existente.
4. Respuesta aditiva: `duplicate: bool = False`, `reading_id: int | None`.
5. `alert_service` acota `started_at` para que nunca quede en el futuro.

**Aceptación:** reenviar el mismo payload 5 veces deja **una** fila y devuelve `duplicate: true` en las 4 siguientes; `timestamp` del año 2099 → 422.
**Riesgo:** el dedupe borra filas → respaldo obligatorio (T1.7) + `--dry-run` con conteo previo; `downgrade()` solo elimina el índice.

---

#### T2.6 · Rate limit y semántica HTTP en `/iot/*`

| Campo | Valor |
|---|---|
| Cierra | C4 (parcial) |
| Depende de | T2.1, T2.3 |
| Archivos | `backend/app/api/v1/endpoints/iot.py`, `docs/API.md` |
| Estimación | 2 h |

**Pasos:** aplicar `RateLimit` a `POST /iot/readings` y `GET /iot/config`; 401 clave inválida · 429 abuso · 409 dispositivo sin camión · 422 payload inválido; añadir cabeceras `X-RateLimit-*` para que el firmware haga backoff.

**Aceptación:** 200 peticiones con `device_id` válido y clave incorrecta reciben 429 en < 1 s y no consumen más del 20 % de un core.

---

#### T2.7 · Arnés de pruebas mínimo

| Campo | Valor |
|---|---|
| Cierra | A10 (parcial) |
| Depende de | T2.5 |
| Bloquea a | T3.1 y todas las fases siguientes |
| Archivos | `backend/pyproject.toml` (nuevo, sección pytest), `backend/tests/conftest.py`, `backend/tests/integration/test_auth.py`, `test_iot_ingest.py`, `compose.test.yml` (nuevo) |
| Estimación | 4 h |

**Pasos**
1. Postgres 16 real (índices parciales y `ON CONFLICT` no existen en SQLite).
2. `conftest` fija `SECRET_KEY`, `ADMIN_PASSWORD`, `DEVICE_KEY_PEPPER` de test **antes** de importar `app`.
3. Fixtures de sesión con rollback por test; fábricas de camión/dispositivo/ruta.

**Tests mínimos:** login ok/ko · rate limit 429 · smoke de tiempo constante · ingesta crea lectura+alerta · reingesta idempotente · timestamp fuera de ventana 422 · fallo de alertas no persiste lectura · clave rotada autentica · clave antigua deja de autenticar.

**Aceptación:** `pytest -q` en verde contra la BD de test en < 60 s.

---

#### T2.8 · Documentación de contratos IoT

| Campo | Valor |
|---|---|
| Cierra | soporte de C4/C5 |
| Depende de | T2.5, T2.6 |
| Archivos | `docs/API.md`, `docs/IOT-INTEGRATION.md` |
| Estimación | 1 h |

**Pasos:** documentar ventana de `timestamp`, `duplicate`, `reading_id`, 429, cabeceras de rate limit, backoff recomendado del firmware, rotación de claves y `DEVICE_KEY_PEPPER`.

---

### FASE 3 · Rendimiento, resiliencia y plataforma

**Etapa 2 (Corto plazo) · Semanas 2–3 · 44–54 h · Cierra A1, A2, A3, A4, A8, A9, A10, M1, M2, M8, M9, M11, M12, B1–B4, B10**

---

#### T3.1 · Plataforma de calidad: lint, tipos, lock y CI

| Campo | Valor |
|---|---|
| Cierra | A10, B1, B10 |
| Depende de | T2.7 |
| Bloquea a | todas las tareas restantes |
| Archivos | `backend/pyproject.toml`, `backend/requirements.lock` (nuevo), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `frontend/.eslintrc.json`, `frontend/.prettierrc` |
| Estimación | 6 h |

**Pasos**
1. `ruff` (line-length 88; reglas E/F/I/UP/B) + `ruff format`.
2. `mypy` con `strict` activado por módulo de forma gradual.
3. `pip-compile --generate-hashes` → `requirements.lock`; el Dockerfile instala desde el lock.
4. CI con servicio `postgres:16`: `ruff check` → `mypy app` → `pytest --cov=app --cov-fail-under=70` → `docker build`.
5. `pip-audit` semanal; ESLint/Prettier para `frontend/js`.

**Aceptación:** un PR con código sin formatear o sin tipos falla el CI; el build es reproducible con el lock.

---

#### T3.2 · Conteo de alertas por camión en SQL

| Campo | Valor |
|---|---|
| Cierra | A1 |
| Depende de | T3.1 |
| Archivos | `backend/app/repositories/alerts.py`, `services/truck_service.py` (`get_truck_detail`) |
| Estimación | 2 h |

**Pasos:** añadir `count_active_by_truck(db, truck_id) -> int` (`SELECT count(*) WHERE status='activa' AND truck_id=:id`); sustituir la list comprehension que carga todas las alertas; quitar `selectinload` innecesario en `find_active` cuando solo se necesita el estado.

**Aceptación:** `GET /trucks/{id}` pasa de 3+ queries con N filas a 1 query agregada (verificado con contador de queries en test).

---

#### T3.3 · Índices, caché de resumen y geometría ligera

| Campo | Valor |
|---|---|
| Cierra | A3 |
| Depende de | T3.1 |
| Bloquea a | T3.4 |
| Archivos | `alembic/versions/0005_perf_indexes.py`, `services/dashboard_service.py`, `services/serializers.py`, `app/utils/geo.py` (nuevo), `app/core/cache.py` (nuevo), `docs/ops/perf-baseline.md` (nuevo) |
| Estimación | 8 h |
| Migración | `0005_perf_indexes` |

**Pasos**
1. Índices `ix_readings_received_at (received_at DESC)` y `ix_alerts_truck_status (truck_id, status)`.
2. Caché TTL 10 s para `get_summary`, invalidada al actualizar `/settings`; reutilizar la abstracción memory/redis de T2.1.
3. `simplify_polyline(points, tolerance=0.0001, max_points=400)` (Ramer–Douglas–Peucker) en `serialize_route_brief_geometry`; la geometría completa se mantiene en `GET /routes/{id}` y `/iot/config`.
4. Unificar `effectiveness_since` en una query con `count(*) FILTER (WHERE …)`.

**Aceptación:** con 100.000 lecturas sembradas, `/dashboard/summary` < 80 ms en frío y < 10 ms en caliente; payload de `/dashboard/trucks` −70 %; el mapa se dibuja igual a simple vista.
**Verificación:** `EXPLAIN (ANALYZE, BUFFERS)` antes/después archivado en `docs/ops/perf-baseline.md`.

---

#### T3.4 · Watcher de desconexiones en SQL y fuera del proceso web

| Campo | Valor |
|---|---|
| Cierra | A2, B4 |
| Depende de | T3.3 |
| Bloquea a | T3.9 |
| Archivos | `services/alert_service.py`, `app/main.py`, `backend/scripts/disconnect_watcher.py` (nuevo), `compose.yml` |
| Estimación | 6 h |
| Flag | `ENABLE_INPROCESS_WATCHER` |

**Pasos**
1. Reescribir con dos sentencias set-based (inserción `ON CONFLICT … DO NOTHING` + resolución `UPDATE … FROM devices`), eliminando el N+1.
2. `started_at = device.last_seen` (no el umbral).
3. Servicio `watcher` en compose con *advisory lock* para que solo una instancia trabaje.
4. Retirar la tarea del `lifespan` detrás del flag (`false` en producción, `true` solo en desarrollo sin compose).

```sql
INSERT INTO alerts (truck_id, device_id, alert_type, message, started_at, status)
SELECT d.truck_id, d.id, 'desconexion',
       'El dispositivo dejó de enviar lecturas dentro del tiempo esperado.',
       d.last_seen, 'activa'
FROM devices d
WHERE d.last_seen IS NOT NULL AND d.last_seen < :threshold
ON CONFLICT (device_id, alert_type) WHERE status = 'activa' DO NOTHING;

UPDATE alerts a SET status = 'resuelta', resolved_at = now()
FROM devices d
WHERE a.device_id = d.id AND a.alert_type = 'desconexion' AND a.status = 'activa'
  AND d.last_seen >= :threshold;
```

**Aceptación:** con 500 dispositivos el ciclo ejecuta ≤ 3 queries en < 50 ms; dos watchers simultáneos no duplican ni fallan; parar el simulador 90 s crea la alerta y reanudarlo la resuelve.

---

#### T3.5 · I/O externo no bloqueante y circuit breaker

| Campo | Valor |
|---|---|
| Cierra | A4 |
| Depende de | T3.1 |
| Archivos | `services/weather_service.py`, `services/routing.py`, `api/v1/endpoints/dashboard.py`, `api/v1/endpoints/routes.py`, `app/core/http.py` (nuevo), `models/route.py`, `alembic/versions/0007_route_geometry_status.py` (opcional) |
| Estimación | 6 h |
| Flag | `ROUTE_GEOMETRY_ASYNC` |

**Pasos**
1. `httpx.AsyncClient` compartido con pooling; timeouts 3 s (clima) / 5 s (OSRM).
2. `async def weather(...)`: la lectura de `settings` va con `run_in_threadpool` (SQLAlchemy es síncrono; no bloquear el event loop).
3. Circuit breaker: N fallos consecutivos → abrir 60 s → devolver `stale`/`warning` sin llamar al proveedor.
4. **Iteración 2 (flag + mig 0007):** `routes.geometry_status` (`pending|ready|failed`); `POST /routes` guarda sin geometría y encola el cálculo; el frontend hace poll del estado.

**Aceptación:** con Open-Meteo simulado lento (10 s), 50 peticiones concurrentes a `/dashboard/weather` no degradan `/auth/login` ni `/iot/readings` (p95 < 300 ms); con el flag activo, guardar ruta tarda < 200 ms.

---

#### T3.6 · Paginación, topes y búsqueda segura

| Campo | Valor |
|---|---|
| Cierra | M12 |
| Depende de | T3.1 |
| Archivos | `api/v1/endpoints/{readings,alerts,trucks,devices,routes}.py`, `repositories/{trucks,devices,routes}.py`, `docs/API.md` |
| Estimación | 4 h |

**Pasos:** `page` con `le=10000`; keyset pagination aditiva (`cursor`) en `/readings` y `/alerts`; escapar `%` y `_` en los `ilike`; documentar el orden estable.

**Aceptación:** `?page=99999999` → 422; una búsqueda con `%` literal no provoca full scan (`EXPLAIN`).

---

#### T3.7 · Unicidad de placa compatible con borrado lógico

| Campo | Valor |
|---|---|
| Cierra | A8 |
| Depende de | T3.3 |
| Archivos | `alembic/versions/0006_trucks_plate_partial_unique.py`, `models/truck.py`, `repositories/trucks.py`, `services/truck_service.py`, `frontend/js/pages/routes.js`, `frontend/js/pages/trucks.js` |
| Estimación | 4 h |
| Migración | `0006_trucks_plate_partial_unique` |

**Pasos:** eliminar el índice único `ix_trucks_plate` y crear `uq_trucks_plate_active ON trucks (plate) WHERE is_deleted = false`; `get_by_plate` filtra `is_deleted`; permitir reutilizar la placa de un camión borrado; confirmación explícita en la UI cuando asignar una ruta desasigna otro camión.

**Aceptación:** borrar `ABC-123-A` y volver a registrarlo funciona; el histórico de lecturas del camión borrado se conserva intacto.

---

#### T3.8 · UnitOfWork global

| Campo | Valor |
|---|---|
| Cierra | M9 |
| Depende de | T2.4, T2.5, T3.1 |
| Archivos | `api/deps.py`, todos los `services/*.py` y `repositories/*.py` |
| Estimación | 5 h |

**Pasos:** extender el patrón de T2.4 a todos los endpoints; los repositorios solo hacen `flush()`; los servicios dejan de hacer `commit()`; `get_db` pasa a ser transaccional; eliminar `db.refresh()` redundantes (`expire_on_commit=False` ya está configurado).

**Aceptación:** ningún repositorio contiene `commit()` (verificado por grep en CI); crear camión + asignar ruta + vincular dispositivo es atómico ante fallo intermedio.

---

#### T3.9 · Contenedor y orquestación productivos

| Campo | Valor |
|---|---|
| Cierra | A9 |
| Depende de | T1.4, T3.4 |
| Archivos | `Dockerfile` → `docker/Dockerfile`, `docker/entrypoint.sh`, `compose.yml`, `deploy/nginx.conf` (nuevo) |
| Estimación | 5 h |

**Pasos**
1. Multi-stage con `USER app`, base pinneada por versión/digest, `HEALTHCHECK`, `--workers ${WEB_CONCURRENCY:-2}`, `--proxy-headers`.
2. `compose.yml`: servicio `watcher`, `redis` opcional, límites de CPU/memoria, red interna sin publicar Postgres.
3. `deploy/nginx.conf`: TLS, `limit_req` como segunda capa de rate limit, `gzip`/`brotli` para estáticos.

```dockerfile
FROM python:3.12.8-slim AS runtime
RUN addgroup --system app && adduser --system --ingroup app app
COPY --chown=app:app backend/ /app/backend/
USER app
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8050/health/ready').status==200 else 1)"
CMD ["sh","-c","exec uvicorn app.main:app --host 0.0.0.0 --port 8050 --workers ${WEB_CONCURRENCY:-2} --proxy-headers"]
```

**Aceptación:** `docker compose ps` muestra `healthy`; `docker compose exec app id` no es root; reiniciar una réplica no interrumpe el servicio.

---

#### T3.10 · Salud, observabilidad y cabeceras de seguridad

| Campo | Valor |
|---|---|
| Cierra | M8, M11 (parcial), A5 (parcial) |
| Depende de | T3.1 |
| Bloquea a | T4.1 |
| Archivos | `app/main.py`, `app/core/logging.py` (nuevo), `compose.yml` (healthcheck) |
| Estimación | 4 h |

**Pasos**
1. `/health/live` (proceso) y `/health/ready` (`SELECT 1` + `alembic current == head`).
2. Logging JSON con `request_id`, duración y `admin_id`/`device_id`; contadores de ingesta/alertas/errores (`/metrics` opcional).
3. Middleware de cabeceras: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`; `TrustedHostMiddleware`.
4. **CSP en `Report-Only`** (se activa en T4.1, cuando ya no haya inline).

**Aceptación:** con Postgres caído `/health/ready` devuelve 503; cada petición tiene `request_id` correlacionable.

---

#### T3.11 · CSRF y ciclo de vida de la sesión

| Campo | Valor |
|---|---|
| Cierra | M11 |
| Depende de | T1.5, T3.10 |
| Archivos | `app/main.py` o middleware nuevo, `api/v1/endpoints/auth.py`, `core/security.py`, `frontend/js/core/api.js` |
| Estimación | 3 h |

**Pasos:** doble cookie CSRF (`frostbase_csrf` legible + cabecera `X-CSRF-Token`) para POST/PUT/DELETE autenticados por cookie; exención explícita de `/iot/*`; `ACCESS_TOKEN_EXPIRE_MINUTES=60` con `/auth/refresh` silencioso; `token_version` como revocación.

**Aceptación:** un POST cross-site sin cabecera CSRF → 403; el frontend renueva la sesión sin perder el estado del panel.

---

#### T3.12 · Limpieza de configuración y código muerto

| Campo | Valor |
|---|---|
| Cierra | M1, M2, B2, B3 |
| Depende de | T3.1 |
| Archivos | `core/config.py`, `.env.example`, `compose.yml`, `docs/INSTALLATION.md`, `repositories/{alerts,routes,devices,admin}.py`, `services/{serializers,truck_service}.py`, `schemas/common.py`, `api/v1/endpoints/dashboard.py` |
| Estimación | 2 h |

**Pasos:** eliminar `device_offline_seconds` y `weather_city/latitude/longitude` de `Settings` y de toda la documentación; borrar `trucks_without_contact`, `unassign_truck`, `truck_exists`, `freshness_threshold`, `assign_route_to_truck`, `MessageOut`, `dependencies=[]`; reescribir `admin_repo.count` con `func.count`.

**Aceptación:** `ruff` limpio + test de "config declarada == config usada"; grep de símbolos muertos vacío.

---

### FASE 4 · Frontend endurecido y sostenibilidad

**Etapa 2 (bloque 4A) + Etapa 3 (bloque 4B) · Semanas 4–6 · 46–58 h**

#### Bloque 4A — Corto plazo 🟠

---

#### T4.1 · Entrega segura de assets: vendors, SRI y CSP activa

| Campo | Valor |
|---|---|
| Cierra | A5 |
| Depende de | T3.10 |
| Archivos | `frontend/assets/vendors/**` (nuevo), los 9 HTML, `frontend/js/components/sidebar.js`, `frontend/js/core/theme-boot.js` (nuevo), `backend/app/main.py` |
| Estimación | 6 h |

**Pasos**
1. Vendorizar Leaflet 1.9.4, un subconjunto de FontAwesome (solo los iconos usados) y la fuente Outfit.
2. Eliminar los `<script>` inline de tema y los `onerror` inline (sustituir por listeners).
3. Si se conserva algún CDN, añadir `integrity` + `crossorigin="anonymous"`.
4. Pasar la CSP de `Report-Only` a **enforced**.

```
default-src 'self';
img-src 'self' data: https://*.tile.openstreetmap.org;
style-src 'self';
script-src 'self';
font-src 'self';
connect-src 'self';
frame-ancestors 'none';
base-uri 'none'
```

**Aceptación:** cero violaciones CSP en las 8 páginas; el panel funciona sin Internet salvo tiles y APIs externas; Lighthouse Best Practices ≥ 95.

---

#### T4.2 · Cliente HTTP resiliente

| Campo | Valor |
|---|---|
| Cierra | A6 |
| Depende de | T3.11 |
| Bloquea a | T4.3 |
| Archivos | `frontend/js/core/api.js`, `frontend/js/core/app.js`, `frontend/js/core/auth.js` |
| Estimación | 5 h |

**Pasos**
1. `AbortController` con timeout de 15 s y mensaje propio para `AbortError`.
2. Redirección a login en 401 desde cualquier llamada (no solo al inicio).
3. Backoff exponencial con techo de 60 s en `setupPolling` + badge "Reconectando…".
4. Cancelar peticiones en vuelo al ocultar la pestaña; `Promise.allSettled` donde un fallo tumba el grupo.

```js
const controller = new AbortController();
const t = setTimeout(() => controller.abort(), 15000);
try {
  response = await fetch(url, { ...options, signal: controller.signal });
} finally {
  clearTimeout(t);
}
```

**Aceptación:** con el backend detenido el panel muestra "Sin conexión", conserva los últimos datos y se recupera solo; al expirar el JWT redirige a login con `?next=`; ninguna petición queda colgada > 15 s.

---

#### T4.3 · Paginación y búsqueda server-side en el frontend

| Campo | Valor |
|---|---|
| Cierra | A7 |
| Depende de | T4.2, T3.6 |
| Archivos | `frontend/js/pages/routes.js`, `pages/trucks.js`, `pages/alerts.js`, `backend/app/api/v1/endpoints/{routes,trucks}.py` (nuevos `/options`), `frontend/js/components/pagination.js` (nuevo) |
| Estimación | 6 h |

**Pasos:** `routes.js` pasa a búsqueda/paginación contra la API (elimina el filtro local sobre 100); nuevos `GET /routes/options` y `/trucks/options` con solo `id`+etiqueta para los selects; contador "mostrando X de N" en todas las listas; componente de paginación reutilizable.

**Aceptación:** con 250 rutas sembradas todas son alcanzables y buscables; ningún desplegable depende de un límite mágico de 100.

---

#### T4.4 · Estados de error y carga homogéneos

| Campo | Valor |
|---|---|
| Cierra | M6 (parcial) |
| Depende de | T4.2 |
| Archivos | `frontend/js/components/feedback.js` (nuevo), `pages/{trucks,alerts,truck-detail,routes}.js` |
| Estimación | 3 h |

**Pasos:** unificar los bloques "tabla con error" y "empty state"; skeletons en lugar de spinners sueltos; `aria-busy` durante las cargas; botón "Reintentar".

**Aceptación:** todas las tablas muestran el mismo patrón de error con acción de reintento.

---

#### Bloque 4B — Mediano plazo 🟡🟢

---

#### T4.5 · Consolidación del CSS

| Campo | Valor |
|---|---|
| Cierra | M4, B7 (parcial) |
| Depende de | T4.1 |
| Bloquea a | T4.6, T4.8 |
| Archivos | `frontend/css/**` (renombrar `variables.css`→`tokens.css`, `global.css`→`base.css`; eliminar `bauhaus.css`), los 9 HTML, JS que genera `style="..."` |
| Estimación | 10 h |

**Pasos**
1. Inventariar las 802 líneas de `bauhaus.css` y repartir cada regla en `tokens/base/components/layout/pages`.
2. Resolver duplicados (`.main` ×4, `.kpi-card` ×4, `.sidebar` ×4, `.btn` ×2, etc.).
3. Sustituir los estilos inline generados desde JS por clases.
4. Mover la fuente al HTML con `preconnect`/`preload`; eliminar el `@import` de `variables.css:1` y la carga de Inter (no usada).

**Aceptación:** cero selectores duplicados entre archivos (script de verificación en CI); paridad visual confirmada con capturas antes/después de las 8 páginas en claro/oscuro × 360/768/1440 px; CSS servido ≤ 60 KB minificado.

---

#### T4.6 · Accesibilidad y SEO técnico

| Campo | Valor |
|---|---|
| Cierra | M5, B8 |
| Depende de | T4.5 |
| Archivos | los 9 HTML, `frontend/js/components/modal.js` (nuevo), `pages/{trucks,alerts}.js`, `components/sidebar.js` |
| Estimación | 6 h |

**Pasos:** `role`/`aria-label` en los contenedores de mapa; `modal.js` con focus trap, `aria-modal`, restauración de foco y `Escape`; `width`/`height` en imágenes; `meta description` y `robots: noindex` en páginas internas; revisión de contraste en ambos temas; navegación por teclado del carrusel de temperaturas y alertas.

**Aceptación:** axe-core sin violaciones *serious/critical* en las 8 páginas; flujo principal completable solo con teclado.

---

#### T4.7 · Deduplicación de utilidades frontend

| Campo | Valor |
|---|---|
| Cierra | M6 |
| Depende de | T4.3, T4.4 |
| Archivos | `frontend/js/components/{sidebar,pagination,feedback,modal,map-layers}.js`, `core/helpers.js`, `pages/*.js` |
| Estimación | 4 h |

**Pasos:** eliminar `escapeText()` del sidebar y usar `escapeHtml`; extraer `pagination.js`, `feedback.js`, `modal.js`, `map-layers.js`; centralizar formateadores; regla de lint que prohíba `innerHTML` con interpolaciones no escapadas.

**Aceptación:** −25 % de líneas duplicadas en `frontend/js` (medido con `jscpd`); un único lugar construye HTML de tabla/paginación.

---

#### T4.8 · Build y rendimiento de carga

| Campo | Valor |
|---|---|
| Cierra | B7 |
| Depende de | T4.5 |
| Archivos | `frontend/package.json` (nuevo), configuración esbuild/Vite, `backend/app/main.py` (cabeceras de caché, `GZipMiddleware`) |
| Estimación | 5 h |

**Pasos:** minificar y versionar CSS/JS con hash + manifest consumido por los HTML (o plantilla Jinja); `Cache-Control: public, max-age=31536000, immutable` para assets con hash y `no-cache` para HTML; `GZipMiddleware` como red de seguridad.

**Aceptación:** Lighthouse Performance ≥ 90 en el dashboard con 20 camiones; primera carga < 300 KB sin tiles; sin regresiones en §10.

---

#### T4.9 · Retención y crecimiento de datos

| Campo | Valor |
|---|---|
| Cierra | M7 |
| Depende de | T3.4 |
| Archivos | `backend/scripts/retention.py` (nuevo), `core/config.py`, `compose.yml`, `docs/ops/RUNBOOK.md` |
| Estimación | 5 h |

**Pasos:** job configurable (`READINGS_RETENTION_DAYS=90`, `RESOLVED_ALERTS_RETENTION_DAYS=365`) ejecutado por el servicio `watcher`; evaluar particionado mensual de `readings` si se supera ~1 M filas/mes; documentar impacto en el histórico de `/readings`.

**Aceptación:** job idempotente, con `--dry-run` y logging; el tamaño de tabla se estabiliza en una prueba de 7 días simulados.

---

#### T4.10 · Documentación viva y DX

| Campo | Valor |
|---|---|
| Cierra | M3, B9 |
| Depende de | T4.8 |
| Archivos | `docs/ops/RUNBOOK.md` (nuevo), `docs/api/openapi.json` (nuevo), `README.md`, `Makefile` / `tasks.ps1` (nuevo), `.github/workflows/ci.yml` |
| Estimación | 4 h |

**Pasos:** runbook (arranque, incidentes, rotación de secretos y de claves de dispositivo, restore probado); `openapi.json` versionado y generado en CI para detectar cambios de contrato involuntarios; README con arquitectura, desarrollo, tests y tabla de variables reales; tareas `dev/test/lint/seed`; auditorías de dependencias programadas.

**Aceptación:** un desarrollador nuevo levanta el entorno y ejecuta los tests en < 15 min siguiendo solo el README.

---

#### T4.11 · Idempotencia del seed y datos de demo

| Campo | Valor |
|---|---|
| Cierra | B5 |
| Depende de | T3.1 |
| Archivos | `backend/scripts/seed_demo.py`, `docs/INSTALLATION.md` |
| Estimación | 2 h |

**Pasos:** buscar la ruta por nombre antes de crearla; flag `--reset` explícito; claves solo con `--print-keys`; `--trucks N --devices M` para pruebas de carga.

**Aceptación:** ejecutar el seed 3 veces no duplica rutas ni camiones.

---

#### T4.12 · Pruebas end-to-end y de carga

| Campo | Valor |
|---|---|
| Cierra | A10 (cierre) |
| Depende de | T4.3, T4.6, T4.9 |
| Archivos | `frontend/tests/e2e/**` (nuevo), `backend/scripts/loadtest.py` (nuevo), `.github/workflows/nightly.yml`, `docs/ops/load-test.md` |
| Estimación | 4 h |

**Pasos:** Playwright con 6 flujos críticos (login, alta camión+dispositivo, ruta con OSRM mockeado, ingesta→alerta, configuración, borrado lógico); carga con 50 dispositivos simulados durante 10 min midiendo p95 de `/iot/readings` y del dashboard; informe archivado.

**Aceptación:** E2E verde en CI nightly; p95 de ingesta < 150 ms con 50 dispositivos activos.

---

## 6. Trazabilidad hallazgo → tarea

| Hallazgo | Tareas | Fase | | Hallazgo | Tareas | Fase |
|---|---|---|---|---|---|---|
| C1 | T1.1, T1.2, T1.5 | 1 | | M1 | T1.2, T3.12 | 1, 3 |
| C2 | T1.3 | 1 | | M2 | T3.12 | 3 |
| C3 | T2.1, T2.2 | 2 | | M3 | T1.6, T4.10 | 1, 4B |
| C4 | T2.3, T2.6 | 2 | | M4 | T4.5 | 4B |
| C5 | T2.4, T2.5 | 2 | | M5 | T4.6 | 4B |
| C6 | T1.4 | 1 | | M6 | T4.4, T4.7 | 4 |
| A1 | T3.2 | 3 | | M7 | T2.5, T4.9 | 2, 4B |
| A2 | T3.4 | 3 | | M8 | T3.10 | 3 |
| A3 | T3.3 | 3 | | M9 | T2.4, T3.8 | 2, 3 |
| A4 | T3.5 | 3 | | M10 | T1.5 | 1 |
| A5 | T3.10, T4.1 | 3, 4A | | M11 | T1.5, T3.10, T3.11 | 1, 3 |
| A6 | T4.2 | 4A | | M12 | T3.6 | 3 |
| A7 | T4.3 | 4A | | B1 | T3.1 | 3 |
| A8 | T3.7 | 3 | | B2, B3 | T3.12 | 3 |
| A9 | T3.9 | 3 | | B4 | T3.4 | 3 |
| A10 | T2.7, T3.1, T4.12 | 2, 3, 4B | | B5 | T4.11 | 4B |
| B6 | T1.7 | 1 | | B8 | T4.6 | 4B |
| B7 | T4.5, T4.8 | 4B | | B9 | T4.10 | 4B |
| B10 | T3.1 | 3 | | | | |

---

## 7. Cronograma y gates de fase

| Semana | Fase | Entregable verificable | **Gate de aprobación** |
|---|---|---|---|
| 1 (días 1–2) | F1 | Stack que se niega a arrancar inseguro + contraseña rotable + Alembic gobernando el esquema | Demo de arranque fallido sin secretos · login con rotación forzada · `alembic current == head` · §10 en verde |
| 1 (días 3–6) | F2 | Login/IoT con rate limit, claves HMAC, ingesta atómica e idempotente + tests | `pytest -q` verde · informe de `loadcheck` con 429 · simulador 10 min sin duplicados ni 500 · §10 en verde |
| 2–3 | F3 | Consultas y watcher escalables, I/O async, contenedor productivo, CI completo | Baseline de rendimiento antes/después · CI verde con cobertura ≥ 70 % · contenedor no-root y healthy · §10 en verde |
| 4 | F4A | Assets locales + CSP activa, cliente resiliente, paginación real | Cero violaciones CSP · prueba de caída del backend · 250 rutas navegables · §10 en verde |
| 5–6 | F4B | CSS consolidado, a11y, build, retención, documentación y E2E | Lighthouse ≥ 90/95 · axe sin críticos · E2E verde · runbook probado |

**Regla:** no se inicia una fase sin el gate de la anterior cerrado y registrado en §9.

---

## 8. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación | Tarea |
|---|---|---|---|
| El `.env` nuevo invalida el acceso al admin existente | Bloqueo de la demo | `must_change_password` + `scripts/reset_admin.py` + respaldo previo | T1.3, T1.5 |
| El dedupe de `readings` borra filas | Pérdida de histórico | Respaldo cifrado obligatorio + `--dry-run` con conteo + downgrade del índice | T2.5 |
| Cambio de esquema de claves de dispositivo | Los ESP32 dejan de autenticar | Modo dual `argon2`/`hmac` + fast-path cacheado; rotación del parque solo con script y ventana anunciada | T2.3 |
| CSP activa rompe el panel | UI inutilizable | `Report-Only` en F3 y eliminación de inline antes de activarla | T3.10, T4.1 |
| Consolidar CSS altera el diseño | Regresión visual | Capturas antes/después en 3 anchos × 2 temas, revisión por página | T4.5 |
| UnitOfWork global | Transacciones mal cerradas | Se hace después del patrón probado en IoT + tests de atomicidad por endpoint | T2.4 → T3.8 |
| Rate limit `memory` con varios workers | Protección parcial | Redis o `limit_req` en el proxy; documentado explícitamente | T2.1, T3.9 |
| Rotar `DEVICE_KEY_PEPPER` | Invalida claves `hmac` | Procedimiento documentado de rotación conjunta | T2.3, T4.10 |

---

## 9. Registro de progreso (única fuente de verdad del estado)

**Leyenda:** ⬜ pendiente · 🟨 en curso · ✅ completada · ⛔ bloqueada
**Instrucción para el agente:** actualizar **solo esta tabla** al iniciar y al terminar una tarea. No duplicar el estado en las fichas.

| Tarea | Fase | Estado | Responsable | Commit | Fecha | Notas / bloqueos |
|---|:--:|:--:|---|---|---|---|
| T1.1 | F1 | ✅ | OpenCode (agente IA) | `2eeae4c` | 2026-11-19 | Fail-fast verificado: sin `SECRET_KEY` y con `COOKIE_SECURE=false` en producción el import termina con exit 1; con `.env` válido `import app.main` OK. |
| T1.2 | F1 | ✅ | OpenCode (agente IA) | `550322a` | 2026-11-19 | Renombrado a `compose.yml`; `docker compose config` falla sin `SECRET_KEY`/`DEVICE_KEY_PEPPER`/`ADMIN_PASSWORD`/`POSTGRES_PASSWORD`; healthcheck `/health` en estado healthy. |
| T1.3 | F1 | ✅ | OpenCode (agente IA) | `a8a6877` | 2026-11-19 | `.env` respaldado fuera del repo y regenerado con secretos aleatorios; `DATABASE_URL` coherente; log de configuración efectiva sin secretos; `reset_admin.py` probado. |
| T1.4 | F1 | ✅ | OpenCode (agente IA) | `acc5dd2` | 2026-11-19 | `scripts/migrate.py` con `pg_advisory_lock`; dos migraciones simultáneas exit 0; `alembic current == heads == 0002`; drill `create_all` + `stamp head` verificado. |
| T1.5 | F1 | ✅ | OpenCode (agente IA) | `0ca9be0` | 2026-11-19 | Migración 0002 up/down probada en BD temporal; login con `must_change_password=true`; cambio de contraseña funcional; JWT previo → 401 y JWT nuevo → 200. |
| T1.6 | F1 | ✅ | OpenCode (agente IA) | `47617ee` | 2026-11-19 | `frostbase_v4_pgdata` corregido; tabla de variables sincronizada; comandos PowerShell; `docs/security/evidence` eliminado; README enlaza plan y docs. |
| T1.7 | F1 | ✅ | OpenCode (agente IA) | `211a2f8` | 2026-11-19 | `db-backups/` movido a `%USERPROFILE%\backups\frostbase`; `.gitignore` ampliado; restore drill medido: 0.79 s, conteos verificados; RPO 24 h / RTO 30 min documentados. Cifrado no aplicado: requiere clave del responsable; procedimiento `age`/GPG documentado. |
| T2.1 | F2 | ⬜ | — | — | — | — |
| T2.2 | F2 | ⬜ | — | — | — | — |
| T2.3 | F2 | ⬜ | — | — | — | — |
| T2.4 | F2 | ⬜ | — | — | — | — |
| T2.5 | F2 | ⬜ | — | — | — | — |
| T2.6 | F2 | ⬜ | — | — | — | — |
| T2.7 | F2 | ⬜ | — | — | — | — |
| T2.8 | F2 | ⬜ | — | — | — | — |
| T3.1 | F3 | ⬜ | — | — | — | — |
| T3.2 | F3 | ⬜ | — | — | — | — |
| T3.3 | F3 | ⬜ | — | — | — | — |
| T3.4 | F3 | ⬜ | — | — | — | — |
| T3.5 | F3 | ⬜ | — | — | — | — |
| T3.6 | F3 | ⬜ | — | — | — | — |
| T3.7 | F3 | ⬜ | — | — | — | — |
| T3.8 | F3 | ⬜ | — | — | — | — |
| T3.9 | F3 | ⬜ | — | — | — | — |
| T3.10 | F3 | ⬜ | — | — | — | — |
| T3.11 | F3 | ⬜ | — | — | — | — |
| T3.12 | F3 | ⬜ | — | — | — | — |
| T4.1 | F4A | ⬜ | — | — | — | — |
| T4.2 | F4A | ⬜ | — | — | — | — |
| T4.3 | F4A | ⬜ | — | — | — | — |
| T4.4 | F4A | ⬜ | — | — | — | — |
| T4.5 | F4B | ⬜ | — | — | — | — |
| T4.6 | F4B | ⬜ | — | — | — | — |
| T4.7 | F4B | ⬜ | — | — | — | — |
| T4.8 | F4B | ⬜ | — | — | — | — |
| T4.9 | F4B | ⬜ | — | — | — | — |
| T4.10 | F4B | ⬜ | — | — | — | — |
| T4.11 | F4B | ⬜ | — | — | — | — |
| T4.12 | F4B | ⬜ | — | — | — | — |

### Gates de fase

| Gate | Estado | Fecha | Evidencia |
|---|:--:|---|---|
| F1 cerrado | 🟨 | 2026-11-19 | 7/7 tareas ✅ · `import app.main` con `.env` válido · login + rotación/revocación probados por API · `alembic current == head` · restore drill 0.79 s · **pendiente:** §10 manual en navegador con simulador 10 min (modal de cambio forzado y flujo del panel) |
| F2 cerrado | ⬜ | — | — |
| F3 cerrado | ⬜ | — | — |
| F4A cerrado | ⬜ | — | — |
| F4B cerrado | ⬜ | — | — |

---

## 10. Checklist de regresión manual (ejecutar al cierre de cada fase)

Con el simulador corriendo al menos 10 minutos:

- [ ] Login con credenciales correctas e incorrectas (mensaje genérico, sin filtrar existencia de usuario).
- [ ] Logout y expiración de sesión (redirección a `login.html?next=`).
- [ ] Tema claro/oscuro persistido y sincronizado con `/auth/preferences`.
- [ ] Crear, editar y listar camiones (búsqueda, filtro por estado, paginación).
- [ ] Alta de dispositivo, copia de clave y rotación de clave (la antigua deja de funcionar).
- [ ] Asignar/desasignar dispositivo a camión (incluido el caso de reasignación desde otro camión).
- [ ] Crear ruta con geometría OSRM; editar puntos; recalcular; comportamiento con OSRM caído (`warning`).
- [ ] Asignar/desasignar ruta a camión.
- [ ] Ingesta del simulador: lecturas visibles en el panel y en el detalle del camión.
- [ ] Alerta de temperatura fuera de rango y resolución automática al volver al rango.
- [ ] Alerta de humedad fuera de rango y resolución automática.
- [ ] Alerta de desconexión (detener el simulador 90 s) y resolución al reanudar.
- [ ] KPIs del panel (camiones activos, temperatura promedio, efectividad, lecturas 24 h).
- [ ] Mapa: marcadores, polilíneas, filtro por camión, popups.
- [ ] Historial de alertas: filtros por camión/tipo/estado/fechas y paginación.
- [ ] Detalle de camión: lecturas con filtro de fechas y paginación.
- [ ] Guardar configuración (umbrales, timeout, clima) y ver el efecto en las alertas.
- [ ] Borrado lógico de camión (el histórico se conserva; las alertas se resuelven).
- [ ] `docker compose ps` sin reinicios en bucle; logs sin excepciones no controladas.

---

## 11. Variables de entorno tras el plan

| Variable | Obligatoria | Default | Notas |
|---|:--:|---|---|
| `SECRET_KEY` | ✅ | — | ≥ 64 caracteres aleatorios. Firma JWT. |
| `DEVICE_KEY_PEPPER` | ✅ | — | ≥ 64 caracteres. HMAC de claves de dispositivo. Rotarla invalida claves `hmac`. |
| `ADMIN_PASSWORD` | ✅ | — | ≥ 12 caracteres; se fuerza su cambio en el primer login. |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` | — | `admin` / `admin@frostbase.local` | Solo si no existe ningún administrador. |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | ✅ | — | Sin defaults débiles. |
| `DATABASE_URL` | — | construida por compose | Host `db` en contenedor; `localhost` en local. |
| `ENVIRONMENT` | — | `production` | Activa las validaciones de coherencia. |
| `COOKIE_SECURE` | — | `true` | Obligatorio `true` en producción. |
| `COOKIE_SAMESITE` | — | `lax` | `lax` o `strict`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `60` (tras T3.11) | Con refresh silencioso. |
| `AUTO_CREATE_TABLES` | — | `false` | Solo desarrollo/tests. |
| `RATE_LIMIT_BACKEND` / `REDIS_URL` | — | `memory` / `""` | `redis` en producción multi-worker. |
| `DEVICE_KEY_FAST_PATH` | — | `true` | `false` vuelve a Argon2 por lectura. |
| `ENABLE_INPROCESS_WATCHER` | — | `false` | `true` solo en desarrollo sin compose. |
| `ROUTE_GEOMETRY_ASYNC` | — | `false` | Cálculo OSRM en background (mig 0007). |
| `DISCONNECT_CHECK_SECONDS` | — | `30` | Frecuencia del watcher. |
| `DASHBOARD_FRESH_MINUTES` | — | `10` | Ventana de vigencia del promedio. |
| `OSRM_BASE_URL` / `OSRM_TIMEOUT_SECONDS` | — | proveedor público / `5` | Timeout reducido en T3.5. |
| `WEATHER_CACHE_SECONDS` | — | `600` | TTL de la caché de clima. |
| `READINGS_RETENTION_DAYS` | — | `90` | Añadida en T4.9. |
| `RESOLVED_ALERTS_RETENTION_DAYS` | — | `365` | Añadida en T4.9. |
| `APP_PORT` | — | `8050` | Puerto publicado. |
| `CORS_ORIGINS` | — | localhost 8050/8060/8070 | Sin `*` con credenciales. |
| `FRONTEND_DIR` | — | autodetectado | Ruta alternativa del frontend. |

**Eliminadas por no ser leídas por el código (M1):** `DEVICE_OFFLINE_SECONDS`, `WEATHER_CITY`, `WEATHER_LATITUDE`, `WEATHER_LONGITUDE`.
**Nunca pertenecieron a este proyecto (C2):** `FROSTBASE_SECRET`, `AUTO_SEED`.

---

## 12. Árbol de directorios objetivo (estado final tras F4)

```
frostbase-v2/
├── PLAN-MEJORA.md              ← este documento
├── .env.example
├── compose.yml
├── docker/{Dockerfile,entrypoint.sh}
├── deploy/{nginx.conf,pg-backup.sh}
├── backend/
│   ├── pyproject.toml · requirements.txt · requirements.lock
│   ├── alembic/versions/0001…0007
│   ├── scripts/{migrate,seed_demo,reset_admin,rotate_all_device_keys,disconnect_watcher,retention,loadcheck,loadtest}.py
│   ├── tests/{conftest.py,unit/,integration/}
│   └── app/{main.py,core/,api/,services/,repositories/,models/,schemas/,utils/}
├── frontend/
│   ├── *.html
│   ├── assets/{logo.png,fonts/,vendors/}
│   ├── css/{tokens,base,components,layout}.css + pages/
│   ├── js/{core/,components/,pages/}
│   └── tests/e2e/
├── iot-simulator/
├── docs/
│   ├── api/{API.md,openapi.json}
│   ├── ops/{INSTALLATION.md,RUNBOOK.md,BACKUP-RESTORE.md,perf-baseline.md,load-test.md}
│   ├── DATABASE.md · IOT-INTEGRATION.md · proyecto.md
│   └── img/panel-de-control.jpeg
└── .github/workflows/{ci.yml,nightly.yml}
```

**Eliminados:** `frontend/css/bauhaus.css` (T4.5), `docs/security/evidence/**` (T1.6), `db-backups/` del árbol de trabajo (T1.7).

---

## 13. Historial de cambios del plan

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 2026-11-18 | Creación a partir de la auditoría técnica del commit `4598891`. 3 etapas, 4 fases, 39 tareas. |
