# Seguridad del acceso del agente a FrostBase

Documento de la fase **B5**. Cubre el estado actual, el endurecimiento aplicado
y lo que queda pendiente para sacar el token del prompt.

## 1. Estado actual

- El agente del ESP32 llama a `GET /api/v1/agent-read/*` con
  `Authorization: Bearer <AI_AGENT_READ_TOKEN>`.
- El token es de **solo lectura**; no existe ningún endpoint de escritura para
  el agente.
- En el modo HTTP clásico el token vive en el prompt y el LLM remoto lo ve. El
  modo recomendado desde B5 fase 2 es la skill Lua, donde el token queda en un
  archivo privado del dispositivo y no en el prompt.
- El backend es el único cliente del ESP32; el navegador nunca habla con el
  dispositivo.
- Cada lectura se audita sin token ni contenido, y `/ai/status` expone
  `last_agent_read_at`.

## 2. Endurecimiento aplicado (B5 fase 1)

1. **Rate limit antes de autenticar**: los intentos con token ausente o
   inválido también consumen el límite de `agent-read` (60/min por IP). Antes
   solo se limitaban las peticiones autenticadas.
2. **Allowlist de origen opcional**:
   ```env
   AI_AGENT_READ_ALLOWED_IPS=192.168.0.103/32
   ```
   Acepta IPs y CIDR IPv4/IPv6 separados por coma. Vacío = sin restricción
   (comportamiento anterior).
3. **`X-Forwarded-For` solo con confianza explícita**:
   ```env
   AI_AGENT_TRUST_FORWARDED_FOR=false
   ```
   Actívelo únicamente si el backend está detrás de un proxy de confianza que
   sobrescribe la cabecera. Si el backend está expuesto directamente, un
   cliente podría falsificarla.
4. **Auditoría de rechazos**: un origen no permitido genera un evento
   `action=read`, `http_status=403`, `detail=ip_not_allowed`.
5. **Validación al arrancar**: un CIDR inválido impide el arranque con un error
   de configuración.

## 3. Limitación importante con Docker

Con el `app` publicado por Docker, la IP que ve FastAPI suele ser la **puerta
NAT** (por ejemplo `172.x.x.1`), no la IP real del ESP32. Por tanto:

- No active `AI_AGENT_READ_ALLOWED_IPS` con la IP del ESP32 si el backend corre
  con el mapeo de puertos por defecto: bloqueará al agente.
- Opciones válidas:
  1. Ejecutar el backend con **red de host** (solo en un servidor dedicado).
  2. Poner un **proxy inverso de confianza** que añada `X-Forwarded-For` y
     activar `AI_AGENT_TRUST_FORWARDED_FOR=true`.
  3. Dejar la allowlist vacía y proteger el acceso por red/VLAN/firewall.
- En desarrollo, la opción 3 es la recomendada.

## 4. Comprobación

```powershell
# Permitido (ejemplo con proxy de confianza)
curl -H "Authorization: Bearer <token>" `
     -H "X-Forwarded-For: 192.168.0.103" `
     http://<IP_BACKEND>:8050/api/v1/agent-read/fleet-summary

# Origen no permitido → 403
curl -i -H "Authorization: Bearer <token>" `
     -H "X-Forwarded-For: 203.0.113.9" `
     http://<IP_BACKEND>:8050/api/v1/agent-read/fleet-summary
```

En la base de datos:

```sql
select created_at, action, status, http_status, detail
from ai_audit
where action = 'read' and http_status = 403
order by id desc
limit 5;
```

## 5. B5 fase 2: skill Lua

El objetivo estratégico es que el LLM **no vea el token**. La vía implementada
es una skill Lua:

- El agente activa `frostbase` y ejecuta `frostbase_query.lua`.
- El script llama a `http_request` mediante `capability.call` y lee la URL y el
  token de `private/config.txt` en el dispositivo.
- El prompt generado con `.\tasks.ps1 ai-prompt -Skill` **no contiene URL ni
  token**.
- MCP se descartó por ahora: `cap_mcp_client` está expuesto, pero el cliente MCP
  del `edge_agent` no se inicializa correctamente
  ([issue upstream #129](https://github.com/espressif/esp-claw/issues/129)).

Instalación y límites en `docs/ai/SKILL-LUA.md`.

**Riesgo residual**: si `cap_files` está habilitado, el LLM podría intentar leer
`private/config.txt`. La skill lo prohíbe, pero la mitigación fuerte es no
exponer herramientas de archivos o de creación de skills a usuarios no
confiables. Esto reduce la exposición; no es un sandbox.

Hasta completar una alternativa MCP operativa:

- Rotar el token periódicamente y tras cualquier sospecha.
- No exponer el backend a Internet sin VPN/proxy.
- Mantener el token fuera de logs, issues y capturas.
- Usar una VLAN/IoT separada y firewall restrictivo.
- Regenerar el ZIP de la skill si cambia la URL o el token.

## 6. Si se sospecha una filtración

1. Rotar `AI_AGENT_READ_TOKEN` en `.env`.
2. Recrear `app` y regenerar el prompt (`.\tasks.ps1 ai-prompt`).
3. Pegar el prompt nuevo en ESP-Claw.
4. Verificar que el token viejo devuelve `401`.
5. Revisar `ai_audit` por accesos `read` anómalos.
6. Revisar la configuración de red del dispositivo y del backend.
