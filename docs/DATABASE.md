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
| `updated_at` | timestamptz | |

Los mínimos y máximos se calculan en el servicio (`ideal ± tolerancia`), no se almacenan.

## Reglas de negocio relevantes

1. **Una lectura pertenece al camión del dispositivo**, nunca al camión indicado por el cliente.
2. **Alertas de rango:** se crea una alerta si el valor sale de `[min, max]`; si ya existe una activa del mismo tipo se reutiliza.
3. **Resolución:** una lectura de nuevo dentro de rango resuelve la alerta activa correspondiente. La reconexión de un dispositivo resuelve la alerta de desconexión.
4. **Desconexión:** tarea periódica (`DISCONNECT_CHECK_SECONDS`) marca dispositivos con `last_seen` vencido y crea/resuelve alertas.
5. **Baja de camiones:** lógica (`is_deleted = true`), conservando lecturas y alertas históricas.
6. **Rutas:** requieren al menos dos coordenadas distintas; el nombre se deriva del primer y último punto.

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

## Migraciones

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "descripcion del cambio"
```

En Docker, la migración se ejecuta al iniciar el contenedor. El seed (`python -m scripts.seed_demo`) no reemplaza migraciones: es solo para datos de demostración.
