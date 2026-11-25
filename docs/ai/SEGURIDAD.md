# Seguridad del acceso del agente a FrostBase

Documento de la fase **B5**. Cubre el estado actual, el endurecimiento aplicado
y lo que queda pendiente para sacar el token del prompt.

## 1. Estado actual

- El agente del ESP32 llama a `GET /api/v1/agent-read/*` con
  `Authorization: Bearer <AI_AGENT_READ_TOKEN>`.
- El token es de **solo lectura**; no existe ningún endpoint de escritura para
  el agente.
- El token vive en el prompt/skill del ESP-Claw, por lo que el LLM remoto lo
  ve. Es un riesgo aceptado temporalmente.
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

## 5. Lo que sigue pendiente: MCP o Lua

El objetivo estratégico es que el LLM **no vea el token**. Para eso hay que
sacar la llamada HTTP del prompt y encapsularla en una herramienta:

- **MCP**: el firmware expone `cap_mcp_client`, pero falta verificar el
  transporte (stdio/SSE/HTTP), la autenticación y el formato de configuración.
  Si se confirma, FrostBase puede publicar un servidor MCP de solo lectura con
  herramientas tipadas y el token quedaría en la configuración del cliente MCP.
- **Lua/skill**: encapsular la petición HTTP en un módulo del dispositivo; el
  LLM solo vería una función. Requiere confirmar la API Lua del firmware.

Hasta entonces:

- Rotar el token periódicamente y tras cualquier sospecha.
- No exponer el backend a Internet sin VPN/proxy.
- Mantener el token fuera de logs, issues y capturas.
- Usar una VLAN/IoT separada y firewall restrictivo.
- Recordar que el token sigue viajando al LLM como parte del prompt.

## 6. Si se sospecha una filtración

1. Rotar `AI_AGENT_READ_TOKEN` en `.env`.
2. Recrear `app` y regenerar el prompt (`.\tasks.ps1 ai-prompt`).
3. Pegar el prompt nuevo en ESP-Claw.
4. Verificar que el token viejo devuelve `401`.
5. Revisar `ai_audit` por accesos `read` anómalos.
6. Revisar la configuración de red del dispositivo y del backend.
