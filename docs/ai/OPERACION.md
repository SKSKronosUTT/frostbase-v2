# Operación del asistente IA (A4/A5)

Runbook para desplegar, mantener y diagnosticar el asistente ESP-Claw.

## 1. Requisitos

| Elemento | Valor |
|---|---|
| Agente | ESP32-S3 con ESP-Claw (`http://<ip>/`, AP `esp-claw-XXXXXX`) |
| Red | Preferida: IP de LAN del ESP32 (APSTA). El AP (`192.168.4.1`) es rescate |
| Backend | Publicado en `:8050` y accesible desde el ESP32 (IP de LAN del host) |
| LLM | Configurado en el ESP32 (hoy DeepSeek `deepseek-flash`, compatible OpenAI) |

## 2. Variables de entorno

```env
AI_AGENT_ENABLED=true
AI_AGENT_URL=http://192.168.100.52      # IP del ESP32 (LAN o AP)
AI_AGENT_READ_TOKEN=<secreto>          # token que usa el agente para leer
AI_BACKEND_URL=http://192.168.100.16:8050  # IP del backend tal como la ve el ESP32
AI_AGENT_TIMEOUT_SECONDS=90
AI_AGENT_SESSION_TTL_HOURS=12          # rotación de memoria del agente
AI_AGENT_MAX_REPLY_CHARS=4000          # recorte de respuestas largas
AI_AGENT_MAX_CONVERSATIONS=5           # sesiones activas por administrador
AI_AGENT_RATE_LIMIT=6                  # por minuto y administrador
AI_AGENT_DAILY_LIMIT=100               # por administrador y día
AI_AGENT_BOOT_PROBE_SECONDS=2          # detección de reinicio del ESP32
AI_AGENT_BREAKER_FAILURES=3            # fallos seguidos antes de abrir
AI_AGENT_BREAKER_SECONDS=30            # pausa sin llamar al agente
AI_AUDIT_RETENTION_DAYS=90
AI_CONVERSATIONS_RETENTION_DAYS=30
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.100.16
```

`ALLOWED_HOSTS` **debe** incluir la IP con la que el agente llama al backend; si
no, el *pull* devuelve `400 Invalid host header`.

## 3. Activación y comprobación

```powershell
docker compose up -d --force-recreate app
# Estado del agente
curl http://localhost:8050/api/v1/ai/status  # requiere sesión admin (navegador)
# Endpoint que usa el agente (token RO)
curl -H "Authorization: Bearer <AI_AGENT_READ_TOKEN>" `
     http://192.168.100.16:8050/api/v1/agent-read/fleet-summary
```

Si el segundo comando responde `200`, el *pull* está listo. Si responde `401`,
revise el token; `404`, el asistente está deshabilitado o el token está vacío.

## 4. Prompt del agente

Genere el texto con la URL y el token reales:

```powershell
docker compose exec -T app python -m scripts.agent_prompt
# o desde el host: .\tasks.ps1 ai-prompt
```

Péguelo en la configuración de instrucciones/skill del ESP-Claw. Para compartirlo
sin el secreto use `--no-token`.

> El token es un secreto: no lo envíe en mensajes de chat ni lo pegue en issues.

## 5. Rotación del token de solo lectura

1. Genere un token nuevo y actualice `AI_AGENT_READ_TOKEN` en `.env`.
2. `docker compose up -d --force-recreate app`.
3. Actualice el prompt del ESP32 con el token nuevo.
4. Borre las sesiones antiguas del agente (memoria):

```powershell
# Lista y borra las sesiones web guardadas por FrostBase
docker compose exec -T app python -c "from app.core.database import SessionLocal; from app.models.ai import AiConversation; import httpx; db=SessionLocal(); sessions=[c.agent_session for c in db.query(AiConversation).filter(AiConversation.agent_session.isnot(None))]; c=httpx.Client(base_url='http://192.168.100.52', timeout=10); [c.delete(f'/api/webim/sessions/{s}') for s in sessions]"
```

5. Verifique: token viejo → `401`, token nuevo → `200`.

## 6. Memoria y conversaciones

- Cada conversación del panel ↔ una sesión en el agente (`ai_conversations`).
- Tras **12 h** sin uso (`AI_AGENT_SESSION_TTL_HOURS`) la sesión se rota
  automáticamente: se borra la anterior y se crea una nueva.
- Se guarda el `boot_id` del ESP32 con el que se creó la sesión. Si el
  dispositivo reinicia, la sesión se rota antes de usarla; si aun así el
  agente responde `404` (sesión perdida), el backend crea otra y **reintenta
  una vez** (`detail=session_recovered` en la auditoría).
- Máximo **5 conversaciones activas** por administrador
  (`AI_AGENT_MAX_CONVERSATIONS`); al crear otra se cierra la más antigua.
- «Nueva conversación» cierra la sesión de inmediato.
- El panel muestra las conversaciones activas y permite abrirlas, renombrarlas
  y eliminarlas. El historial se lee del agente (no de FrostBase) y la
  conversación activa se restaura al recargar la página.
- Renombrar actualiza el título en el agente y la etiqueta local
  `ai_conversations.title` (máx. 60 caracteres).
- El backend **no guarda el texto** de los mensajes. Las conversaciones
  inactivas se purgan a los 30 días (`AI_CONVERSATIONS_RETENTION_DAYS`).
- Las respuestas se recortan a `AI_AGENT_MAX_REPLY_CHARS` (4000) y se limpian
  caracteres de control (`detail=reply_truncated` en la auditoría).

## 7. Modelo y respaldo

El modelo se configura en el ESP32 (no en FrostBase). Procedimiento ante fallo
o límite del proveedor:

1. Entre a la consola del ESP32 → sección LLM.
2. Cambie `llm_base_url`, `llm_api_key` y `llm_model` a un proveedor compatible
   con OpenAI (o Anthropic).
3. Guarde y reinicie el dispositivo.
4. Compruebe con una pregunta simple y con `GET /ai/status`.

El backend no necesita cambios: el contrato WebIM es independiente del modelo.

## 8. Auditoría y métricas

- **Auditoría** (`ai_audit`): administrador, acción (`chat`/`quick`/`messages`/
  `rename`/`close`/`read`), estado, código HTTP, latencia, `conversation_id` y
  código de error.
  **Nunca** el contenido del chat. En `read` solo se guarda la ruta consultada
  por el agente (sin token).
- **Métricas**: `GET /api/v1/ai/metrics?days=7` (solo admin) devuelve peticiones,
  errores, desglose por acción/estado y latencia media/p50/p95.
- **Cuota**: `GET /api/v1/ai/usage` (solo admin) devuelve `limit`, `used`,
  `remaining`, `day` y `reset_at` (medianoche local).
- **Salud del pull**: `GET /api/v1/ai/status` incluye `last_agent_read_at`, la
  última vez que el agente consultó `agent-read`; si es antiguo, el agente está
  respondiendo solo con el contexto *push*.
- **Retención**: el watcher elimina auditoría con más de
  `AI_AUDIT_RETENTION_DAYS` (90) y conversaciones inactivas con más de
  `AI_CONVERSATIONS_RETENTION_DAYS` (30), junto con lecturas/alertas.

## 9. Cuotas y límites

| Límite | Valor |
|---|---|
| Mensajes por minuto/admin | 6 (`AI_AGENT_RATE_LIMIT`) |
| Consultas diarias/admin | 100 (`AI_AGENT_DAILY_LIMIT`) |
| Mensaje | 500 caracteres (`AI_AGENT_MAX_MESSAGE_CHARS`) |
| Respuesta del agente | 4000 caracteres (`AI_AGENT_MAX_REPLY_CHARS`) |
| Conversaciones activas/admin | 5 (`AI_AGENT_MAX_CONVERSATIONS`) |
| Cortacircuito | 3 fallos → 30 s sin llamar (`AI_AGENT_BREAKER_*`) |
| Respuestas rápidas | 30/min, sin cuota ni LLM |
| `agent-read` | 60/min, solo GET |

## 10. Diagnóstico rápido

| Síntoma | Causa probable | Acción |
|---|---|---|
| `/ai/status` offline | IP/red del ESP32 o firewall | `ping`/`curl` al ESP32 desde el host y el contenedor |
| `503` al chatear | ESP32 apagado o URL incorrecta | Revisar `AI_AGENT_URL` y `docker compose logs app` |
| `503` con `Retry-After` | Cortacircuito abierto tras fallos seguidos | Esperar el tiempo indicado; al recuperar el agente se cierra solo |
| `504` | LLM lento o caído | Reintentar; revisar proveedor en el ESP32 |
| El chat dice «sesión recuperada» | El ESP32 reinició durante la conversación | Normal: el backend creó otra sesión y reintentó |
| `401` en `agent-read` | Token distinto (rotado) | Actualizar el prompt del ESP32 |
| `400` en `agent-read` | `ALLOWED_HOSTS` sin la IP del backend | Añadir la IP y recrear `app` |
| `429` al chatear | Otra consulta en curso o cuota | Esperar 3 s / 24 h |
| Respuestas con datos viejos | Memoria de sesión | «Nueva conversación» o esperar el TTL |
| El agente no consulta la API | Prompt sin instrucciones o `cap_http_request` deshabilitada | Regenerar el prompt y habilitar la capacidad + allowlist |

## 11. Cambio de IP

1. Actualice `AI_AGENT_URL` (IP del ESP32) y/o `AI_BACKEND_URL` + `ALLOWED_HOSTS`.
2. Regenere el prompt (`scripts.agent_prompt`) y péguelo en el ESP32.
3. Recrear `app` y comprobar `/ai/status` + `agent-read/fleet-summary`.

Atajo: `.\tasks.ps1 net-check` (o `make net-check`) detecta la IP, compara la
configuración, prueba los servicios y muestra las líneas de `.env` y el prompt.

## 12. Mudanza de red en desarrollo (misma LAN)

Escenario típico: el ESP32 y la computadora de desarrollo se mueven juntos a
otra red 2.4 GHz, sin cambiar la zona horaria.

1. **WiFi del ESP32**: conéctese al AP `esp-claw-XXXXXX`, abra
   `http://192.168.4.1`, configure la red nueva y reinicie. Anote la IP nueva
   (tabla DHCP del router o consola del dispositivo).
2. **Diagnóstico** desde la raíz del repositorio:

   ```powershell
   .\tasks.ps1 net-check
   # Si detecta una IP de VPN/interfaz equivocada:
   .\tasks.ps1 net-check -HostIp 192.168.1.45
   ```

   El script muestra la IP local, la configuración actual, el resultado de
   backend local/LAN, ESP32 y `agent-read`, las líneas sugeridas de `.env` y el
   prompt listo para pegar.
3. **Aplicar `.env`** con las líneas sugeridas y recrear:

   ```powershell
   docker compose up -d --force-recreate app watcher
   ```

4. **Repetir `net-check`** hasta que las comprobaciones estén en `OK`.
5. **Pegar el prompt** impreso en ESP-Claw (contiene la URL nueva del backend).
   Para compartirlo sin secreto: `.\tasks.ps1 net-check -NoToken`.
6. **Validar**: chat simple, alertas, historial y reinicio del ESP32. Tras la
   primera consulta, `last_agent_read_at` debe actualizarse.

Requisitos de la red: 2.4 GHz, WPA2, sin portal cautivo ni aislamiento de
clientes; perfil de Windows **Privado** y puerto **8050** permitido en el
firewall. Si el ESP32 y la PC quedan en subredes distintas, el diagnóstico por
LAN fallará aunque el backend esté arriba.
