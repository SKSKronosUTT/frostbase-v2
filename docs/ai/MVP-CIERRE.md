# Cierre del MVP del asistente IA

**Estado:** MVP cerrado para la versión actual · **Fecha:** 2026-11-25
**Decisión:** se entrega sin streaming token a token. B6.2 queda para una
versión posterior.

## 1. Alcance entregado

| Área | Estado |
|---|---|
| Chat con el agente ESP-Claw | ✅ Solo administrador, contexto operativo y *pull* |
| `agent-read` de solo lectura | ✅ Token RO, rate limit, allowlist opcional, sin escritura |
| Respuestas rápidas | ✅ 10 respuestas deterministas, sin LLM ni cuota |
| Conversaciones | ✅ Abrir, renombrar, eliminar, restaurar al recargar |
| Robustez | ✅ `boot_id`, recuperación, cortacircuito, límites y cuota |
| Observabilidad | ✅ Auditoría sin contenido, métricas, `/ai/usage`, salud del pull |
| Seguridad | ✅ Token RO, rate limit previo a auth, allowlist, skill Lua |
| Espera y cancelación | ✅ Temporizador, fases y cancelación local |
| Higiene de datos | ✅ Limpieza segura de alertas de prueba |
| Pruebas | ✅ Backend, E2E, axe, XSS y carga de concurrencia |

## 2. Fuera de alcance / diferido

- **B6.2 · streaming real**: el WebSocket `/ws/webim` solo notifica cambios
  (`{"type":"subscribe","scope":"webim"}`); no entrega deltas de texto.
- **MCP operativo**: el cliente MCP del `edge_agent` no se inicializa de forma
  fiable (issue upstream #129). Se usa la skill Lua.
- **Cancelación real del run** en el ESP32: cancelar solo corta la espera del
  navegador.
- **Reanudación de un stream** tras perder la red.

## 3. Limitaciones conocidas

| Limitación | Efecto | Mitigación |
|---|---|---|
| Sin streaming | La respuesta aparece al final (4–12 s típicos) | Temporizador, fases y Cancelar |
| Cancelar no detiene el agente | La cuota ya se consumió y puede devolver 429 después | Aviso explícito y cuenta atrás |
| Token en prompt en modo HTTP | El LLM remoto ve el token | Usar skill Lua (`--skill`) y rotar el token |
| `cap_files` en el dispositivo | El LLM podría intentar leer la config privada de la skill | Deshabilitar herramientas de archivos para usuarios no confiables |
| Historial leído del agente | Si la sesión se perdió, no hay historial antiguo | Se avisa y se limpia el estado local |
| AP del ESP32 sin auth | Cualquiera en la red puede acceder a la consola | Mantenerlo en LAN/VLAN y sin exposición a Internet |

## 4. Arquitectura en una línea

```text
Navegador admin → FastAPI → ESP32-S3 (ESP-Claw) → LLM remoto
                        ↘ PostgreSQL (lock, cuota, conversaciones, auditoría)
```

El navegador nunca habla directamente con el ESP32. El backend es el único
cliente y aplica autenticación, CSRF, límites, lock y auditoría.

## 5. Operación y documentación

- Runbook: [`OPERACION.md`](OPERACION.md)
- Seguridad: [`SEGURIDAD.md`](SEGURIDAD.md)
- Skill Lua: [`SKILL-LUA.md`](SKILL-LUA.md)
- Documentación técnica: [`../AI-AGENT.md`](../AI-AGENT.md)
- Checklist de cierre: [`CHECKLIST-MVP.md`](CHECKLIST-MVP.md)
- Notas de release: [`RELEASE-NOTES-MVP.md`](RELEASE-NOTES-MVP.md)

## 6. Criterios de aceptación del MVP

- Un administrador puede conversar y recibir datos reales del panel.
- Las respuestas rápidas funcionan aunque el agente esté caído.
- El token RO no permite escritura y las lecturas se auditan sin contenido.
- La cuota y el lock son correctos con dos workers.
- Reiniciar el ESP32 no rompe el chat.
- La UI muestra espera, error, cuota, historial y cancelación.
- La suite backend y E2E está en verde.
- La operación está documentada y hay un procedimiento de rollback.

## 7. Próximas versiones (backlog)

1. **B6.2 streaming**: sonda de `/messages`, decisión texto/progreso, SSE,
   feature flag y fallback.
2. **MCP** cuando el firmware lo soporte de forma estable.
3. Cancelación real si el firmware expone un método para detener el run.
4. Pruebas de 100k auditorías en staging y ajuste de retención.
5. Mejoras de datos demo si se necesita una presentación más limpia.

## 8. Control de cambios

Cualquier trabajo de B6.2 debe hacerse en una rama nueva, con feature flag
desactivado por defecto. No se debe reabrir el MVP ni activar streaming sin la
validación previa del contrato del firmware.
