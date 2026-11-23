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

Login **compartido por rol**: el mismo `POST /auth/login` y el mismo formulario
sirven para administradores (usuario o correo) y conductores (correo). La
respuesta indica el rol (`role: "admin" | "driver"`) y el perfil
correspondiente (`admin` o `driver`). La cookie de sesión (`frostbase_token`)
es la misma; el JWT lleva el rol en el claim `type` (`admin`/`driver`).

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/login` | Inicia sesión (admin o conductor) |
| `POST` | `/auth/logout` | Cierra sesión (`204`) |
| `POST` | `/auth/refresh` | Renueva la cookie de sesión del rol actual |
| `GET` | `/auth/me` | Perfil del administrador actual (solo rol `admin`) |
| `GET` | `/auth/session` | Rol y perfil de la sesión actual (admin o conductor) |
| `PUT` | `/auth/preferences` | Actualiza preferencia de tema (`light`/`dark`, admin) |
| `POST` | `/auth/change-password` | Cambia la contraseña (admin o conductor) y revoca los JWT anteriores |

### Roles y acceso

- Endpoints administrativos (`/trucks`, `/routes`, `/alerts`, `/settings`, …):
  requieren token `admin`. Un conductor recibe `403`.
- Endpoints del conductor (`/driver/*`): requieren token `driver`. Un
  administrador recibe `403`. El ID del conductor siempre viene del token.
- Un conductor inactivo (`is_active = false`) no puede iniciar sesión y sus
  sesiones previas quedan revocadas (`token_version`).
- Mensaje de login fallado siempre genérico: `Usuario o contraseña incorrectos`.

### Conductor

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/driver/me` | Perfil del conductor con su camión asignado (o `null`) |
| `GET` | `/driver/dashboard` | Resumen: camión, ruta de hoy, contenedor y alertas activas |
| `GET` | `/driver/container/live` | Última lectura con umbrales efectivos, estado de puerta (`door_open`, `door_event_at`) |

`container.status`: `ok`, `out_of_range`, `door_open`, `no_signal` (última
lectura más antigua que `offline_timeout_seconds`), `no_data`.
| `GET` | `/driver/container/readings` | Lecturas recientes del contenedor (`limit` 1–500) |
| `GET` | `/driver/routes` | Rutas propias con calendario semanal |
| `GET` | `/driver/routes/{id}` | Detalle de una ruta propia (ajena → `404`) |
| `GET` | `/driver/alerts` | Alertas del camión, paginado (`status` opcional) |
| `POST` | `/driver/alerts/{id}/ack` | Reconoce una alerta propia (ajena → `404`, idempotente) |
| `GET` | `/driver/trips/can-start` | Si puede iniciar viaje y por qué no (`blocking_reason`) |
| `GET` | `/driver/trips/current` | Viaje en curso con órdenes, o `null` |
| `POST` | `/driver/trips/start` | Inicia el viaje de hoy (idempotente) |
| `POST` | `/driver/trips/{id}/end` | Finaliza; pendientes exigen `confirm_pending` |
| `POST` | `/driver/trips/{id}/orders/{oid}/start` | Orden en entrega (solo una a la vez) |
| `POST` | `/driver/trips/{id}/orders/{oid}/deliver` | Marca la orden entregada |
| `POST` | `/driver/trips/{id}/orders/{oid}/fail` | Marca fallida; `reason` obligatorio |
| `GET` | `/driver/trips` | Historial de viajes, paginado |
| `GET` | `/driver/trips/{id}` | Detalle de un viaje propio (ajeno → `404`) |

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

## Asistente IA (administrador)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/ai/chat` | `{message, conversation_id?}` → `{conversation_id, reply, latency_ms}` |
| `GET` | `/ai/status` | Estado del agente (cacheado 15 s) |
| `POST` | `/ai/quick/{id}` | Respuesta determinista con datos actuales (sin LLM) |
| `DELETE` | `/ai/conversations/{id}` | Cierra la conversación y la sesión del agente |

### Endpoints de solo lectura para el agente

Autenticados con `Authorization: Bearer <AI_AGENT_READ_TOKEN>` (no JWT),
solo GET y 60 req/min. Respuestas compactas y sin datos personales.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/agent-read/fleet-summary` | Totales de flota, alertas, viajes y rutas |
| `GET` | `/agent-read/alerts` | Alertas activas (`limit` 1–20) |
| `GET` | `/agent-read/trucks/{id}/status` | Estado y última lectura del camión |
| `GET` | `/agent-read/trips/active` | Viajes en curso (`limit` 1–10) |
| `GET` | `/agent-read/routes/today` | Rutas de hoy (`limit` 1–10) |
| `GET` | `/agent-read/thresholds` | Umbrales globales y por camión |

Requiere rol administrador, CSRF, rate limit (6/min) y cuota diaria
(`AI_AGENT_DAILY_LIMIT`, 100 por defecto). El backend es el único cliente del
ESP32; el navegador nunca lo llama. Si el asistente está deshabilitado
(`AI_AGENT_ENABLED=false`), devuelve `404`. Errores: `429` ocupado/cuota,
`503` inalcanzable, `504` timeout. Documentación completa en
`docs/AI-AGENT.md`.

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

## Conductores (rol administrador)

Gestión CRUD de conductores. Todos los endpoints requieren rol `admin`;
un conductor recibe `403`.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/drivers` | Lista paginada. `search`, `active` (`true`/`false`/`all`), `has_truck` |
| `GET` | `/drivers/options` | Conductores activos con camión (para selectores de rutas) |
| `POST` | `/drivers` | Crea conductor (RF4). Devuelve `temporary_password` **una sola vez** |
| `GET` | `/drivers/{id}` | Detalle con camión asignado y rutas |
| `PATCH` | `/drivers/{id}` | Edita datos (RF6). Cambiar el correo revoca las sesiones |
| `DELETE` | `/drivers/{id}` | Baja lógica: libera camión, revoca sesiones y reporta `affected_routes` |
| `POST` | `/drivers/{id}/restore` | Reactiva al conductor |
| `POST` | `/drivers/{id}/reset-password` | Contraseña temporal visible una sola vez |
| `PUT` | `/drivers/{id}/truck` | Asigna o reasigna camión (relevo con historial) |
| `DELETE` | `/drivers/{id}/truck` | Quita el camión asignado |
| `GET` | `/drivers/{id}/trips` | Historial de viajes del conductor |

### Reglas

- **Correo único global**: no puede coincidir con otro conductor ni con un
  administrador (`409`). Un conductor inactivo conserva su correo reservado:
  se sugiere restaurarlo en lugar de duplicarlo.
- **Contraseña**: opcional en el alta. Si se omite, se genera una temporal de
  16 caracteres que se devuelve **una sola vez**; siempre se exige cambio en
  el primer ingreso (`must_change_password = true`).
- **Baja lógica**: rechazada con `409` si el conductor tiene un viaje en
  curso. Si no, `is_active = false`, se cierra la asignación de camión y
  `token_version += 1` (sus sesiones mueren de inmediato). Las rutas activas
  que tenían a este conductor se devuelven en `affected_routes`.
- **Asignación de camión**: el camión debe existir y no estar en mantenimiento;
  un camión solo puede tener un conductor activo (`409`). El relevo cierra la
  asignación anterior y abre la nueva en la misma transacción.
- Validaciones: teléfono de 10–15 dígitos y conductor mayor de 18 años (`422`).

### Ejemplo de alta

```json
{
  "first_name": "María",
  "last_name": "López",
  "middle_name": null,
  "email": "maria.lopez@frostbase.local",
  "phone": "6641234567",
  "birthdate": "1988-07-22",
  "password": null,
  "truck_id": null
}
```

La respuesta incluye `temporary_password` (por ejemplo `k7Rm2xQvPz9bNaWc`),
visible solo en esa llamada.

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
| `GET` | `/routes` | Lista paginada (`search`, `status`, `missing_driver`) |
| `GET` | `/routes/options` | Lista ligera `{id, label}` para desplegables (máx. 500) |
| `POST` | `/routes` | Crea ruta y calcula geometría con OSRM |
| `GET` | `/routes/{id}` | Detalle con geometría, puntos, camión (legado), conductor y calendario |
| `PUT` | `/routes/{id}/driver` | Asigna o quita el **conductor dueño** y su calendario semanal (G4) |
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

### Asignar ruta (vínculo legado con camión)

```json
{"truck_id": 1}
```

> `POST /routes/{id}/assign` es el vínculo **legado** con el camión. La
> propiedad canónica de la ruta es el conductor (`PUT /routes/{id}/driver`).

### Asignar conductor y calendario semanal (G4)

```json
{"driver_id": 1, "weekdays": [1, 4]}
```

- `weekdays` usa la convención `0=domingo … 6=sábado`, sin repeticiones.
- El conductor debe estar **activo** (con o sin camión). Un conductor inactivo da `422`.
- Solo puede existir **una ruta por conductor y día** (`409` con el día en
  conflicto, p. ej. *"El conductor ya tiene otra ruta asignada el lunes"*).
- `driver_id: null` quita al conductor y limpia su calendario.
- `GET /routes?missing_driver=true` lista las rutas aún sin conductor.

### Camión de la ruta: derivado del conductor (G4.1)

> **El camión de una ruta es el camión activo de su dueño** (regla única).
> `RouteOut.truck` se calcula como `ruta → dueño activo → asignación activa → camión`.
> El vínculo legado `trucks.route_id` está **en desuso** y nadie lo escribe ya.

| Situación | Resultado |
|---|---|
| Dueño con camión T1 | La ruta muestra T1 por construcción |
| Dueño sin camión | La ruta no muestra camión |
| Sin dueño | La ruta no muestra camión |
| Dueño inactivo | La ruta no muestra camión |

**A la inversa**: la ruta de un camión se deriva como `camión → conductor activo →
la de hoy (calendario, `America/Tijuana`) o la única`. Afecta a `/trucks` (detalle),
`/dashboard/trucks` y `/iot/config`.

### Escritores legados deprecados (G4.1)

- `POST /routes/{id}/assign` → `409` con mensaje de migración.
- `PUT /trucks/{id}` con `route_id` no nulo → `409` con mensaje de migración.

### Reporte de conciliación

`GET /routes/legacy-mismatch` (admin) lista las rutas cuyo vínculo legado difiere del derivado:

| `case` | Situación | Acción sugerida |
|---|---|---|
| `owner_without_truck` | Dueño sin camión + legado libre | «Convertir en asignación» (`convertible: true`) |
| `owner_truck_differs` | Dueño con T1 + legado T2 | «El legado sobra; la ruta ya muestra el derivado» |
| `no_owner` | Ruta sin dueño con legado | «Asigne conductor; el camión saldrá de él» |

La columna `trucks.route_id` se eliminará en G6 cuando el reporte esté vacío.

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

`alert_type`: `temperatura`, `humedad`, `desconexion`, `puerta`.
`status`: `activa`, `resuelta`.

Una sola alerta activa por dispositivo y tipo. Se resuelve automáticamente cuando una lectura vuelve al rango o el dispositivo se reconecta. Las desconexiones se detectan con una tarea periódica que compara `last_seen` con el umbral `offline_timeout_seconds` configurado en el panel.

La alerta `puerta` (G7) la crea el watcher cuando un evento de apertura supera el periodo de gracia (`door_open_grace_seconds`) durante un viaje en curso sin entregas activas, y se resuelve al recibir el evento de cierre. El conductor puede reconocerla desde su portal (`POST /driver/alerts/{id}/ack`), lo que queda registrado en `acknowledged_at`/`acknowledged_by`.

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
  "door_open_grace_seconds": 30,
  "weather_city": "Tijuana",
  "weather_latitude": 32.5149,
  "weather_longitude": -117.0382
}
```

Los límites se derivan: `min = ideal - tolerancia`, `max = ideal + tolerancia`. Rangos válidos: temperatura −50…30 °C (resultado −80…60), humedad 0…100 %, timeout 10…86400 s, gracia de puerta 5…600 s (opcional en el `PUT`; si se omite se conserva el valor actual).

---

## IoT

| Método | Ruta | Autenticación | Descripción |
|---|---|---|---|
| `POST` | `/iot/readings` | `X-Device-Key` | Registra lectura y evalúa alertas |
| `POST` | `/iot/door` | `X-Device-Key` | Registra un evento del Reed Switch de la puerta |
| `GET` | `/iot/config` | `X-Device-Id` + `X-Device-Key` | Devuelve camión, ruta y umbrales |

Límites de abuso (ventana deslizante):

| Endpoint | Límite |
|---|---|
| `POST /iot/readings` | 30/min por `device_id` y 120/min por IP |
| `POST /iot/door` | 30/min por `device_id` y 120/min por IP |
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

### POST /iot/door

El ESP32 envía un evento **inmediato** cada vez que el Reed Switch cambia de
estado (abrir/cerrar). Igual que las lecturas, es idempotente por
`(device_id, event_time)`.

```json
{
  "device_id": "ESP32-FROST-001",
  "is_open": true,
  "timestamp": "2026-11-22T22:30:00Z"
}
```

Respuesta:

```json
{
  "success": true,
  "message": "Evento de puerta registrado correctamente",
  "truck_id": 1,
  "door_open": true,
  "duplicate": false,
  "event_id": 42
}
```

Semántica (G7):

- `is_open: true` queda **pendiente**; no genera alerta por sí solo. El
  watcher la evalúa al vencer el periodo de gracia configurable
  (`door_open_grace_seconds`, 30 s por defecto, editable en `PUT /settings`).
- La alerta `puerta` (apertura no autorizada) solo se crea si al vencer la
  gracia la puerta sigue abierta, el camión tiene un viaje `in_progress` y
  **ninguna** orden está `in_delivery`.
- `is_open: false` resuelve de inmediato la alerta `puerta` activa del
  dispositivo y cierra los eventos abiertos pendientes.
- El conductor la ve en su portal en <10 s y puede reconocerla con
  `POST /driver/alerts/{id}/ack`.

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
