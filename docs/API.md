# Referencia de la API

Base URL: `http://localhost:8050/api/v1`

Documentación interactiva: `/docs` (Swagger UI), `/redoc` (ReDoc), `/openapi.json`.

## Autenticación

### Administradores

1. `POST /auth/login` con `identifier` (usuario o correo) y `password`.
2. El servidor responde con el perfil y establece la cookie `frostbase_token` (`HttpOnly`, `SameSite=Lax`, 60 min) y la cookie legible `frostbase_csrf`.
3. Todas las rutas administrativas aceptan la cookie o `Authorization: Bearer <token>`.
4. Las peticiones mutantes autenticadas por cookie (`POST`/`PUT`/`PATCH`/`DELETE`) deben enviar `X-CSRF-Token` con el valor de `frostbase_csrf`; si falta o no coincide → `403`.
5. `POST /auth/refresh` renueva la sesión sin cambiar el estado del panel.
6. `POST /auth/logout` elimina ambas cookies.
7. `POST /auth/change-password` exige la contraseña actual y una nueva de al menos 12 caracteres. Al cambiarla se incrementa `token_version` y **todos los JWT emitidos antes dejan de ser válidos** (la sesión que hace el cambio recibe una cookie nueva).

Si `must_change_password` es `true`, el panel bloquea la navegación con un modal
obligatorio hasta definir la nueva contraseña.

Errores de autenticación: `401` (sin sesión o credenciales inválidas), `400`
(contraseña actual incorrecta al cambiarla), `422` (política de contraseña) y
`429` (rate limit o bloqueo por intentos fallidos).

El login aplica una ventana deslizante de **5 intentos/minuto por IP** y
**10 intentos/15 minutos por identificador**. Tras varios fallos se aplica un
bloqueo progresivo con `Retry-After`. El mensaje de error es idéntico para
usuario inexistente y contraseña incorrecta.

### Dispositivos IoT

Encabezado `X-Device-Key: <clave>`. En `GET /iot/config` además se requiere `X-Device-Id`. Nunca se usan JWT de administrador para dispositivos.

## Formato de paginación

Las listas paginadas responden:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

Parámetros comunes: `page` (≥ 1, máximo `10000`) y `page_size` (1–100; lecturas hasta 500).

### Paginación keyset

`GET /readings` y `GET /alerts` aceptan `cursor` (opaco, devuelto en
`next_cursor`). El orden es estable:

- Lecturas: `reading_timestamp DESC, id DESC`.
- Alertas: `started_at DESC, id DESC`.

La respuesta incluye `next_cursor` cuando hay más páginas. Para la siguiente
página envíe `?cursor=<next_cursor>`; no combine `cursor` con `page` > 1.

La búsqueda (`search`) escapa `%`, `_` y `\` para que se traten como texto
literal.

## Errores

FastAPI devuelve `{"detail": "mensaje"}`. Códigos usados:

| Código | Significado |
|---|---|
| `400` | Petición inválida |
| `401` | No autenticado / clave de dispositivo inválida |
| `403` | CSRF ausente o inválido en una mutación autenticada por cookie |
| `404` | Recurso no encontrado |
| `409` | Conflicto (placa o dispositivo duplicado, dispositivo sin camión) |
| `422` | Validación de datos |
| `429` | Rate limit o bloqueo temporal por intentos fallidos |
| `503` | Servicio externo no disponible (OSRM) o `/health/ready` no listo |

---

## Sistema y salud

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health/live` | Proceso vivo |
| `GET` | `/health/ready` | PostgreSQL disponible y `alembic_version == head`; si no, `503` |
| `GET` | `/health` | Alias de compatibilidad de `live` |

Todas las respuestas incluyen `X-Request-ID`. El backend añade
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` y CSP
en `Report-Only`.

---

## Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/login` | Inicia sesión |
| `POST` | `/auth/logout` | Cierra sesión (`204`) |
| `POST` | `/auth/refresh` | Renueva la cookie de sesión |
| `GET` | `/auth/me` | Perfil del administrador actual |
| `PUT` | `/auth/preferences` | Actualiza preferencia de tema (`light`/`dark`) |
| `POST` | `/auth/change-password` | Cambia la contraseña y revoca los JWT anteriores |

### Ejemplo de login

```bash
curl -s -c cookies.txt -X POST http://localhost:8050/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin","password":"<ADMIN_PASSWORD>"}'
```

```json
{
  "admin": {
    "id": 1,
    "username": "admin",
    "email": "admin@frostbase.local",
    "theme": "light",
    "must_change_password": false,
    "created_at": "2026-11-16T19:39:45.753833Z",
    "last_login": "2026-11-16T19:40:03.059663Z"
  }
}
```

### Ejemplo de cambio de contraseña

```bash
curl -s -b cookies.txt -X POST http://localhost:8050/api/v1/auth/change-password \
  -H "Content-Type: application/json" \
  -d '{"current_password":"<actual>","new_password":"<nueva-de-12-o-mas>"}'
```

Devuelve el perfil actualizado y renueva la cookie. La nueva contraseña no puede
ser igual a la actual ni contener el nombre de usuario.

---

## Panel

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/dashboard/summary` | Totales, promedio de temperatura, efectividad, lecturas 24 h, alertas activas |
| `GET` | `/dashboard/trucks` | Camiones con última lectura, GPS, estado de conexión y ruta |
| `GET` | `/dashboard/alerts` | Alertas activas recientes para el panel |
| `GET` | `/dashboard/weather` | Clima actual del destino (Open-Meteo, con caché) |

---

## Camiones

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/trucks` | Lista paginada (`search`, `status`, `page`, `page_size`) |
| `GET` | `/trucks/options` | Lista ligera `{id, label}` para desplegables (máx. 500) |
| `POST` | `/trucks` | Crea camión |
| `GET` | `/trucks/{id}` | Detalle con ruta, dispositivo, última lectura y umbrales |
| `PUT` | `/trucks/{id}` | Actualiza camión |
| `DELETE` | `/trucks/{id}` | Elimina (baja lógica, `204`) |

`status`: `en_ruta`, `disponible`, `mantenimiento`.

### Crear camión

```json
{
  "brand": "Freightliner",
  "model": "M2 106",
  "year": 2022,
  "plate": "ABC-123-A",
  "description": "Unidad de reparto refrigerado",
  "status": "en_ruta",
  "route_id": 1,
  "device_id": 1
}
```

La placa se normaliza a mayúsculas y es única. `route_id` y `device_id` son opcionales; el dispositivo se vincula al camión.

---

## Dispositivos IoT

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/devices` | Lista paginada (`search`) |
| `GET` | `/devices/all` | Todos los dispositivos |
| `GET` | `/devices/unassigned` | Dispositivos sin camión |
| `POST` | `/devices` | Crea dispositivo y devuelve su clave una vez |
| `GET` | `/devices/{id}` | Detalle por ID interno |
| `PUT` | `/devices/{id}` | Cambia el camión vinculado |
| `POST` | `/devices/{id}/rotate-key` | Genera una nueva clave y la devuelve una vez |

### Crear dispositivo

```json
{
  "device_id": "ESP32-FROST-001",
  "truck_id": 1
}
```

Respuesta (`201`):

```json
{
  "id": 1,
  "device_id": "ESP32-FROST-001",
  "truck_id": 1,
  "truck_plate": "ABC-123-A",
  "is_online": false,
  "last_seen": null,
  "created_at": "2026-11-16T19:39:45Z",
  "device_key": "s0KUuzkBhJAJDvH2suTTic4GmN6tP2wtuU2PvC467s0"
}
```

> Guarde `device_key`: solo se muestra al crearla o rotarla. Las claves nuevas se
> guardan como HMAC-SHA256 con `DEVICE_KEY_PEPPER` (verificación O(1)); los
> dispositivos antiguos usan Argon2 con un caché de aciertos de 300 s. Rote la
> clave si el equipo se compromete; la anterior deja de funcionar de inmediato.

---

## Rutas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/routes` | Lista paginada (`search`, `status`) |
| `GET` | `/routes/options` | Lista ligera `{id, label}` para desplegables (máx. 500) |
| `POST` | `/routes` | Crea ruta y calcula geometría con OSRM |
| `GET` | `/routes/{id}` | Detalle con geometría, puntos y camión asignado |
| `PUT` | `/routes/{id}` | Actualiza puntos/estado (recalcula geometría) |
| `DELETE` | `/routes/{id}` | Elimina ruta (`204`) |
| `POST` | `/routes/{id}/calculate` | Recalcula geometría |
| `POST` | `/routes/{id}/assign` | Asigna la ruta a un camión |

`status`: `activa`, `inactiva`. El nombre se genera como `primerPunto - últimoPunto`.

### Crear ruta

```json
{
  "description": "Ruta de reparto",
  "status": "activa",
  "points": [
    {"name": "Villa Fontana", "address": "Tijuana", "latitude": 32.5062, "longitude": -116.9725},
    {"name": "Zona Centro", "address": "Tijuana", "latitude": 32.5333, "longitude": -117.0369},
    {"name": "Playas de Tijuana", "address": "Tijuana", "latitude": 32.5346, "longitude": -117.1217}
  ]
}
```

La geometría se devuelve como lista de pares `[latitud, longitud]`. Si OSRM falla, la ruta se guarda con `geometry: null`, `geometry_status: "failed"` y un campo `warning`.

Con `ROUTE_GEOMETRY_ASYNC=true`, `POST/PUT /routes` responde de inmediato con
`geometry_status: "pending"` y calcula la geometría en segundo plano; consulte
`GET /routes/{id}` para ver si pasó a `ready` o `failed`. El dashboard usa una
geometría simplificada (máx. 400 puntos); `GET /routes/{id}` y `/iot/config`
devuelven la geometría completa.

### Asignar ruta

```json
{"truck_id": 1}
```

---

## Lecturas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/readings` | Lista paginada (`truck_id`, `device_id`, `date_from`, `date_to`) |
| `GET` | `/readings/truck/{truck_id}` | Lecturas de un camión con filtros de fecha |

`date_from`/`date_to` aceptan ISO 8601. `page_size` máximo: 500.

---

## Alertas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/alerts` | Lista paginada (`truck_id`, `alert_type`, `status`, `date_from`, `date_to`) |
| `GET` | `/alerts/{id}` | Detalle de alerta |

`alert_type`: `temperatura`, `humedad`, `desconexion`.
`status`: `activa`, `resuelta`.

Una sola alerta activa por dispositivo y tipo. Se resuelve automáticamente cuando una lectura vuelve al rango o el dispositivo se reconecta. Las desconexiones se detectan con una tarea periódica que compara `last_seen` con el umbral `offline_timeout_seconds` configurado en el panel.

```json
{
  "id": 1,
  "truck_id": 1,
  "truck_plate": "ABC-123-A",
  "device_id": 1,
  "device_identifier": "ESP32-FROST-001",
  "alert_type": "temperatura",
  "value": 8.5,
  "min_value": -5.0,
  "max_value": 1.0,
  "message": "Temperatura fuera de rango: 8.5 °C. Rango permitido: -5.0 a 1.0 °C.",
  "started_at": "2026-11-16T19:40:14.431924Z",
  "resolved_at": null,
  "status": "activa"
}
```

---

## Configuración

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/settings` | Configuración global |
| `PUT` | `/settings` | Actualiza umbrales, timeout y clima |

`PUT` recibe:

```json
{
  "temperature_ideal": -2.0,
  "temperature_tolerance": 3.0,
  "humidity_ideal": 80.0,
  "humidity_tolerance": 5.0,
  "offline_timeout_seconds": 60,
  "weather_city": "Tijuana",
  "weather_latitude": 32.5149,
  "weather_longitude": -117.0382
}
```

Los límites se derivan: `min = ideal - tolerancia`, `max = ideal + tolerancia`. Rangos válidos: temperatura −50…30 °C (resultado −80…60), humedad 0…100 %, timeout 10…86400 s.

---

## IoT

| Método | Ruta | Autenticación | Descripción |
|---|---|---|---|
| `POST` | `/iot/readings` | `X-Device-Key` | Registra lectura y evalúa alertas |
| `GET` | `/iot/config` | `X-Device-Id` + `X-Device-Key` | Devuelve camión, ruta y umbrales |

Límites de abuso (ventana deslizante):

| Endpoint | Límite |
|---|---|
| `POST /iot/readings` | 30/min por `device_id` y 120/min por IP |
| `GET /iot/config` | 60/min por `device_id` y 120/min por IP |

Los límites se aplican **antes** de verificar la clave. Una respuesta `429`
incluye `Retry-After` y `X-RateLimit-Limit`, `X-RateLimit-Remaining` y
`X-RateLimit-Reset` (segundos). El firmware debe esperar `Retry-After` antes de
reintentar y usar backoff exponencial.

### POST /iot/readings

```json
{
  "device_id": "ESP32-FROST-001",
  "temperature": -2.4,
  "humidity": 79.5,
  "latitude": 32.5149,
  "longitude": -117.0382,
  "timestamp": "2026-11-15T22:30:00Z"
}
```

Validaciones:

- `device_id` 3–100 caracteres y debe existir.
- Temperatura −80…80 °C; humedad 0…100 %; latitud/longitud dentro de rango.
- `timestamp` es opcional (si falta se usa la hora del servidor). Si se envía,
  debe estar entre **7 días en el pasado** y **5 minutos en el futuro**. Un
  timestamp sin zona horaria se interpreta como UTC. Fuera de ventana → `422`.
- El camión se obtiene de la base de datos, nunca del payload.

Respuesta:

```json
{
  "success": true,
  "message": "Lectura registrada correctamente",
  "truck_id": 1,
  "alerts": [],
  "duplicate": false,
  "reading_id": 12345
}
```

La ingesta es **idempotente** por `(device_id, reading_timestamp)`. Si se reenvía
el mismo payload, no se crea otra fila: la respuesta trae `duplicate: true`,
`reading_id` de la lectura existente y `alerts: []`. Para que la idempotencia
funcione, el dispositivo debe conservar el mismo `timestamp` al reintentar.

### Códigos HTTP de `/iot/*`

| Código | Causa | Acción sugerida |
|---|---|---|
| `200` | Lectura registrada o duplicada | Continuar; revisar `duplicate` |
| `401` | Falta la clave o no coincide | Revisar clave; no reintentar en bucle rápido |
| `409` | Dispositivo sin camión asignado | Asignar camión desde el panel |
| `422` | Payload inválido o timestamp fuera de ventana | Corregir payload, no reintentar igual |
| `429` | Rate limit | Esperar `Retry-After` y aplicar backoff |
| `5xx` | Error temporal del servidor | Reintentar con backoff exponencial |

### GET /iot/config

```bash
curl -s http://localhost:8050/api/v1/iot/config \
  -H "X-Device-Id: ESP32-FROST-001" \
  -H "X-Device-Key: <clave>"
```

```json
{
  "device_id": "ESP32-FROST-001",
  "truck_id": 1,
  "truck_plate": "ABC-123-A",
  "route": {"name": "Villa Fontana - Playas de Tijuana", "geometry": [[32.5064, -116.9727]]},
  "temperature_min": -5.0,
  "temperature_max": 1.0,
  "humidity_min": 75.0,
  "humidity_max": 85.0
}
```

### Rotación de claves de dispositivo

- Al crear o rotar un dispositivo se devuelve `device_key` **una sola vez**.
- Las claves nuevas usan HMAC-SHA256 con `DEVICE_KEY_PEPPER` (verificación O(1)).
- Los dispositivos previos a la migración `0003_device_key_scheme` siguen con
  Argon2; `DEVICE_KEY_FAST_PATH=true` cachea el acierto 300 s para no repetir el
  KDF en cada lectura. Los fallos nunca se cachean.
- Rotar `DEVICE_KEY_PEPPER` invalida todas las claves HMAC: rote también las
  claves de los dispositivos en la misma ventana.
- `POST /devices/{id}/rotate-key` está limitado a 10 rotaciones/hora por admin.
- Para migrar todo el parque: `python -m scripts.rotate_all_device_keys --dry-run`
  y luego `--yes` (imprime el mapa de claves una sola vez).

Consulte [IOT-INTEGRATION.md](IOT-INTEGRATION.md) para el ejemplo de firmware y
las recomendaciones de backoff.
