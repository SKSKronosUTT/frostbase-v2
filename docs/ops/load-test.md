# Prueba de carga IoT · Fase 4

Script: [`backend/scripts/loadtest.py`](../../backend/scripts/loadtest.py).

## Metodología

1. Inicia sesión como administrador y crea `N` camiones y dispositivos vía API.
2. Cada dispositivo envía lecturas cada `--interval` segundos, con un desfase
   inicial repartido para evitar ráfagas sincronizadas.
3. Se mide la latencia de `POST /api/v1/iot/readings` (p50/p95/p99) y de
   `GET /api/v1/dashboard/summary` cada 5 s.
4. Los errores 429 se reportan aparte: el límite por IP (`IOT_IP_RATE_LIMIT`,
   120/min por defecto) está pensado para una IP de cliente, no para 50
   dispositivos detrás del mismo NAT. Para pruebas de volumen use
   `IOT_IP_RATE_LIMIT` alto en el entorno de carga.

```bash
# Perfil pequeño (validación funcional)
python -m scripts.loadtest --devices 10 --duration 30 --interval 3

# Perfil de capacidad (50 dispositivos)
IOT_IP_RATE_LIMIT=100000 \
  python -m scripts.loadtest --devices 50 --duration 600 --interval 3
```

## Resultados observados (Windows, Docker Desktop)

Fecha: **2026-11-20** · commit de referencia: `feat/f4-hardened-frontend`.

| Perfil | Lecturas | Errores | Ingesta p50 | Ingesta p95 | Dashboard p50 | Dashboard p95 |
|---|---:|---:|---:|---:|---:|---:|
| 10 dispositivos · 30 s · cada 3 s | 99 | 0 | 30.4 ms | **59.3 ms** | 38.3 ms | 103.0 ms |
| 50 dispositivos · 60 s · cada 3 s | 932 | 0 | 43.3 ms | 1 493.5 ms | 62.0 ms | 871.1 ms |

### Lectura de los resultados

- Con 10 dispositivos el p95 de ingesta queda por debajo del objetivo de
  **150 ms**.
- En el perfil de 50 dispositivos el p50 sigue siendo bajo, pero aparecen picos
  de 1–3 s. El entorno de medición es Docker Desktop sobre Windows (I/O de
  PostgreSQL con fsync y disco virtualizado); no es representativo de un host
  Linux con volumen local.
- El objetivo de aceptación (`p95 < 150 ms` con 50 dispositivos) debe validarse
  en el runner Linux del workflow **Nightly** (`loadtest`), que ejecuta 50
  dispositivos durante 60 s y publica el resultado en el log del job.

## Histórico y siguientes pasos

- Si el p95 en Linux supera 150 ms, revisar:
  1. `pool_size`/`max_overflow` de SQLAlchemy y número de workers.
  2. Coste de `settings_service.get_settings` por lectura (cachearlo).
  3. Índices de `alerts` y evaluación de umbrales por lectura.
  4. Uso de Redis para rate limit compartido (`RATE_LIMIT_BACKEND=redis`).
- Las lecturas generadas por la prueba usan placas `LOAD-*` y dispositivos
  `LOAD-*`; se pueden limpiar con un `DELETE` acotado o recreando la base de
  pruebas.
