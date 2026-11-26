# Checklist de cierre del MVP · Asistente IA

Fecha: ______ · Responsable: ______ · Versión/tag: ______

Marcar cada punto **después** de comprobarlo en el entorno de entrega. No cerrar
el MVP con puntos críticos abiertos.

## 1. Código y revisiones

- [ ] Las ramas del asistente están revisadas y fusionadas en la rama de release.
- [ ] No quedan cambios sin commit relacionados con el asistente.
- [ ] B6.2 está documentada como diferida, sin código a medias.
- [ ] OpenAPI está regenerado y sin diferencias.
- [ ] No se ha añadido ningún endpoint de escritura para el agente.

## 2. Pruebas automáticas

- [ ] Backend: `pytest --cov=app --cov-report=term --cov-fail-under=70` → verde.
- [ ] Cobertura registrada (objetivo ≥ 70 %).
- [ ] E2E: `npx playwright test` → verde.
- [ ] ESLint, Prettier, `check:css`, `check:html` y build → limpios.
- [ ] Accesibilidad: `ai.html` claro/oscuro sin violaciones graves.
- [ ] Prueba XSS de respuesta HTML → el texto no se ejecuta.
- [ ] Carga: `.\tasks.ps1 ai-loadtest -Concurrency 3` → 1×200 y 2×429.

Resultados:

| Prueba | Resultado | Fecha |
|---|---|---|
| Backend | | |
| E2E | | |
| axe IA | | |
| Carga/lock | | |

## 3. Configuración del backend

- [ ] `AI_AGENT_ENABLED=true`.
- [ ] `AI_AGENT_URL` apunta a la IP real del ESP32.
- [ ] `AI_BACKEND_URL` y `ALLOWED_HOSTS` incluyen la IP real del backend.
- [ ] `AI_AGENT_READ_TOKEN` configurado y rotado si fue necesario.
- [ ] `APP_TIMEZONE` correcto para la operación.
- [ ] Contenedores `app` y `watcher` Healthy.
- [ ] Esquema Alembic en `0014_ai_conversation_title`.
- [ ] `/health/ready` responde 200 desde la LAN.

## 4. Dispositivo y red

- [ ] El ESP32 tiene IP reservada o documentada.
- [ ] El ESP32 responde en `GET /api/status`.
- [ ] El backend ve el dispositivo (`/ai/status` online).
- [ ] El dispositivo ve el backend en `agent-read` (sin 400/401).
- [ ] `http_allowlist` incluye el host del backend.
- [ ] El ESP32 tiene Internet para el LLM (443/DNS/NTP).
- [ ] Firewall permite 8050 solo en la red local/VLAN.
- [ ] No hay port forwarding al ESP32 ni al backend.

## 5. Prompt o skill

- [ ] Se eligió modo HTTP clásico o skill Lua.
- [ ] Si es skill: `private/config.txt` existe y el prompt generado con
      `ai-prompt -Skill` **no contiene URL ni token**.
- [ ] Si es HTTP clásico: el prompt tiene la URL y el token actuales y se acepta
      el riesgo de exposición al LLM.
- [ ] El prompt/skill se probó con una pregunta simple y una de datos.
- [ ] La sesión antigua se rotó o se creó una conversación nueva.

## 6. Seguridad

- [ ] Token RO verificado: sin token → 401; token válido → 200.
- [ ] `agent-read` solo admite GET.
- [ ] `AI_AGENT_READ_ALLOWED_IPS` revisado (vacío o con el origen correcto).
- [ ] `AI_AGENT_TRUST_FORWARDED_FOR` solo si hay proxy de confianza.
- [ ] No se registran tokens, prompts ni contenido de chat en logs.
- [ ] Se revisó `docs/ai/SEGURIDAD.md` con el equipo.
- [ ] Se definió una fecha de rotación del token.

## 7. Datos y demo

- [ ] Se ejecutó `.\tasks.ps1 clean-alerts` (simulación).
- [ ] Se aplicó `.\tasks.ps1 clean-alerts -Apply` si había alertas de prueba.
- [ ] Las alertas activas restantes son las esperadas para la demo.
- [ ] La cuota diaria tiene margen suficiente.
- [ ] Se revisó que el historial y las conversaciones demo sean coherentes.

## 8. Respaldo y despliegue

- [ ] Respaldo de PostgreSQL realizado.
- [ ] Copia de `.env` guardada fuera del repositorio.
- [ ] Variables de entorno revisadas sin imprimir secretos.
- [ ] `docker compose up -d --force-recreate app watcher` ejecutado.
- [ ] Logs de arranque sin errores de configuración.

## 9. Smoke test posterior al despliegue

- [ ] Login admin.
- [ ] `/ai/status` online y `boot_id` visible.
- [ ] Chat simple responde.
- [ ] Pregunta de alertas devuelve datos reales.
- [ ] Respuesta rápida de flota responde sin cuota.
- [ ] Historial: abrir, renombrar y eliminar.
- [ ] Cancelar durante una consulta muestra el aviso.
- [ ] Reiniciar el ESP32 no rompe el chat.
- [ ] `last_agent_read_at` se actualiza después de una consulta.
- [ ] Cuota y métricas coherentes.

## 10. Release y comunicación

- [ ] Notas de release revisadas (`RELEASE-NOTES-MVP.md`).
- [ ] Limitaciones conocidas comunicadas a los usuarios.
- [ ] Se indicó que no hay streaming en esta versión.
- [ ] Tag de release creado (si el equipo lo usa).
- [ ] Backlog actualizado con B6.2 y MCP.
- [ ] Responsable de guardia/contacto definido.

## 11. Rollback

- [ ] Se conoce la versión anterior de la app.
- [ ] Se conserva el prompt/skill anterior.
- [ ] Se conserva el `.env` anterior.
- [ ] Si el agente falla, la app sigue funcionando con respuestas rápidas.
- [ ] Procedimiento de rollback probado o revisado.

## 12. Firma de cierre

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Desarrollo | | | |
| Operación | | | |
| Producto | | | |

**No cerrar el MVP si falla:** autenticación del agente, lock/cuota, chat
básico, historial, respaldo o rollback.
