# Asistente IA (ESP-Claw / ESP32-S3) — documentación base

> **Estado:** **MVP cerrado** (2026-11-25), sin streaming token a token.
> El WebSocket del ESP32 solo notifica cambios; B6.2 queda para una versión
> posterior.
>
> Cierre y alcance: [`ai/MVP-CIERRE.md`](ai/MVP-CIERRE.md) ·
> checklist: [`ai/CHECKLIST-MVP.md`](ai/CHECKLIST-MVP.md) ·
> release: [`ai/RELEASE-NOTES-MVP.md`](ai/RELEASE-NOTES-MVP.md).
>
> Plan de trabajo: `C:\Users\dell\.opencode\plan\PLAN-ASISTENTE-IA.md`
> (decisiones: AP `192.168.4.1`, lock/cuota en PostgreSQL, alias de conductores).

## 1. Qué es

Un apartado **«Asistente»** en el panel del administrador para conversar con el
agente que corre en un ESP32-S3 con **ESP-Claw** y consultar en lenguaje natural
la flota, alertas, viajes, rutas y contenedores. Solo lectura y solo
administradores.

El navegador **nunca** habla con el ESP32: el backend de FrostBase hace de
**proxy** y enriquece/limita las consultas.

## 2. Arquitectura (objetivo)

```text
Navegador admin ──HTTPS──▶ FastAPI ──WebSocket LAN──▶ ESP32-S3 (ESP-Claw)
  ai.html / ai.js           /api/v1/ai/*               agente + sesiones/memoria
                            · lock (PG)                        │
                            · cuota (PG)                       │ HTTPS
                            · respuestas deterministas         ▼
                            /api/v1/agent-read/* (token RO) ◀──┘ (pull)
                                                        OpenCode Go → LLM
```

## 3. Red de desarrollo (AP del ESP32)

| Elemento | Valor |
|---|---|
| SSID | `esp-claw-XXXXXX` (el del dispositivo) |
| IP del agente | `http://192.168.4.1` |
| **IP en la LAN (APSTA)** | **`192.168.100.52`** — el ESP32 está conectado a `Mega-2.4G-1CB2` |
| WebSocket candidato | `ws://192.168.4.1/api/webim/ws` **[pendiente: devuelve 302]** |
| Salida a internet del ESP32 | Necesaria para el LLM remoto (DeepSeek) |
| Backend | Publicado en la LAN en `:8050` para el *pull* del agente |

> **Hallazgo:** el dispositivo está en **APSTA** (`wifi_mode: "apsta"`): mantiene el
> AP (`192.168.4.1`) y a la vez tiene IP en la LAN (`192.168.100.52`). Para el
> backend es preferible la **IP de la LAN** (no obliga a conectar el equipo al AP
> y evita perder el acceso a la red habitual); conviene **reservar esa IP por
> DHCP**. El AP queda como rescate/configuración.

> Al conectar el equipo al AP del ESP32 se pierde el acceso a la red habitual.
> Para demos con varios dispositivos, use doble interfaz (Ethernet a la LAN +
> Wi-Fi al AP) o un router de viaje. En producción se recomienda ESP32 en
> **STA** con IP reservada; `AI_AGENT_URL` es configurable.

## 4. Cómo ejecutar el sondeo (A0)

Script: `backend/scripts/ai_probe.py` (HTTP + WebSocket, sin tocar la BD).

> **Use el Python del proyecto, no el global.** El `python` del sistema no
> tiene `httpx`/`websockets`. Desde `backend/`:
> `.\.venv\Scripts\python.exe` (Windows) o `.venv/bin/python` (Linux/macOS);
> o active el entorno con `.\.venv\Scripts\Activate.ps1`.
> También puede usar `.\tasks.ps1 ai-probe` desde la raíz, que ya usa el venv.

```bash
# 1) Conecte el equipo al AP del ESP32 y compruebe el gateway
#    Windows: ipconfig  → Puerta de enlace predeterminada 192.168.4.1

# 2) Desde el host (backend/)
.\.venv\Scripts\python.exe -m scripts.ai_probe --mode both --output ..\docs\ai\evidencia-a0.json
# Linux/macOS: .venv/bin/python -m scripts.ai_probe --mode both --output ../docs/ai/evidencia-a0.json

# 3) Igual que lo verá el backend (Docker)
docker compose exec app python -m scripts.ai_probe --mode both

# 4) Solo HTTP, o solo WebSocket con un mensaje concreto
.\.venv\Scripts\python.exe -m scripts.ai_probe --mode http
.\.venv\Scripts\python.exe -m scripts.ai_probe --mode ws --message "Resumen de la flota"

# 5) Si el agente exige token o el contrato difiere
.\.venv\Scripts\python.exe -m scripts.ai_probe --mode ws --token "<token>" --payload '{"op":"chat","data":"{message}"}'

# 6) Segunda pasada recomendada (redirects + Origin + escaneo del JS de la SPA)
.\.venv\Scripts\python.exe -m scripts.ai_probe --mode both --follow-redirects --ws-origin http://192.168.4.1 --output ..\docs\ai\evidencia-a0-2.json

# 7) Prueba de conversación completa (crea sesión, envía y espera respuesta)
.\.venv\Scripts\python.exe -m scripts.ai_probe --url http://192.168.100.52 --chat --message "Responde solo: OK"

# 8) Continuar una conversación existente (memoria de sesión)
.\.venv\Scripts\python.exe -m scripts.ai_probe --url http://192.168.100.52 --chat --session <session> --message "¿Qué código te dije?"
```

La segunda pasada es la que debe revelar el WebSocket real: captura `Location`
de los 302, envía la cabecera `Origin` (muchos servidores embebidos la exigen)
y analiza el HTML/JS de la consola para extraer `ws://…`, rutas `/api/*` y tipos
de mensaje. Para el contrato definitivo, complementar con DevTools → Network →
WS en el Web Chat (frames enviados/recibidos).

Si el entorno no existe o está incompleto:

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

El script:

- Rechaza hosts que no sean de red privada salvo `--allow-public`.
- Comprueba TCP y mide latencia.
- Prueba rutas HTTP candidatas (`/`, `/api/status`, `/api/config`, `/api/webim/ws`,
  `/api/chat`, `/chat`, `/v1/models`) y guarda estado, tipo y fragmento.
- Intenta el WebSocket con cinco formatos de payload y **captura los frames**.
- Puede guardar la evidencia en JSON (`--output`).

> Si el puerto no responde, el script termina con código 2 y recuerda conectar
> el equipo al AP. Ese es el caso actual del entorno de desarrollo.

## 5. Evidencia A0

### 5.0 Evidencia recogida (2026-11-23, `docs/ai/evidencia-a0.json`)

> La evidencia local no se versiona (incluye SSID y configuración del
> dispositivo, aunque los secretos estén enmascarados). Se guarda en
> `docs/ai/` y está excluida por `.gitignore`; aquí solo se resumen los
> hallazgos.

| Ruta | Resultado |
|---|---|
| TCP `192.168.4.1:80` | **OK**, 7.5 ms (AP); **LAN `192.168.100.52`** también responde |
| `GET /` | **200**, `text/html`, 381 KB — SPA «ESP-Claw Settings» |
| `GET /api/status` | **200** JSON: `boot_id`, `wifi_connected: true`, `ip: 192.168.100.52`, `ap_active: true`, `ap_ssid: esp-claw-CE3085`, `ap_ip: 192.168.4.1`, `wifi_mode: apsta` |
| `GET /api/config` | **200** JSON **sin autenticación**: Wi-Fi (`Mega-2.4G-1CB2`), `llm_api_key` enmascarada, `llm_backend_type: openai_compatible`, `llm_model: deepseek-flash`, `llm_base_url: https://api.deepseek.com` |
| `GET /api/webim/sessions` | **200** lista de conversaciones (`session`, `source` web/telegram, `chat_id`, `run_state`, `delivery_state`) |
| `POST /api/webim/sessions` | **201** crea conversación web |
| `POST /api/webim/send` | **202** `{run_id, client_message_id, state: "queued"}` |
| `GET /api/webim/sessions/{id}/messages?before=0` | **200** `{messages:[{seq, role, text}], total, revision, run_state}` |
| `WEBSOCKET /ws/webim` | **conecta** con `Origin`; sin frames salvo suscripción (no necesaria para MVP) |
| `/api/webim/ws`, `/api/chat`, `/chat`, `/v1/models` | 302 (rutas inexistentes; redirigen a la SPA/AP) |
| `GET /api/capabilities` | **200** grupos disponibles: `cap_http_request`, `cap_mcp_client`, `cap_im_local`, etc. |

**Conclusiones:**

- **El contrato de chat es HTTP REST, no WebSocket**: sesión → `/api/webim/send` →
  sondeo de `/messages`. El WS es un canal de eventos opcional.
- El **LLM es remoto vía DeepSeek** (OpenAI-compatible, `deepseek-flash`,
  `llm_supports_tools: true`, timeout 120 s), no OpenCode Go. Actualizar
  privacidad, cuota y plan de respaldo.
- La **zona horaria del dispositivo es UTC+8**: hay que enviar explícitamente la
  hora local de `America/Tijuana` en la cabecera de contexto.
- `/api/status` es una **comprobación de salud barata** para `/ai/status`.
- La consola **no exige autenticación** y `POST /api/config` permite cambiar la
  configuración (incluidos secretos): el backend debe ser el único cliente y el
  dispositivo nunca debe publicarse fuera de la red local.
- **Pull pendiente de habilitar**: `cap_http_request` existe pero no está en
  `enabled_cap_groups`/`llm_visible_cap_groups`; el agente respondió que
  necesita URL, autenticación y dominio autorizado. La allowlist actual
  (`search_http_allowlist`) es `*`.

### 5.1 Contrato HTTP (confirmado)

| Ruta | Método | Cuerpo / respuesta |
|---|---|---|
| `/api/status` | GET | salud, `boot_id`, Wi-Fi, AP |
| `/api/capabilities` | GET | grupos de capacidades (`cap_http_request`, `cap_mcp_client`, …) |
| `/api/config` | GET/POST | configuración (no usar desde el backend; expone secretos enmascarados) |
| `/api/webim/sessions` | GET | `{items, has_more, next_cursor, boot_id}` |
| `/api/webim/sessions` | POST | crea sesión → `{session, source:"web", chat_id:"web-ui", alias, run_state}` |
| `/api/webim/sessions/{id}` | GET/PATCH/DELETE | detalle / renombrar (`{title}`) / borrar |
| `/api/webim/sessions/{id}/messages?before=` | GET | `{messages:[{seq, role, text}], total, revision, run_state, delivery_state}` |
| `/api/webim/send` | POST | `{session, client_message_id, text, files:[]}` → `202 {run_id, state:"queued"}` |

### 5.2 Contrato WebSocket

| Aspecto | Hallazgo |
|---|---|
| URL real | `ws://<host>/ws/webim` (el JS usa `window.location.host`) |
| Autenticación | Ninguna; requiere `Origin` correcto |
| Uso | Canal de eventos; **no** se usa para enviar mensajes |
| Envío | `POST /api/webim/send` (ver 5.1) |
| Frames | 0 sin suscripción durante un envío; el MVP usa sondeo de `/messages` |
| Streaming | Posible fase posterior (requiere descubrir el mensaje de suscripción) |

### 5.3 Sesiones

| Aspecto | Hallazgo |
|---|---|
| Crear sesión | `POST /api/webim/sessions` → `201` |
| Identificador | `session` (32 hex) |
| Memoria | **Confirmada**: se recordó `AZUL-42` en un mensaje posterior de la misma sesión |
| Aislamiento | Cada `session` es independiente (web y Telegram conviven) |
| Listar / historial | `GET /sessions` y `GET /sessions/{id}/messages?before=` |
| Borrar / renombrar | `DELETE` / `PATCH {title}` |
| `conversation_id` | El backend mapeará UUID propio ↔ `session` en `ai_conversations` |

### 5.4 Autenticación de la consola

| Aspecto | Hallazgo |
|---|---|
| ¿Exige login? | **No** |
| ¿Qué expone? | `/api/status`, `/api/config` (secretos enmascarados), sesiones de chat |
| Mitigación | Solo LAN/AP; backend único cliente; sin *port forwarding*; nunca reenviar `/api/config` |

### 5.5 Modelo

| Aspecto | Hallazgo |
|---|---|
| Proveedor/protocolo | `openai_compatible` |
| Endpoint | `https://api.deepseek.com` |
| Modelo | `deepseek-flash` (`llm_supports_tools: true`, `llm_timeout_ms: 120000`) |
| Latencia medida | **4.1 s** («OK»), **7–12 s** (respuestas elaboradas) |
| Zona horaria del agente | UTC+8 → incluir hora local de Tijuana en el contexto |
| Respaldo | Pendiente definir (otro modelo/proveedor *Custom* en A4) |

### 5.6 Pull desde el ESP32

| Aspecto | Hallazgo |
|---|---|
| `cap_http_request` | Disponible, **deshabilitada** (fuera de `enabled_cap_groups` y `llm_visible_cap_groups`) |
| `cap_mcp_client` | Disponible, deshabilitada |
| Allowlist HTTP | `search_http_allowlist: "*"` (demasiado amplia; restringir a la IP del backend) |
| ESP32 → backend | Pendiente de probar tras habilitar la capacidad y el token RO |
| Backend → ESP32 | **Probado** vía LAN `192.168.100.52` |

**Pasos para habilitar el pull (acción en la consola del ESP32):**

1. **Capabilities**: habilitar `cap_http_request` y marcarla visible al LLM.
2. **Network Requests**: allowlist `192.168.100.10` (IP LAN del host) en lugar de `*`.
3. En FrostBase: token RO de `agent-read` y URL `http://<IP_LAN>:8050/api/v1/agent-read/...`.
4. Prompt/skill: indicar que use esa API para datos y que el token va en `Authorization`.
5. Probar desde el agente: «¿Cuántas alertas activas hay?».

### 5.7 Memoria y firmware

| Aspecto | Hallazgo |
|---|---|
| ¿La memoria guarda cifras/contenido? | Sí, dentro de la sesión (memoria conversacional) |
| ¿Se puede limitar/limpiar? | Borrando la sesión (`DELETE`) o creando una nueva |
| Versión/commit de ESP-Claw | Pendiente (no expuesta en `/api/status`; revisar pie de la consola) |
| Módulo (flash/PSRAM) | Pendiente de confirmar con el hardware |
| Integraciones activas | Telegram (`tg_bot_token` configurado), WeChat configurado |

## 6. Decisiones tomadas con la evidencia

1. Adaptador del backend: **HTTP REST** (`POST /api/webim/sessions`, `POST /api/webim/send`, `GET /messages`); WS solo como mejora futura.
2. Estrategia de contexto: **P mínimo en A1** (el pull aún no está habilitado) y evolución a **Híbrido (H)** tras habilitar `cap_http_request`.
3. `conversation_id` del backend ↔ `session` del agente, persistido en `ai_conversations`.
4. Modelo: DeepSeek `deepseek-flash`; respaldo a definir en A4.
5. Streaming: no en MVP (WS sin suscripción conocida); indicador de escritura + sondeo.
6. Hora local de Tijuana en la cabecera de contexto (el agente está en UTC+8).

## 7. Seguridad (resumen)

- **La API del ESP32 no exige autenticación** (comprobado en `/api/status` y
  `/api/config`): solo LAN/AP, backend como único cliente y sin *port forward*.
  Nunca reenviar `/api/config` al navegador.
- Solo el backend llama al agente; el ESP32 no se expone a Internet.
- Token de solo lectura para `agent-read`, hasheado y rotable; **sin escritura**.
- Sin PII en los datos del agente: alias `Conductor {id}`.
- Datos operativos viajan al LLM remoto (OpenCode Go): aviso al usuario.
- Prompt del agente versionado en `docs/ai/prompt-sistema.md`.

## 8. Implementación A1 (backend)

**Migración `0011_ai_assistant`** (ya aplicada):

- `ai_usage(admin_id, day, count)` con índice único: cuota diaria atómica.
- `ai_conversations(id UUID, admin_id, agent_session, last_seq, created_at, last_used_at, closed_at)`.

**Endpoints (solo administrador, CSRF y rate limit):**

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/ai/chat` | `{message, conversation_id?}` → `{conversation_id, reply, latency_ms}` |
| GET | `/api/v1/ai/status` | Salud cacheada 15 s (`/api/status` del ESP32) |
| DELETE | `/api/v1/ai/conversations/{id}` | Cierra la conversación y la sesión del agente |

**Configuración (`AI_AGENT_*`):** `ENABLED`, `URL` (IP LAN o AP), `TOKEN`,
`TIMEOUT_SECONDS=90`, `CONNECT_TIMEOUT_SECONDS=5`,
`POLL_INTERVAL_SECONDS=1`, `MAX_MESSAGE_CHARS=500`, `RATE_LIMIT=6/min`,
`DAILY_LIMIT=100`, `STATUS_CACHE_SECONDS=15`, `READ_TOKEN` (para A2).

**Comportamiento:**

- `AgentGate` con `pg_try_advisory_lock(7712028)`: una consulta a la vez entre
  workers; si está ocupado → `429` con `Retry-After`.
- Cuota con UPSERT atómico; al agotarse → `429` (`Retry-After: 3600`).
- Contexto **push mínimo** por mensaje: hora local de Tijuana, totales, alertas
  por tipo, viajes/entregas y hasta 6 camiones críticos. Sin nombres, correos ni
  texto libre.
- Errores mapeados: 404 deshabilitado · 422 mensaje inválido · 429 ocupado/cuota
  · 502 respuesta inválida · 503 inalcanzable · 504 timeout.
- La conversación se cierra borrando la sesión del agente (best-effort).

**Verificación en vivo (2026-11-23, ESP32 en `192.168.100.52`):**

| Comprobación | Resultado |
|---|---|
| `GET /ai/status` | online, 2.2 s, `boot_id` actual |
| `POST /ai/chat` «Responde solo: A1-OK» | **200**, respuesta `A1-OK`, 4.4 s |
| Segundo mensaje en la misma conversación | recordó `A1-OK` |
| `DELETE /ai/conversations/{id}` | 200 y sesión cerrada |

**Limitaciones conocidas:** aún no hay UI (A3); el contexto se envía por *push*
hasta habilitar/implementar el *pull* (`agent-read`, A2); sin streaming.

## 9. Implementación A3 (UI)

- Página **`ai.html`** («Asistente IA») en el menú del administrador.
- Chat con burbujas, indicador de escritura, sugerencias rápidas, contador de
  caracteres y botón «Nueva conversación».
- Estado del agente (en línea / no disponible / deshabilitado) con sondeo cada
  30 s.
- Errores mapeados a mensajes claros (ocupado, cuota, timeout, sin conexión).
- Renderizado seguro: se construyen nodos DOM y `textContent`; nunca
  `innerHTML` con la respuesta.
- Aviso de privacidad visible (el texto se procesa en un LLM externo).
- Responsive y compatible con los temas claro/oscuro.
- E2E con backend simulado: respuesta, agente offline y error 429 (**26/26**
  pruebas E2E en total).

## 10. Implementación A2 (solo lectura + respuestas rápidas)

**Endpoints `agent-read`** (token propio, solo GET, 60/min):

| Ruta | Contenido |
|---|---|
| `GET /api/v1/agent-read/fleet-summary` | Totales, alertas por tipo, viajes y rutas de hoy |
| `GET /api/v1/agent-read/alerts?limit=10` | Alertas activas sin PII |
| `GET /api/v1/agent-read/alerts/today?limit=10` | Creadas/resueltas desde medianoche local + activas ahora |
| `GET /api/v1/agent-read/trucks/{id}/status` | Última lectura, estado, umbrales, alertas |
| `GET /api/v1/agent-read/trips/active?limit=5` | Progreso por viaje con alias de conductor |
| `GET /api/v1/agent-read/routes/today?limit=6` | Rutas de hoy, puntos y pendientes |
| `GET /api/v1/agent-read/thresholds` | Umbrales globales y por camión |

- Autenticación: `Authorization: Bearer <AI_AGENT_READ_TOKEN>` (comparación en
  tiempo constante). Sin token → `401`; asistente deshabilitado o token vacío →
  `404`.
- Respuestas compactas (<4 KB), ISO 8601 con offset, alias `Conductor {id}`,
  sin correos/teléfonos ni texto libre salvo nombre de ruta saneado.
- **Métricas de alertas**: `alerts_active` (ahora), `alerts_created_today` y
  `alerts_resolved_today` (desde medianoche de `America/Tijuana`, incluye
  resueltas), más `window_start`. El prompt indica cómo distinguirlas cuando el
  usuario pregunta por «hoy».
- Solo métodos GET: no existe ninguna ruta de escritura para el agente.

**Respuestas rápidas deterministas** (sin LLM ni cuota):

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/ai/quick` | Lista de sugerencias disponibles |
| `POST` | `/api/v1/ai/quick/{id}` | Texto calculado con datos actuales |

IDs: `fleet-summary`, `active-alerts`, `today-alerts`, `active-trips`,
`critical-containers`, `today-routes`, `trips-history`, `alerts-by-type`,
`truck-status` y `truck-thresholds` (estas dos con `truck_id`). La UI las marca
como **«Datos del sistema»**.

**Verificación en vivo (23/11/2026):**

- Los 6 endpoints responden con el token RO (401 sin token / token inválido).
- Respuesta de `fleet-summary`: **308 B**.
- Las 5 respuestas rápidas responden y no consumen cuota.
- **Pull validado de punta a punta desde el ESP32**: con `cap_http_request`
  habilitada, el agente llamó a `fleet-summary` y respondió con las cifras
  reales del panel (569 alertas y 2 viajes en curso en ese momento).

**Configuración del agente para el pull** (A4):

```text
Para datos de FrostBase usa la API de solo lectura:
  GET http://192.168.100.16:8050/api/v1/agent-read/fleet-summary
  GET http://192.168.100.16:8050/api/v1/agent-read/alerts?limit=10
  GET http://192.168.100.16:8050/api/v1/agent-read/trips/active?limit=5
  GET http://192.168.100.16:8050/api/v1/agent-read/routes/today?limit=6
  GET http://192.168.100.16:8050/api/v1/agent-read/thresholds
Header obligatorio: Authorization: Bearer <AI_AGENT_READ_TOKEN>
```

## 11. Implementación A4/A5 (operación y endurecimiento)

**A4 · Agente y memoria**

- Prompt de operación generado con URL y token reales:
  `python -m scripts.agent_prompt` (`.\tasks.ps1 ai-prompt`). Soporta
  `--no-token` para compartirlo sin secreto.
- **Política de memoria**: la sesión del agente se rota automáticamente tras
  `AI_AGENT_SESSION_TTL_HOURS` (12 h) sin uso; «Nueva conversación» la cierra.
- **Batería conversacional** (`scripts/ai_conversation_check.py`): contrasta las
  respuestas con `agent-read`; resultado en vivo **5/5 (100 %)** con preguntas de
  alertas, viajes, rutas, entregas pendientes y placas.
- **Modelo de respaldo**: procedimiento documentado en
  `docs/ai/OPERACION.md` (cambio de proveedor en el ESP32 sin tocar FrostBase).

**A5 · Auditoría y métricas**

- Tabla `ai_audit` (migración `0012`): `admin_id`, acción (`chat`/`quick`/`close`),
  estado, código HTTP, latencia, `conversation_id` y código de error. **Sin texto
  del chat.**
- La auditoría se escribe en una transacción independiente para que sobreviva a
  errores de la petición.
- `GET /api/v1/ai/metrics?days=7` (solo admin): peticiones, errores, desglose por
  acción/estado y latencia media/p50/p95.
- Retención integrada en el watcher (`AI_AUDIT_RETENTION_DAYS`, 90 por defecto).
- Runbook completo en `docs/ai/OPERACION.md` (red, activación, rotación de token,
  cuotas, memoria, modelo y diagnóstico).

**B1/B2 · Robustez y observabilidad (2026-11-24)**

- **Recuperación tras reinicio**: `ai_conversations.agent_boot_id` (migración
  `0013`) guarda el `boot_id` del ESP32. Cada consulta sondea `/api/status`
  (2 s, `AI_AGENT_BOOT_PROBE_SECONDS`) y rota la sesión si cambió. Si el agente
  responde `404` porque olvidó la sesión, se crea otra y se reintenta **una
  vez** (`session_recovered`).
- **Cortacircuito** (`ai_breaker`, compartido entre workers): tras
  `AI_AGENT_BREAKER_FAILURES` fallos seguidos se responde `503` inmediato con
  `Retry-After` durante `AI_AGENT_BREAKER_SECONDS`; se cierra solo al expirar o
  tras una respuesta correcta. El bloqueo ocurre **antes** de consumir cuota.
- **Límites**: respuestas recortadas y saneadas (`AI_AGENT_MAX_REPLY_CHARS`) y
  máximo de conversaciones activas por admin (`AI_AGENT_MAX_CONVERSATIONS`);
  al superarlo se cierra la más antigua. Las conversaciones inactivas se purgan
  con la retención (`AI_CONVERSATIONS_RETENTION_DAYS`).
- **Observabilidad**: `GET /ai/usage` (cuota, restante y reinicio local),
  `last_agent_read_at` en `/ai/status` (salud del *pull*) y auditoría `read`
  con solo la ruta. La UI muestra cuota, errores, latencia p50/p95 y último
  pull, deshabilita el envío al agotar la cuota y hace cuenta atrás con
  `Retry-After` (429/503).
- **Pruebas**: recuperación de sesión, rotación por `boot_id`, cortacircuito,
  recorte de respuestas, límite de conversaciones, cuota y retención.

**B3 · Conversaciones e historial (2026-11-24)**

- `GET /ai/conversations` lista las conversaciones **activas** del
  administrador (metadatos: título, fechas y último `seq`); no expone la sesión
  del agente.
- `GET /ai/conversations/{id}/messages?limit=50` lee el historial **del agente**
  (FrostBase no guarda el texto), elimina el contexto *push* del mensaje del
  usuario, sanea caracteres de control y recorta cada mensaje. No consume cuota.
- `PATCH /ai/conversations/{id}` renombra en el agente (`PATCH
  /api/webim/sessions/{id}`) y guarda una etiqueta local (`ai_conversations.title`,
  migración `0014`). `DELETE` sigue cerrando la conversación y su sesión.
- **UI**: panel de conversaciones recientes con abrir, renombrar en línea y
  eliminar; la conversación activa se guarda en `localStorage` y se restaura al
  recargar leyendo el historial del agente. Si la sesión ya no existe, se avisa
  y se limpia el estado local.
- **Auditoría**: acciones `messages` y `rename` (solo metadatos, sin contenido).

**B4 · Más respuestas rápidas (2026-11-24)**

- El catálogo determinista pasa de 6 a 10 respuestas. Nuevas:
  - `truck-status` + `truck-thresholds` con `truck_id` (selector de camión).
  - `trips-history`: últimos viajes completados, fallos y motivo saneado/truncado.
  - `alerts-by-type`: conteo y última alerta por tipo.
- `POST /ai/quick/{id}?truck_id=N`; sin `truck_id` en las respuestas por camión
  devuelve `422`, y un camión inexistente `404`.
- Todas se calculan con datos del panel: **sin LLM, sin cuota**, y siguen
  auditándose como `quick` (el detalle incluye el camión cuando aplica).
- La UI añade el selector (cargado de `/trucks/options`) y cuatro botones;
  si no hay camiones, las consultas por camión quedan deshabilitadas.

**B5 fase 1 · endurecimiento de `agent-read` (2026-11-25)**

- El rate limit se aplica **antes** de validar el token: los intentos fallidos
  también están limitados (60/min por IP).
- Allowlist de origen opcional (`AI_AGENT_READ_ALLOWED_IPS`, IPs/CIDR IPv4/IPv6)
  y `X-Forwarded-For` solo con `AI_AGENT_TRUST_FORWARDED_FOR=true` detrás de un
  proxy de confianza.
- Los rechazos por origen se auditan como `read`/`403`/`ip_not_allowed`.
- En Docker la IP vista suele ser la puerta NAT; la allowlist queda desactivada
  por defecto y el procedimiento está en `docs/ai/SEGURIDAD.md`.
- **Pendiente estratégico**: MCP/Lua para que el LLM no vea el token. El
  transporte MCP y la API Lua del firmware aún deben validarse; mientras tanto
  el token sigue en el prompt y debe rotarse.

**B5 fase 2 · skill Lua sin token en el prompt (2026-11-25)**

- Se elige **Lua** en lugar de MCP: `cap_mcp_client` está expuesto pero el
  cliente MCP del `edge_agent` no se inicializa correctamente (issue upstream
  #129). La skill usa `cap_lua` + `capability.call("http_request", …)`.
- Paquete en `esp-claw/skills/frostbase/`: `SKILL.md`, script Lua y
  `private/config.example.txt`. El token se guarda en el dispositivo, no en el
  prompt.
- `python -m scripts.build_agent_skill` (`.\tasks.ps1 ai-skill`) genera
  `dist/frostbase-skill.zip` con la URL y el token actuales. El ZIP es secreto.
- `python -m scripts.agent_prompt --skill` (`.\tasks.ps1 ai-prompt -Skill`)
  genera el prompt sin URL ni token, indicando cómo activar la skill.
- El script solo permite endpoints de lectura conocidos y valida `truck_id`.
- Límite: si `cap_files` está habilitado, un LLM malicioso podría intentar leer
  `private/`; deshabilitarlo para usuarios no confiables. Esto reduce la
  exposición, no sustituye a un sandbox.

**B6 fase 1 · espera y cancelación (2026-11-25)**

- Se confirmó el contrato del WebSocket: tras conectar se envía
  `{"type":"subscribe","scope":"webim"}` y el dispositivo notifica cambios para
  que la SPA recargue mensajes. **No emite deltas parciales de texto**, así que
  el streaming token a token no es posible con este firmware; el backend
  mantiene el sondeo de `/messages`.
- La UI muestra tiempo transcurrido y fase aproximada
  («Enviando consulta», «El agente está pensando», «sigue trabajando») durante
  la espera.
- Nuevo botón **Cancelar** en el indicador: pide confirmación, aborta la espera
  HTTP y avisa de que el agente puede completar la consulta y la cuota ya se
  consumió. No cancela el trabajo en el ESP32.
- El temporizador se limpia al terminar o cancelar; el indicador no se anuncia
  cada segundo a lectores de pantalla (`aria-live="off"`).

**B7 · Pruebas de carga y seguridad del asistente (2026-11-25)**

- `scripts/loadtest_ai.py` (`.\tasks.ps1 ai-loadtest`) lanza N consultas
  simultáneas contra `/ai/chat` y comprueba el lock: **1×200 y (N−1)×429**.
  Imprime estados, p50/p95 y el delta de cuota; consume una consulta diaria.
- `/ai/metrics` ahora agrega en PostgreSQL (`count`, `avg`,
  `percentile_cont`) en lugar de cargar toda la auditoría en memoria. Una
  prueba con 100 filas valida p50/p95, errores por estado y por acción.
- La página `ai.html` entra en la batería axe (temas claro/oscuro) y se añadió
  una prueba E2E de XSS: una respuesta con `<img onerror>` se muestra como
  texto y no se ejecuta.
- Siguen cubiertos por pruebas existentes: timeout, ESP32 caído, sesión
  borrada, rotación por `boot_id`, cuota, lock, token RO sin escritura y
  saneado de motivos de fallo.

## 12. Siguientes pasos

1. ~~Sondeo, contrato, backend, UI, pull y respuestas rápidas~~ ✅.
2. ~~Prompt/skill, rotación de token, seguridad, historial, quick answers,
   espera y pruebas~~ ✅.
3. **MVP cerrado**: entregar con el checklist
   [`ai/CHECKLIST-MVP.md`](ai/CHECKLIST-MVP.md) y las notas
   [`ai/RELEASE-NOTES-MVP.md`](ai/RELEASE-NOTES-MVP.md).
4. **B6.2 diferida**: streaming real cuando el firmware exponga texto parcial o
   progreso utilizable. No implementar sin una fase de descubrimiento.
5. **Backlog**: MCP estable, cancelación real del run y pruebas de 100k
   auditorías.

## 13. Referencias

- ESP-Claw: <https://github.com/espressif/esp-claw>
- Consola web: <https://esp-claw.com/en/tutorial/web-config/>
- Configuración/NVS: <https://esp-claw.com/en/reference-project/configuration/>
- Arranque y capacidades: <https://esp-claw.com/en/reference-project/boot-and-runtime/>
- OpenCode Go: `https://opencode.ai/zen/go/v1/{chat/completions | messages | models}`
