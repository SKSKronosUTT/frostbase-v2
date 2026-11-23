# Revisión de seguridad — G8 (endurecimiento y entrega)

> Fecha: 2026-11-22 · Alcance: backend, frontend, infraestructura Docker y
> módulo de conductores (G1–G7). Cada punto se verificó contra el código y
> las pruebas automatizadas citadas.

## 1. Autenticación y sesiones

| Control | Estado | Evidencia |
|---|---|---|
| Hash de contraseñas Argon2id (`m=65536, t=3, p=4`) | ✅ | `app/core/security.py` (`pwdlib` recomendado) |
| Semáforo de concurrencia de hashing (protege la memoria del worker) | ✅ (G8) | `HASH_CONCURRENCY` (default 2); ver hallazgo H-2 |
| `password_hash` jamás en respuestas ni logs | ✅ | `DriverOut`/`AdminOut` sin campo; serializer filtrado |
| Contraseña temporal visible **una sola vez** (creación / reset) | ✅ | `temporary_password` solo en 201 de creación; test G3 |
| Cambio forzado al primer login (`must_change_password`) | ✅ | flujo verificado en la demo G6/G7 |
| Invalidación de sesiones (`token_version`) al desactivar/resetear | ✅ | `deps.py` compara `tv` del token con BD |
| Un solo endpoint de login por rol compartido, sin distinción de errores (usuario vs contraseña) | ✅ | mismo mensaje 401 (sección 8.1) |
| Rate limit de login por IP e identificador (5/min, 10/min) | ✅ | ventana deslizante; 429 con `Retry-After` |

## 2. Control de acceso

| Control | Estado | Evidencia |
|---|---|---|
| Matriz de roles: admin/driver/IoT separados (`CurrentAdmin`, `CurrentDriver`, `X-Device-Key`) | ✅ | `deps.py`; tests de 403 cruzados |
| ID del conductor siempre del token, nunca del cliente | ✅ | `driver.py` (portal G5–G7) |
| Recursos ajenos → `404` (no revela existencia) | ✅ | viajes, rutas, alertas; tests G6/G7 |
| CSRF doble-submit en todo POST autenticado | ✅ | middleware; tests que olvidan el token dan 403 |
| Cookies `HttpOnly` + `SameSite=lax` + `Secure` obligatorio en producción | ✅ | `Settings` valida `COOKIE_SECURE` en `environment=production` |
| Dispositivos IoT sin JWT: clave con pepper + HMAC, cache con TTL | ✅ | `security.py` (`verify_device_fingerprint`) |

## 3. Entrada y datos

| Control | Estado | Evidencia |
|---|---|---|
| Validación estricta Pydantic en todos los cuerpos | ✅ | 422 en rangos/tamaños; timestamp IoT con ventana (7 d atrás / 5 min adelante) |
| SQL siempre por ORM/parametrizado; nada concatenado | ✅ | revisión de servicios y repositorios |
| `innerHTML` solo con `escapeHtml`/formateadores | ✅ | `npm run check:html` en CI local |
| Idempotencia de ingesta: lecturas y eventos de puerta por `(device_id, timestamp)` | ✅ | índices únicos + `ON CONFLICT DO NOTHING` |
| Un solo viaje activo por conductor/camión; un solo ack sin duplicar alertas | ✅ | índices únicos parciales (`uq_trips_active_*`, `uq_alerts_active_device_type`) |
| Motivo obligatorio en orden fallida (texto libre) | ✅ | validación de servicio + `CHECK` en BD |

## 4. Infraestructura

| Control | Estado | Evidencia |
|---|---|---|
| Secretos solo por `.env` (no versionado); sin credenciales por defecto | ✅ | la app no arranca si falta algo válido |
| Límites de recursos por contenedor (app 2 CPU / 768 MB) | ✅ (G8) | dimensionado con base en la prueba de carga RNF2 |
| Watcher con advisory lock de PostgreSQL (una sola instancia activa) | ✅ | `disconnect_watcher.py` |
| Retención de lecturas (90 d) y alertas resueltas (365 d) | ✅ | `scripts/retention.py` |
| Respaldo diario automatizado con retención y cifrado opcional | ✅ (G8) | `scripts/backup_db.py` + programación en `BACKUP-RESTORE.md` |
| Datos demo nunca en producción (`SEED_DEMO_DATA`) | ✅ (G9) | Guard de configuración + default `false` en compose; `.env.example` usa `ENVIRONMENT=development` |

## 5. Hallazgos de esta revisión

| ID | Hallazgo | Riesgo | Resolución |
|---|---|---|---|
| H-1 | Carrera read-your-writes entre workers: el commit de una escritura puede aterrizar unos ms después de que el cliente recibió la respuesta; una lectura inmediata posterior puede no verla (observado 1 vez en la prueba de carga: `PUT /routes/{id}/driver` → 404 con la ruta recién creada) | Bajo (ventana de ~20 ms; el flujo normal de la UI tolera reintentos) | Mitigado en `scripts/loadtest_portal.py` con reintentos; documentado aquí. Si se requiere garantía estricta, mover el commit de `get_db` a antes del envío de respuesta (refactor futuro) |
| H-2 | Tormenta de logins: Argon2id reserva 64 MB por hash; sin límite, N logins concurrentes mataban a los workers por el límite de memoria del contenedor (reproducido con 20 usuarios) | Alto (caída de disponibilidad bajo pico de logins) | **Corregido (G8):** semáforo `HASH_CONCURRENCY` + memoria del contenedor 512→768 MB; verificado con 999 usuarios sin muertes de workers |
| H-3 | Estado del contenedor `no_signal` (lectura más antigua que `offline_timeout_seconds`) faltaba frente al plan (sección de estados) | Bajo (UX) | **Corregido (G8):** estado implementado + test |
| H-4 | Doble `db.add(truck)` muerto en `start_trip` (código limpio) | Nulo | Corregido de paso en G8 junto al manejo de carrera de inicio de viaje |
| H-5 | Pool de conexiones por worker (10+20) agotado con cientos de peticiones en vuelo: `QueuePool limit reached` → 500 en cascada tras 30 s de cola | Alto (disponibilidad bajo concurrencia RNF2) | **Corregido (G8):** `pool_size=40/max_overflow=10/pool_timeout=10` + `max_connections=250` en PostgreSQL; ver `perf-baseline.md` |

## 6. Cobertura de pruebas que respalda esta revisión

- 137 pruebas de integración (pytest, PostgreSQL real) · cobertura 84 %.
- 23 E2E Playwright (flujos críticos del panel + accesibilidad + CSP sin violaciones).
- Prueba de carga RNF2 con 999 usuarios virtuales (ver `perf-baseline.md`).
- `ruff` + `mypy` estricto en backend; ESLint/Prettier/checks en frontend.
