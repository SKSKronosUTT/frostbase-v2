# Notas de release · Asistente IA MVP (sin streaming)

**Fecha:** 2026-11-25
**Tag sugerido:** `ai-mvp-v1` (crear solo si el equipo lo autoriza)
**Estado:** MVP cerrado

## Resumen

Se entrega el asistente de operaciones integrado en el panel de FrostBase:
consulta en lenguaje natural sobre flota, alertas, viajes, rutas y contenedores,
con datos frescos, solo lectura y control de acceso para administradores.

El MVP **no incluye streaming token a token**. El WebSocket del ESP32 solo
notifica cambios; la UI muestra tiempo, fase y cancelación local mientras espera
la respuesta completa.

## Funcionalidades incluidas

- Chat administrador ↔ ESP-Claw a través del backend.
- Contexto operativo y *pull* de datos con token de solo lectura.
- 10 respuestas rápidas deterministas, sin LLM ni cuota.
- Historial de conversaciones: abrir, renombrar, eliminar y restaurar.
- Cuota diaria, rate limit, lock global y cortacircuito.
- Recuperación automática tras reinicio del ESP32 o pérdida de sesión.
- Espera con temporizador, fases y cancelación local.
- Auditoría sin contenido, métricas y salud del *pull*.
- Modo skill Lua para reducir la exposición del token en el prompt.
- Endurecimiento de `agent-read`: rate limit previo a auth, allowlist opcional
  y auditoría de rechazos.

## Seguridad

- El agente solo puede leer (`GET`); no existe endpoint de escritura.
- El token RO se compara en tiempo constante y no aparece en la auditoría.
- El backend es el único cliente del ESP32; el navegador no lo llama.
- El modo recomendado es la skill Lua: el token queda en el dispositivo, no en
  el prompt.
- Riesgo residual: si `cap_files` está habilitado, el LLM podría intentar leer
  la configuración privada de la skill. Deshabilitar herramientas de archivos
  para usuarios no confiables.

## Limitaciones conocidas

- Sin streaming de texto (B6.2 diferida).
- Cancelar no detiene el trabajo en el ESP32; la cuota ya se consumió.
- Latencia típica de 4–12 s; el modelo externo puede tardar más.
- MCP no está operativo en el `edge_agent` actual; se usa Lua.
- El historial depende de la sesión del agente; si se pierde, no se recupera el
  texto antiguo.
- El AP del ESP32 no tiene autenticación; no exponerlo fuera de la LAN.

## Verificación de la entrega

| Comprobación | Resultado |
|---|---|
| Backend | 225 passed · cobertura 85.24 % |
| E2E Playwright | 39/39 |
| Accesibilidad `ai.html` | Claro y oscuro sin violaciones graves |
| XSS en respuesta del agente | Bloqueado (texto, no HTML) |
| Carga/lock | 1×200 + 2×429; una sola consulta de cuota |
| Stack | Healthy |
| Esquema | `0014_ai_conversation_title` |

> Los números corresponden a la rama de trabajo B7. Repetir la verificación
> final después de fusionar todas las ramas de release.

## Despliegue

1. Revisar `.env`:
   ```env
   AI_AGENT_ENABLED=true
   AI_AGENT_URL=http://<IP_DEL_ESP32>
   AI_BACKEND_URL=http://<IP_DEL_BACKEND>:8050
   ALLOWED_HOSTS=localhost,127.0.0.1,testserver,<IP_DEL_BACKEND>
   AI_AGENT_READ_TOKEN=<token>
   ```
2. Recrear:
   ```powershell
   docker compose up -d --force-recreate app watcher
   ```
3. Verificar:
   ```powershell
   .\tasks.ps1 net-check -NoPrompt -NoToken
   ```
4. Pegar el prompt o instalar la skill:
   ```powershell
   .\tasks.ps1 ai-prompt          # modo HTTP (incluye token)
   .\tasks.ps1 ai-prompt -Skill   # modo skill (sin token)
   ```
5. Ejecutar el smoke test de `CHECKLIST-MVP.md`.

## Rollback

1. Restaurar el `.env` y el prompt/skill anteriores.
2. Recrear `app`.
3. Verificar `/ai/status` y un chat simple.
4. Si el agente falla, el panel sigue operativo: las respuestas rápidas y el
   resto de FrostBase no dependen del ESP32.

## Diferido a la siguiente versión

- Streaming real (SSE + feature flag + fallback).
- MCP estable si el firmware lo soporta.
- Cancelación real del run en el dispositivo.
- Pruebas de 100k auditorías y ajuste de retención.
- Mejoras de datos demo.

## Referencias

- [`MVP-CIERRE.md`](MVP-CIERRE.md)
- [`CHECKLIST-MVP.md`](CHECKLIST-MVP.md)
- [`OPERACION.md`](OPERACION.md)
- [`SEGURIDAD.md`](SEGURIDAD.md)
- [`../AI-AGENT.md`](../AI-AGENT.md)
