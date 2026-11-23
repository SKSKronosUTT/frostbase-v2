# Asistente IA (ESP-Claw / ESP32-S3) — documentación base

> **Estado:** borrador de la Fase **A0 (descubrimiento)**. Las secciones marcadas
> `[PENDIENTE A0]` se completan con la evidencia del sondeo real.
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
| TCP `192.168.4.1:80` | **OK**, 7.5 ms |
| `GET /` | **200**, `text/html`, 381 KB — SPA «ESP-Claw Settings» |
| `GET /api/status` | **200** JSON: `boot_id`, `wifi_connected: true`, `ip: 192.168.100.52`, `ap_active: true`, `ap_ssid: esp-claw-CE3085`, `ap_ip: 192.168.4.1`, `wifi_mode: apsta` |
| `GET /api/config` | **200** JSON **sin autenticación**: Wi-Fi (`Mega-2.4G-1CB2`), `llm_api_key` enmascarada, `llm_backend_type: openai_compatible`, `llm_model: deepseek-flash`, `llm_base_url: https://api.deepseek…` |
| `GET /api/webim/ws` | **302** → el handshake WebSocket se redirige; el sondeo lo interpretó como URI inválida (`http://192.168.4.1/`) |
| `GET /api/chat`, `/chat`, `/v1/models` | **302** (rutas no expuestas o redirección a la SPA) |

**Conclusiones:**

- El **LLM es remoto vía DeepSeek** (OpenAI-compatible, modelo `deepseek-flash`),
  no OpenCode Go. Actualizar privacidad, cuota y plan de respaldo.
- `/api/status` es una **comprobación de salud barata** (54 ms) para
  `/ai/status`: no hace falta gastar una consulta al LLM ni abrir el WebSocket.
- La consola **no exige autenticación** en `/api/config` (expone configuración
  con secretos enmascarados). El backend debe ser el único cliente y el ESP32
  no debe publicarse fuera de la red local.
- El contrato WebSocket **sigue pendiente**: el 302 indica ruta equivocada o
  requisitos de `Origin`/query/autenticación. El script de sondeo ya captura
  `Location`, escanea el JS de la SPA en busca de `ws://`, rutas `/api/*` y tipos
  de mensaje, y envía `Origin`.

### 5.1 Contrato HTTP

| Ruta | Código | Content-Type | Notas |
|---|---|---|---|
| `/` | | | |
| `/api/status` | | | |
| `/api/webim/ws` | | | |
| … | | | |

### 5.2 Contrato WebSocket

| Aspecto | Hallazgo |
|---|---|
| URL real del WS | `[PENDIENTE A0]` |
| Autenticación (cabecera/token) | `[PENDIENTE A0]` |
| Formato de envío | `[PENDIENTE A0]` (texto plano vs JSON; claves exactas) |
| Formato de respuesta | `[PENDIENTE A0]` (texto, JSON, eventos) |
| Eventos parciales / streaming | `[PENDIENTE A0]` |
| Errores y códigos | `[PENDIENTE A0]` |
| Keep-alive / cierre | `[PENDIENTE A0]` |

### 5.3 Sesiones

| Aspecto | Hallazgo |
|---|---|
| Crear sesión | ¿`/new` por WS? `[PENDIENTE A0]` |
| Cambiar/aislar sesión | `[PENDIENTE A0]` |
| Límite de sesiones/memoria | `[PENDIENTE A0]` |
| ¿Se puede fijar sesión por protocolo? | `[PENDIENTE A0]` |

### 5.4 Autenticación de la consola

| Aspecto | Hallazgo |
|---|---|
| ¿Exige login? | `[PENDIENTE A0]` |
| ¿Qué expone? (config, claves) | `[PENDIENTE A0]` |
| Mitigación si no hay auth | Solo LAN/AP; backend único cliente |

### 5.5 Modelo (OpenCode Go)

| Aspecto | Hallazgo |
|---|---|
| Proveedor/protocolo configurado | `[PENDIENTE A0]` |
| Modelo elegido y respaldo | `[PENDIENTE A0]` |
| Latencia pregunta simple | `[PENDIENTE A0]` |
| Latencia con herramientas | `[PENDIENTE A0]` |
| ¿Bloquea clientes embebidos? | `[PENDIENTE A0]` |

### 5.6 Pull desde el ESP32

| Aspecto | Hallazgo |
|---|---|
| `cap_http_request` disponible | `[PENDIENTE A0]` |
| Transporte MCP soportado | `[PENDIENTE A0]` |
| ESP32 → backend (`http://<IP_LAN>:8050/...`) | `[PENDIENTE A0]` |
| Backend → ESP32 (Docker) | `[PENDIENTE A0]` |

### 5.7 Memoria y firmware

| Aspecto | Hallazgo |
|---|---|
| ¿La memoria guarda cifras de mensajes? | `[PENDIENTE A0]` |
| ¿Se puede limitar/limpiar? | `[PENDIENTE A0]` |
| Versión/commit de ESP-Claw | `[PENDIENTE A0]` |
| Módulo (flash/PSRAM) | `[PENDIENTE A0]` |

## 6. Decisiones que dependen de A0

1. Adaptador del backend: `webim_ws` (por defecto) u otro.
2. Estrategia de contexto: **Híbrido** (cabecera mínima + *pull* HTTP).
3. `conversation_id` ↔ sesión del agente (por protocolo o vía `/new`).
4. Modelo y proveedor de respaldo.
5. Streaming sí/no (solo si hay eventos parciales).

## 7. Seguridad (resumen)

- **La API del ESP32 no exige autenticación** (comprobado en `/api/status` y
  `/api/config`): solo LAN/AP, backend como único cliente y sin *port forward*.
  Nunca reenviar `/api/config` al navegador.
- Solo el backend llama al agente; el ESP32 no se expone a Internet.
- Token de solo lectura para `agent-read`, hasheado y rotable; **sin escritura**.
- Sin PII en los datos del agente: alias `Conductor {id}`.
- Datos operativos viajan al LLM remoto (OpenCode Go): aviso al usuario.
- Prompt del agente versionado en `docs/ai/prompt-sistema.md`.

## 8. Siguientes pasos

1. Ejecutar el sondeo con el equipo conectado al AP y completar §5.
2. Registrar el contrato en este documento y en el plan.
3. Implementar A1 (adaptador, lock y cuota en PostgreSQL) y seguir A2–A5.

## 9. Referencias

- ESP-Claw: <https://github.com/espressif/esp-claw>
- Consola web: <https://esp-claw.com/en/tutorial/web-config/>
- Configuración/NVS: <https://esp-claw.com/en/reference-project/configuration/>
- Arranque y capacidades: <https://esp-claw.com/en/reference-project/boot-and-runtime/>
- OpenCode Go: `https://opencode.ai/zen/go/v1/{chat/completions | messages | models}`
