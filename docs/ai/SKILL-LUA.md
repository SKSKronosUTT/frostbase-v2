# B5 fase 2 · sacar el token del prompt con una skill Lua

El objetivo es que el LLM **no vea** el token de solo lectura. En lugar de
incluir la URL y el token en el prompt, el agente activa una skill local y
ejecuta un script Lua que hace la petición HTTP por él.

## 1. Por qué Lua y no MCP

`cap_mcp_client` existe en el firmware, pero el cliente MCP del `edge_agent`
tiene un problema abierto: las herramientas se exponen al LLM pero la instancia
MCP no se inicializa
([issue upstream #129](https://github.com/espressif/esp-claw/issues/129)). No es
una base fiable para producción todavía.

La vía implementada es **Lua**:

- `cap_lua` ejecuta scripts locales.
- `lua_module_call_capability` permite llamar a `http_request` desde Lua.
- El token vive en un archivo del dispositivo (`private/config.txt`), no en el
  prompt.

## 2. Estructura de la skill

```text
esp-claw/skills/frostbase/
├── SKILL.md
├── scripts/frostbase_query.lua
└── private/
    └── config.example.txt
```

El ZIP generado incluye `private/config.txt` con la URL y el token actuales.
Ese archivo **no se versiona** (está en `.gitignore`).

## 3. Generar e instalar

```powershell
# Genera dist/frostbase-skill.zip con AI_BACKEND_URL y el token del .env
.\tasks.ps1 ai-skill
```

1. Descomprima el ZIP y, en ESP-Claw (con **Admin Mode** activo), suba su
   contenido a `/skills/frostbase` mediante el gestor de archivos. Deben quedar
   `SKILL.md`, `scripts/frostbase_query.lua` y `private/config.txt`.
2. Recargue el catálogo de skills (consola `skill --reload` o reinicie si el
   panel no lo refresca) y verifique que `cap_lua` y `cap_http_request` están
   habilitados y que `http_allowlist` incluye el host del backend
   (`192.168.0.210` o el que corresponda).
3. Pegue el prompt sin token:

```powershell
.\tasks.ps1 ai-prompt -Skill
```

4. Active la skill (`activate_skill` con `frostbase`) y pruebe:

```json
{
  "path": "{CUR_SKILL_DIR}/scripts/frostbase_query.lua",
  "args": {"endpoint": "fleet-summary"}
}
```

## 4. Endpoints permitidos por el script

`fleet-summary`, `alerts`, `alerts-today`, `truck-status`, `trips-active`,
`routes-today` y `thresholds`. El script valida el endpoint y el `truck_id`; no
acepta URLs arbitrarias.

## 5. Seguridad y límites

- El prompt ya **no contiene** URL ni token.
- El token sigue en el dispositivo, en `private/config.txt`; proteja el acceso
  físico y no suba ese archivo al repositorio.
- Si `cap_files` está habilitado, el LLM podría intentar leer `private/`. La
  skill se lo prohíbe, pero la mitigación fuerte es **no habilitar cap_files o
  el creador de skills** para usuarios no confiables.
- `cap_http_request` puede estar visible por defecto en `edge_agent`. Sin el
  token no puede autenticarse, pero conviene revisar los grupos visibles.
- El token sigue siendo rotable: si se filtra, cambie `AI_AGENT_READ_TOKEN`,
  regenere el ZIP y vuelva a instalarlo.
- Esto reduce la exposición; no es un sandbox contra un LLM comprometido.

## 6. Verificación

- `lua_run_script` devuelve JSON con `status: 200`.
- `last_agent_read_at` se actualiza tras la consulta.
- El prompt pegado en ESP-Claw no contiene `Bearer` ni el token.
- Una consulta de datos devuelve cifras reales del panel.

## 7. Reversa

Mantenga el prompt anterior con token hasta validar la skill. Si algo falla:

1. Desactive o elimine la skill.
2. Vuelva a pegar el prompt HTTP anterior.
3. Mantenga el mismo token o rótelo según el incidente.
