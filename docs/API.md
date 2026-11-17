# Referencia de la API

Base URL: `http://localhost:8050/api/v1`

Documentación interactiva: `/docs` (Swagger UI), `/redoc` (ReDoc), `/openapi.json`.

## Autenticación

### Administradores

1. `POST /auth/login` con `identifier` (usuario o correo) y `password`.
2. El servidor responde con el perfil y establece la cookie `frostbase_token` (`HttpOnly`, `SameSite=Lax`, expiración configurable).
3. Todas las rutas administrativas aceptan la cookie o `Authorization: Bearer <token>`.
4. `POST /auth/logout` elimina la cookie.

Errores de autenticación: `401` (sin sesión o credenciales inválidas).

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

Parámetros comunes: `page` (≥ 1) y `page_size` (1–100; lecturas hasta 500).

## Errores

FastAPI devuelve `{"detail": "mensaje"}`. Códigos usados:

| Código | Significado |
|---|---|
| `400` | Petición inválida |
| `401` | No autenticado / clave de dispositivo inválida |
| `404` | Recurso no encontrado |
| `409` | Conflicto (placa o dispositivo duplicado, dispositivo sin camión) |
| `422` | Validación de datos |
| `503` | Servicio externo no disponible (OSRM) |

---

## Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/login` | Inicia sesión |
| `POST` | `/auth/logout` | Cierra sesión (`204`) |
| `GET` | `/auth/me` | Perfil del administrador actual |
| `PUT` | `/auth/preferences` | Actualiza preferencia de tema (`light`/`dark`) |

### Ejemplo de login

```bash
curl -s -c cookies.txt -X POST http://localhost:8050/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin","password":"ChangeMe123!"}'
```

```json
{
  "admin": {
    "id": 1,
    "username": "admin",
    "email": "admin@frostbase.local",
    "theme": "light",
    "created_at": "2026-11-16T19:39:45.753833Z",
    "last_login": "2026-11-16T19:40:03.059663Z"
  }
}
```

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

> Guarde `device_key`: solo se muestra al crearla o rotarla.

---

## Rutas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/routes` | Lista paginada (`search`, `status`) |
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

La geometría se devuelve como lista de pares `[latitud, longitud]`. Si OSRM falla, la ruta se guarda con `geometry: null` y un campo `warning`.

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

Una sola alerta activa por dispositivo y tipo. Se resuelve automáticamente cuando una lectura vuelve al rango o el dispositivo se reconecta. Las desconexiones se detectan con una tarea periódica que compara `last_seen` con `DEVICE_OFFLINE_SECONDS` (o el valor configurado en el panel).

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

Validaciones: `device_id` 3–100 caracteres, temperatura −80…80 °C, humedad 0…100 %, latitud/longitud dentro de rangos geográficos. El camión se obtiene de la base de datos, nunca del payload.

Respuesta:

```json
{
  "success": true,
  "message": "Lectura registrada correctamente",
  "truck_id": 1,
  "alerts": []
}
```

Si el dispositivo no tiene camión asignado: `409`.

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

Consulte [IOT-INTEGRATION.md](IOT-INTEGRATION.md) para el ejemplo de firmware.
