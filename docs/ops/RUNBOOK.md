# Runbook operativo · FrostBase

Guía de arranque, incidentes y mantenimiento. Para instalación desde cero consulte
[`docs/INSTALLATION.md`](../INSTALLATION.md) y para respaldos
[`BACKUP-RESTORE.md`](BACKUP-RESTORE.md).

## 1. Arranque y verificación

```bash
docker compose up -d --build
docker compose ps
curl -s http://localhost:8050/health/live
curl -s http://localhost:8050/health/ready
```

Servicios esperados:

| Servicio | Estado | Notas |
|---|---|---|
| `frostbase-v4-db` | healthy | PostgreSQL 16, sin puerto expuesto. |
| `frostbase-v4-app` | healthy | Usuario `app` (uid 999), 2 workers. |
| `frostbase-v4-watcher` | running | Advisory lock único. |

`/health/ready` devuelve `503` si PostgreSQL no responde o si
`alembic_version != head`.

## 2. Incidentes frecuentes

### La aplicación no arranca

1. `docker compose logs --tail=100 app`.
2. Si el mensaje es `required variable ... is missing`, revise `.env` (ver
   `docs/INSTALLATION.md` §2).
3. Si es un error de migración, ejecute `docker compose exec app alembic current`
   y `alembic history`.
4. Si el contenedor queda `unhealthy`, consulte `/health/ready` y los logs.

### `400 Invalid host header`

El dominio o IP no está en `ALLOWED_HOSTS`. Añádalo y reinicie:

```bash
# .env
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.10,frostbase.example.com
docker compose up -d
```

### `403 CSRF token inválido o ausente`

El panel envía `X-CSRF-Token` desde la cookie `frostbase_csrf`. Si usa `curl`,
copie ambas cookies y añada la cabecera. Una integración con `Authorization:
Bearer` no requiere CSRF. Para el simulador IoT (`/api/v1/iot/*`) está exento.

### `429` en login o ingesta

Rate limit esperado (login 5/min por IP, 10/15 min por identificador; IoT
30/120 s). Respete `Retry-After`. Si hay varios workers y necesita límites
compartidos, active Redis:

```bash
docker compose --profile redis up -d
# .env
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

### El dashboard no actualiza y muestra «Sin conexión»

1. `curl -s http://localhost:8050/health/ready`.
2. Revise la pestaña Network: las peticiones se cancelan a los 15 s y el cliente
   reintenta con backoff hasta 60 s.
3. Si el JWT expiró, el panel redirige a `login.html?next=...`.

### Clima o rutas sin geometría

- El clima usa Open-Meteo con timeout de 3 s y circuit breaker (3 fallos/60 s).
  Si el proveedor cae, el panel muestra el último dato como `stale`.
- OSRM usa timeout de 5 s y el mismo patrón. La ruta se guarda con
  `geometry_status=failed` y se puede recalcular después.
- Con `ROUTE_GEOMETRY_ASYNC=true` la geometría se calcula en segundo plano.

### El watcher no genera alertas

1. `docker compose logs -f watcher`.
2. Solo una instancia toma el advisory lock; si hay réplicas, es normal que las
   demás esperen.
3. Compruebe `device.last_seen` y `offline_timeout_seconds` en Configuración.

## 3. Rotación de secretos

### Contraseña del administrador

```bash
docker compose exec app python -m scripts.reset_admin
```

Invalida los JWT anteriores (`token_version`). El panel pedirá la nueva clave.

### `SECRET_KEY`

1. Genere un valor nuevo: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
2. Actualice `.env` y `COOKIE_SECURE`/`ENVIRONMENT`.
3. `docker compose up -d`.
4. Todas las sesiones quedan invalidadas.

### `DEVICE_KEY_PEPPER`

Solo protege claves `hmac`. **Rotarlo invalida a todos los dispositivos**:

1. Anuncie una ventana de mantenimiento.
2. Actualice `DEVICE_KEY_PEPPER`.
3. Rote la clave de cada dispositivo con `scripts.rotate_device_key` (una por
   una) y actualice el firmware o `iot-simulator/.env`.
4. Verifique que `/iot/readings` responde `200`.

### Clave de un dispositivo

```bash
docker compose exec app python -m scripts.rotate_device_key --device-id ESP32-FROST-001
```

Guarde la clave mostrada; no se vuelve a mostrar. La anterior deja de funcionar
de inmediato.

## 4. Retención de datos

Valores por defecto: lecturas 90 días, alertas resueltas 365 días.

```bash
# Simulación (no borra)
docker compose exec app python -m scripts.retention --dry-run

# Aplicar ahora
docker compose exec app python -m scripts.retention

# Ajustar ventanas
docker compose exec app python -m scripts.retention --readings-days 120 --alerts-days 500
```

El servicio `watcher` ejecuta el job cada `RETENTION_CHECK_SECONDS` (24 h). El
histórico de `/readings` deja de incluir las filas eliminadas.

Si `readings` supera ~1 M de filas/mes, evalúe particionado mensual antes de
ampliar la retención.

## 5. Respaldos y restauración

Procedimiento probado, RPO 24 h y RTO 30 min en
[`BACKUP-RESTORE.md`](BACKUP-RESTORE.md). Nunca guarde respaldos en el
repositorio.

## 6. Actualización

```bash
git pull
docker compose up -d --build
docker compose exec app alembic current
curl -s http://localhost:8050/health/ready
```

El entrypoint aplica migraciones con advisory lock; es seguro reiniciar con
varias réplicas.
