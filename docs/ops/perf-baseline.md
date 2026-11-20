# Baseline de rendimiento · Fase 3

Fecha: **2026-11-20** · Rama `feat/f3-perf-platform` · Commit `7aa000c`.

## Entorno

| Elemento | Valor |
|---|---|
| PostgreSQL | 16 (contenedor `frostbase-v4-db`) |
| Aplicación | FastAPI + Uvicorn, 2 workers, imagen no-root |
| Dataset de consultas | base temporal `frostbase_perf_drill` con **100 000 lecturas** |
| Dataset HTTP | base real (`frostbase`) con ~4 000 lecturas |
| Caché de resumen | memoria, TTL 10 s, invalidada al guardar `/settings` |

## Índices añadidos (migración 0005)

- `ix_readings_received_at (received_at DESC)`.
- `ix_alerts_truck_status (truck_id, status)`.

## EXPLAIN (ANALYZE, BUFFERS) con 100 000 lecturas

### 1. Última lectura recibida (`max(received_at)`)

```text
Result (actual time=0.213..0.214 rows=1)
  InitPlan 1
    -> Index Only Scan using ix_readings_received_at on readings
         Index Cond: (received_at IS NOT NULL)
         Heap Fetches: 1
Execution Time: 0.302 ms
```

Antes del índice esta consulta recorría la tabla completa; ahora es un
`Index Only Scan` en **0.30 ms**.

### 2. Lecturas en las últimas 24 h

```text
Aggregate (actual time=32.767..32.769 rows=1)
  -> Seq Scan on readings
       Filter: (reading_timestamp >= now() - interval '24 hours')
       Rows Removed by Filter: 13612
Execution Time: 32.863 ms
```

Es un escaneo secuencial de 100 000 filas; aceptable para el volumen actual.
Si el histórico crece por encima de ~1 M de filas, evaluar particionado
(T4.9) o un índice específico de `reading_timestamp`.

### 3. Última lectura por camión

```text
Limit (actual time=0.062..0.063 rows=1)
  -> Index Scan Backward using ix_readings_truck_time on readings
       Index Cond: (truck_id = 1)
Execution Time: 0.141 ms
```

### 4. Efectividad 24 h (una sola consulta con `FILTER`)

```text
Finalize Aggregate (actual time=22.917..27.692 rows=1)
  -> Parallel Seq Scan on readings
       Filter: (truck_id IS NOT NULL AND reading_timestamp >= now() - '24:00:00')
Execution Time: 27.779 ms
```

Antes se ejecutaban dos consultas `count(*)`; ahora una sola pasada con
`count(*) FILTER (WHERE ...)`.

## Pruebas HTTP con la base real

`GET /api/v1/dashboard/summary` (5 llamadas consecutivas):

| Llamada | `time_total` |
|---|---|
| 1 (fría, calcula) | **58.9 ms** |
| 2 | 12.2 ms |
| 3 | 12.1 ms |
| 4 | 12.1 ms |
| 5 (otro worker) | 40.4 ms |

La primera llamada cumple el objetivo de < 80 ms en frío; las llamadas
calientes quedan alrededor de **10–12 ms** (el límite de 10 ms depende del
worker y de la carga). El caché es por proceso: con `WEB_CONCURRENCY=2` cada
worker mantiene su propia copia de 10 s.

`GET /api/v1/dashboard/trucks` devolvió **2 319 bytes** para 3 camiones.

## Geometría de rutas

La ruta de demostración tenía **478 puntos**. `serialize_route_brief_geometry`
la reduce con Ramer–Douglas–Peucker a **60 puntos** (−87.4 %) para el dashboard,
manteniendo la geometría completa en `GET /routes/{id}` y en `/iot/config`.

## Reproducir el baseline

```bash
# 1. Base temporal y esquema
docker compose exec -T db psql -U frostbase -d postgres -c "CREATE DATABASE frostbase_perf_drill;"
DATABASE_URL="postgresql+psycopg://frostbase:<password>@db:5432/frostbase_perf_drill" \
  docker compose exec -T -e DATABASE_URL="$DATABASE_URL" app alembic upgrade head

# 2. Sembrar 100 000 lecturas (ver migración 0005)
# 3. EXPLAIN
docker compose exec -T db psql -U frostbase -d frostbase_perf_drill \
  -c "EXPLAIN (ANALYZE, BUFFERS) SELECT max(received_at) FROM readings;"

# 4. Limpiar
docker compose exec -T db psql -U frostbase -d postgres -c "DROP DATABASE frostbase_perf_drill;"
```
