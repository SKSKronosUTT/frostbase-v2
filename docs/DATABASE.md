# Modelo de base de datos

PostgreSQL 16. Esquema gestionado con Alembic (`backend/alembic/versions/0001_initial.py`).

## Diagrama de relaciones

```text
admins            (independiente)

routes 1 ──── N delivery_points
  │
  └── 1 ──── N trucks 1 ──── N devices 1 ──── N readings
                 │               │
                 │               └────────── N alerts
                 └────────────────────────── N alerts

settings          (fila única, id = 1)
```

- `trucks.route_id` → `routes.id` (`ON DELETE SET NULL`).
- `devices.truck_id` → `trucks.id` (`ON DELETE SET NULL`).
- `readings.device_id` → `devices.id` (`ON DELETE CASCADE`).
- `readings.truck_id` → `trucks.id` (`ON DELETE SET NULL`).
- `alerts.device_id` → `devices.id` (`ON DELETE SET NULL`).
- `alerts.truck_id` → `trucks.id` (`ON DELETE SET NULL`).
- `delivery_points.route_id` → `routes.id` (`ON DELETE CASCADE`).

## Tablas

### admins

| Columna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `username` | varchar(80) | único, indexado |
| `email` | varchar(255) | único, indexado |
| `password_hash` | varchar(255) | Argon2 |
| `theme` | varchar(10) | `light` / `dark` |
| `must_change_password` | boolean | Fuerza cambio en el próximo login |
| `token_version` | integer | Revocación de JWT (`tv` claim) |
| `created_at` | timestamptz | |
| `last_login` | timestamptz | nullable |

### trucks

| Columna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `brand` | varchar(100) | |
| `model` | varchar(100) | |
| `year` | integer | 1950–2100 |
| `plate` | varchar(40) | única, indexada, mayúsculas |
| `description` | text | nullable |
| `status` | varchar(20) | `en_ruta`, `disponible`, `mantenimiento` |
| `route_id` | integer FK | nullable |
| `is_deleted` | boolean | baja lógica |
| `created_at` / `updated_at` | timestamptz | |

### devices

| Columna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `device_id` | varchar(100) | único, indexado (identificador del ESP32) |
| `truck_id` | integer FK | nullable |
| `key_hash` | varchar(255) | Argon2, nunca se expone |
| `last_seen` | timestamptz | nullable |
| `created_at` | timestamptz | |

La conexión se considera activa si `last_seen` está dentro del timeout configurado.

### readings

| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `device_id` | integer FK | requerido |
| `truck_id` | integer FK | nullable, copiado del dispositivo |
| `temperature` | double precision | −80…80 °C |
| `humidity` | double precision | 0…100 % |
| `latitude` | double precision | nullable |
| `longitude` | double precision | nullable |
| `reading_timestamp` | timestamptz | hora enviada por el dispositivo |
| `received_at` | timestamptz | hora del servidor |

Índices por `truck_id`, `device_id`, `reading_timestamp` y compuestos para consultas del panel.

### alerts

| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `truck_id` | integer FK | nullable |
| `device_id` | integer FK | nullable |
| `alert_type` | varchar(30) | `temperatura`, `humedad`, `desconexion` |
| `value` | double precision | nullable |
| `min_value` / `max_value` | double precision | umbrales al momento de la alerta |
| `message` | varchar(500) | nullable |
| `started_at` | timestamptz | |
| `resolved_at` | timestamptz | nullable |
| `status` | varchar(20) | `activa`, `resuelta` |

Índice parcial único sobre (`device_id`, `alert_type`) donde `status = 'activa'`, garantizando una sola alerta activa por dispositivo y tipo.

### routes

| Columna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `name` | varchar(255) | generado de los puntos |
| `description` | text | nullable |
| `geometry` | json | lista `[[lat, lon], ...]` de OSRM |
| `status` | varchar(20) | `activa`, `inactiva` |
| `created_at` / `updated_at` | timestamptz | |

### delivery_points

| Columna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `route_id` | integer FK | requerido |
| `name` | varchar(255) | |
| `address` | varchar(500) | nullable |
| `latitude` | double precision | −90…90 |
| `longitude` | double precision | −180…180 |
| `order_index` | integer | orden de visita |

### settings

Fila única (`id = 1`).

| Columna | Tipo | Por defecto |
|---|---|---|
| `id` | integer PK | `1` |
| `temperature_ideal` | double | `-2.0` |
| `temperature_tolerance` | double | `3.0` |
| `humidity_ideal` | double | `80.0` |
| `humidity_tolerance` | double | `5.0` |
| `offline_timeout_seconds` | integer | `60` |
| `weather_city` | varchar(120) | `Tijuana` |
| `weather_latitude` | double | `32.5149` |
| `weather_longitude` | double | `-117.0382` |
| `door_open_grace_seconds` | integer | `30` |
| `updated_at` | timestamptz | |

Los mínimos y máximos se calculan en el servicio (`ideal ± tolerancia`), no se almacenan.

## Tablas del módulo de conductores (G1)

### drivers

| Columna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `first_name` / `last_name` / `middle_name` | varchar(80) | `middle_name` nullable |
| `email` | varchar(254) | único por `lower(email)` |
| `phone` | varchar(20) | |
| `birthdate` | date | |
| `password_hash` | varchar(255) | Argon2, nunca se devuelve |
| `is_active` | boolean | baja lógica |
| `must_change_password` | boolean | fuerza cambio en el primer login |
| `token_version` | integer | revocación de sesiones |
| `created_by` | integer FK → `admins.id` | auditoría, `SET NULL` |
| `last_login` / `created_at` / `updated_at` | timestamptz | |

### login_identities

Correo como identificador global de acceso: un email no puede existir a la vez
como administrador y como conductor (`uq_login_identities_email`). Columnas:
`email`, `account_type` (`admin`/`driver`), `account_id`, `created_at`.
Los servicios la mantienen en la misma transacción que crean/reactivan cuentas.

### driver_truck_assignments

Historial de relevo conductor–camión. Una sola asignación **activa** por
conductor (`uq_assignment_active_driver`) y por camión
(`uq_assignment_active_truck`), ambas índices únicos parciales sobre
`unassigned_at IS NULL`. Columnas: `driver_id` (RESTRICT), `truck_id`
(RESTRICT), `assigned_by` → `admins.id`, `assigned_at`, `unassigned_at`.

### routes (nuevas columnas) y route_delivery_days

- `routes.assigned_driver_id` → `drivers.id` (`SET NULL`): **la ruta pertenece
  al conductor**. `trucks.route_id` se conserva durante la transición hasta que
  el administrador reasigne los vínculos existentes.
- `route_delivery_days`: calendario semanal `weekday 0=domingo … 6=sábado`
  con una sola ruta activa por conductor y día
  (`uq_route_delivery_days_driver_weekday`). `driver_id` está desnormalizado
  para poder exigirlo en la base de datos; los servicios lo mantienen coherente
  con `routes.assigned_driver_id`.

### stores y delivery_points.store_id

`stores` es el catálogo de destinos (`name`, `address`, `phone`, lat/lon,
`is_deleted`). `delivery_points.store_id` enlaza la parada con su tienda; la
parada conserva su copia de nombre/dirección/coordenadas para el historial.

### trips

| Columna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `driver_id` | FK → `drivers.id` | RESTRICT |
| `truck_id` | FK → `trucks.id` | RESTRICT |
| `route_id` | FK → `routes.id` | nullable, `SET NULL` (historial) |
| `state` | varchar(20) | `in_progress` / `completed` |
| `started_at` / `ended_at` | timestamptz | |
| `created_at` | timestamptz | |

Solo un viaje `in_progress` por conductor (`uq_trips_active_driver`) y por
camión (`uq_trips_active_truck`), con índices únicos parciales.

### trip_orders

Órdenes congeladas del viaje: `trip_id` (CASCADE), `delivery_point_id` y
`store_id` (ambas `SET NULL`), `order_index` (único por viaje), `name`,
`address`, `latitude`, `longitude`, `state` (`pending` / `in_delivery` /
`delivered` / `failed`), `started_at`, `delivered_at`, `failure_reason`.

`ck_trip_orders_failed_reason` exige motivo de texto libre no vacío cuando
`state = 'failed'` (decisión G0: no hay reprogramación automática).

### trip_logs

Bitácora de eventos de viaje y de órdenes: `trip_id` (CASCADE), `order_id`
(CASCADE, nullable), `event`, `detail`, `actor_admin_id` / `actor_driver_id`
(`SET NULL`), `created_at`.

### door_events

Eventos de puerta del contenedor, idempotentes por
`uq_door_events_device_time (device_id, event_time)`. Columnas: `device_id`
(RESTRICT), `truck_id` (`SET NULL`), `is_open`, `event_time`, `received_at`,
`evaluated_at`, `alert_id` → `alerts.id` (`SET NULL`).

El índice parcial `ix_door_events_pending` deja listos los eventos abiertos sin
evaluar para el escaneo del watcher: la alerta `puerta` solo se crea si, al
vencer `settings.door_open_grace_seconds` (30 s por defecto), la puerta sigue
abierta durante un viaje `in_progress` sin una orden `in_delivery`.

### alerts (nuevas columnas)

- `trip_id` → `trips.id` (`SET NULL`) e índice `ix_alerts_trip_started`.
- `acknowledged_at` / `acknowledged_by` → `drivers.id`: acuse
  "marcar como vista/entendida".

### truck_threshold_overrides

Umbrales por camión (H3): `truck_id` único (CASCADE) y `temperature_ideal`,
`temperature_tolerance`, `humidity_ideal`, `humidity_tolerance` nullable.
`NULL` significa "usar el valor global de `settings`"; los servicios resuelven
el rango efectivo con fallback.

## Reglas de negocio relevantes

1. **Una lectura pertenece al camión del dispositivo**, nunca al camión indicado por el cliente.
2. **Alertas de rango:** se crea una alerta si el valor sale de `[min, max]`; si ya existe una activa del mismo tipo se reutiliza.
3. **Resolución:** una lectura de nuevo dentro de rango resuelve la alerta activa correspondiente. La reconexión de un dispositivo resuelve la alerta de desconexión.
4. **Desconexión:** tarea periódica (`DISCONNECT_CHECK_SECONDS`) marca dispositivos con `last_seen` vencido y crea/resuelve alertas.
5. **Baja de camiones:** lógica (`is_deleted = true`), conservando lecturas y alertas históricas.
6. **Rutas:** requieren al menos dos coordenadas distintas; el nombre se deriva del primer y último punto.
7. **Conductores:** la baja lógica (`is_active = false`) y el cambio de contraseña incrementan `token_version`, invalidando sus sesiones.
8. **Relevo conductor–camión:** cerrar la asignación anterior (`unassigned_at`) y abrir la nueva en la misma transacción.
9. **Ruta de hoy:** se resuelve en el servidor con `APP_TIMEZONE` (`America/Tijuana`) y el calendario de `route_delivery_days`.
10. **Puerta no autorizada:** alerta solo si, vencida la gracia de `door_open_grace_seconds`, la puerta sigue abierta en un viaje `in_progress` sin orden `in_delivery`.

## Operaciones útiles

```bash
# Conectarse a la base
docker compose exec db psql -U frostbase -d frostbase

# Últimas lecturas
SELECT r.id, t.plate, r.temperature, r.humidity, r.reading_timestamp
FROM readings r LEFT JOIN trucks t ON t.id = r.truck_id
ORDER BY r.reading_timestamp DESC LIMIT 10;

# Alertas activas
SELECT id, alert_type, value, started_at
FROM alerts WHERE status = 'activa' ORDER BY started_at DESC;
```

## Datos de demostración (G9)

El primer arranque con `SEED_DEMO_DATA=true` ejecuta
`python -m scripts.seed_demo --if-empty` antes de levantar la API. El catálogo
es idempotente y se identifica por marcadores estables:

| Entidad | Marcador | Volumen |
|---|---|---|
| Camiones | placa `DEMO-00x` | 4 (en ruta, disponible, mantenimiento) |
| Dispositivos | `ESP32-DEMO-00x` | 3 (1:1 con camión) |
| Conductores | correo `@demo.frostbase.local` | 4 (uno de baja) |
| Tiendas y rutas | nombre `Demo · …` | 5 tiendas, 4 rutas |
| Lecturas | por dispositivo demo | ~430 de las últimas 24 h |
| Viajes y órdenes | de los conductores demo | 4 viajes (1 en curso) |
| Alertas y eventos de puerta | de los dispositivos demo | 4 alertas, 3 eventos |

Reglas del seed:

- **No destructivo**: `--reset-demo` borra solo filas con esos marcadores, en
  orden seguro de claves foráneas; los datos reales nunca se tocan.
- **`--if-empty`**: no siembra si ya hay camiones, conductores o rutas.
- **Solo desarrollo**: `SEED_DEMO_DATA=true` con `ENVIRONMENT=production`
  aborta el arranque.
- Las claves de dispositivo se generan aleatorias y se muestran una vez en los
  logs (`DEMO DEVICE KEY …`); no son recuperables (están hasheadas).

## Tablas del asistente IA (A1)

| Tabla | Contenido |
|---|---|
| `ai_usage` | Contador diario por administrador (`admin_id`, `day`, `count`), único por pareja. Sin contenido de chat. |
| `ai_conversations` | `id` UUID del backend ↔ `agent_session` del ESP32, `last_seq` (último mensaje visto), marcas de tiempo y `closed_at`. Sin contenido de chat. |

La cuota se incrementa con un UPSERT atómico (`count = count + 1` solo si
`count < límite`), por lo que es correcta aunque haya varios workers. El lock
del agente usa `pg_try_advisory_lock(7712028)`: una consulta concurrente a la
vez en todo el despliegue.

## Migraciones

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "descripcion del cambio"
```

En Docker, la migración se ejecuta al iniciar el contenedor. El seed (`python -m scripts.seed_demo`) no reemplaza migraciones: es solo para datos de demostración.
