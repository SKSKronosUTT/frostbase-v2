# Plan de mejora frontend — FrostBase

**Fecha:** 2026-11-25
**Base:** `docs/auditoria-frontend.md` (36 hallazgos: 0 críticos · 5 altos · 21 medios · 10 bajos)
**Alcance:** `frontend/*.html`, `frontend/css/**`, `frontend/js/**` y `frontend/scripts/**`.

Este plan solo contiene acciones derivadas de hallazgos verificados. No incluye rediseño visual: la estética actual se conserva.

---

## Leyenda

- **Esfuerzo:** S < 2 h · M ½–1 día · L 2–3 días · XL > 3 días.
- **Impacto:** Alto / Medio / Bajo (sobre accesibilidad, rendimiento o mantenibilidad).
- **Riesgo de regresión visual:** probabilidad de que el diseño cambie sin querer y cómo mitigarlo.
- **Estado:** ✅ aplicado · ⬜ pendiente.

---

## Matriz impacto / esfuerzo

| Paso | Título | Hallazgos | Esfuerzo | Impacto | Depende de | Estado |
|---|---|---|---|---|---|---|
| 0.1 | Nombres accesibles y etiquetas | FE-003, FE-004 | S | Alto | — | ✅ |
| 0.2 | Contraste AA | FE-005 | S | Alto | — | ✅ |
| 0.3 | Drawer móvil accesible | FE-002 | M | Alto | — | ⬜ |
| 0.4 | Bug de cascada `.temp-card` | FE-019 | S | Medio | — | ✅ |
| 1.1 | Semántica de tablas y landmarks | FE-006, FE-008, FE-011 | S | Medio | — | ⬜ |
| 1.2 | Encabezados, `<main>` y skip link | FE-007, FE-014 | S | Medio | — | ⬜ |
| 1.3 | Foco visible en el asistente | FE-015 | S | Medio | — | ⬜ |
| 1.4 | `prefers-reduced-motion` | FE-016 | S | Medio | — | ⬜ |
| 1.5 | Errores de formulario y toasts | FE-012, FE-013, FE-017 | M | Medio | 0.1 | ⬜ |
| 1.6 | Patrón de tabs accesible | FE-009 | M | Medio | — | ⬜ |
| 1.7 | Mapas sin `role="application"` | FE-010 | M | Medio | — | ⬜ |
| 2.1 | Fusionar la cascada «Consolidado» | FE-018, FE-034 | L | Alto | 0.4 | ⬜ |
| 2.2 | Tokens de tipografía y espaciado | FE-021, FE-022, FE-023 | L | Alto | 2.1 | ⬜ |
| 2.3 | Breakpoints unificados mobile-first | FE-020 | M | Medio | 2.1 | ⬜ |
| 2.4 | Limpieza de CSS muerto | FE-025, FE-026, FE-027 | S | Bajo | 2.1 | ⬜ |
| 2.5 | Parciales de `<head>` y sidebar estática | FE-001, FE-033 | L | Medio | 2.1 | ⬜ |
| 2.6 | Pesos tipográficos coherentes | FE-024 | S | Bajo | 2.2 | ⬜ |
| 3.1 | Linters y validación en CI | FE-034, FE-036 | M | Alto | 2.1 | ⬜ |
| 3.2 | Rendimiento de carga | FE-028, FE-030, FE-031, FE-032 | M | Medio | 2.5 | ⬜ |
| 3.3 | `100dvh` y Safari | FE-029 | S | Bajo | — | ⬜ |
| 3.4 | Ampliar suite a11y | FE-036 | M | Medio | 1.x | ⬜ |
| 3.5 | Guía de estilos y README frontend | — | M | Medio | 2.x | ⬜ |
| 4.1 | Container queries y detalles UI | — | M | Bajo | 2.3 | ⬜ |
| 4.2 | Tema automático del sistema | — | S | Bajo | 0.2 | ⬜ |

**Lectura rápida:** 0.1, 0.2, 0.4 y todo el bloque 1.x son «quick wins» (S, alto/medio impacto). La Fase 2 es donde está el verdadero retorno a medio plazo, con 2.1 como prerrequisito.

---

# Fase 0 · Correcciones urgentes

## 0.1 · Nombres accesibles y etiquetas — ✅ Aplicado

**Hallazgos:** FE-003 (botones solo-icono), FE-004 (buscadores sin etiqueta).

**Tareas realizadas**

1. `driver.html`: añadido `aria-label="Cambiar contraseña"` y `aria-label="Cerrar sesión"` a los dos botones de icono, con `aria-hidden="true"` en los `<i>`.
2. `trucks.html`: `aria-label="Buscar camiones"` en `#truckSearch` y `aria-label="Buscar dispositivos IoT"` en `#deviceSearch`.
3. `routes.html`: `aria-label="Buscar ruta"` en `#routeSearch`.
4. Criterio unificado con `drivers.html` (que ya usaba `aria-label`) y con `ai.html` (que usa `.sr-only`).

**Archivos:** `frontend/driver.html`, `frontend/trucks.html`, `frontend/routes.html`.

**Esfuerzo:** S · **Impacto:** Alto · **Dependencias:** ninguna.
**Riesgo de regresión visual:** nulo (solo atributos ARIA).

**Criterios de aceptación**

- `html-validate` sin errores `text-content` en `driver.html`.
- Cada input de búsqueda tiene nombre accesible calculado distinto del `placeholder`.
- axe sin violaciones `button-name` ni `label` en `trucks.html`, `routes.html`, `driver.html`.

**Verificación**

```bash
npx html-validate "frontend/driver.html" "frontend/trucks.html" "frontend/routes.html"
cd frontend && npx playwright test tests/e2e/accessibility.spec.js
```

**Resultado:** los 2 errores `text-content` desaparecieron (242 → 240 problemas totales, 44 → 42 reales). El build sigue pasando.

---

## 0.2 · Contraste AA — ✅ Aplicado

**Hallazgos:** FE-005.

**Tareas realizadas**

1. `tokens.css`: `--text-soft` pasa de `#5b7288` (4.36:1 sobre `--bg`) a `#50687e` (**5.07:1** sobre `--bg`, 5.51:1 sobre `--surface-soft`).
2. `tokens.css`: nuevo token `--offline-text` (`#4f6479` en claro, `#9fb6c8` en oscuro) para texto sobre fondos `--offline-soft`.
3. `components.css`: `.badge--muted` usa `--offline-text` en sus dos declaraciones → **5.11:1** en claro y **6.00:1** en oscuro.
4. `login.css`: `.login-brand__footer` pasa de `rgba(255,255,255,.6)` (4.03:1) a `rgba(255,255,255,.82)` (**6.15:1**).
5. Comprobado que `.badge--danger` ya usaba su valor final `#a8232f` (**5.84:1**) y no requería cambio. `.badge--success` (5.18) y `.badge--warning` (5.10) también pasaban.

**Archivos:** `frontend/css/tokens.css`, `frontend/css/components.css`, `frontend/css/pages/login.css`.

**Esfuerzo:** S · **Impacto:** Alto · **Dependencias:** ninguna.
**Riesgo de regresión visual:** bajo; los textos secundarios se ven ligeramente más oscuros y los badges «muted» más legibles. Mitigación: comparar `dashboard`, `driver`, `login` y `ai` en ambos temas a 1440 px.

**Criterios de aceptación**

- Todo texto normal ≥ 4.5:1; elementos de interfaz y texto grande ≥ 3:1.
- `--text-soft` y `.badge--muted` cumplen en claro y oscuro.
- El tema oscuro no pierde contraste al cambiar `--offline-text`.

**Verificación**

```bash
# cálculo de ratios con el script de contraste usado en la auditoría
node contrast-check.js   # o revisión con el inspector de Chrome
cd frontend && npx playwright test tests/e2e/accessibility.spec.js
```

---

## 0.3 · Drawer móvil accesible — ⬜ Pendiente

**Hallazgos:** FE-002.

**Tareas concretas**

1. En `sidebar.js`, crear el botón antes de `<main>` (o dentro del `.page-header`), no al final del `<body>`.
2. Añadir `aria-expanded` (alternando `true`/`false`) y `aria-controls="sidebar"`.
3. Al abrir: mover el foco al primer enlace del menú, marcar `aria-expanded="true"`, aplicar `overflow: hidden` a `body` y `inert` al contenido principal.
4. Al cerrar (botón, overlay, `Escape` o clic en un enlace): devolver el foco al botón y restaurar el scroll.
5. En `layout.css`, para móvil cerrado: añadir `visibility: hidden` y `transition` sobre `visibility` además de `transform`, para sacar los enlaces del orden de tabulación.
6. Añadir `aria-label` al `<aside>` (`Navegación principal`) mientras no se migre a HTML estático (2.5).

**Archivos:** `frontend/js/components/sidebar.js`, `frontend/css/layout.css`.

**Esfuerzo:** M · **Impacto:** Alto · **Dependencias:** ninguna.
**Riesgo de regresión visual:** medio (interacción móvil). Mitigación: probar 360/480/900 px con teclado y con un lector (NVDA o VoiceOver).

**Criterios de aceptación**

- El toggle es el primer elemento tabulable tras el skip link.
- `aria-expanded` refleja el estado real.
- Con el menú cerrado no se puede tabular a ningún enlace del sidebar.
- El fondo no hace scroll con el menú abierto; `Escape` cierra y devuelve el foco.

**Verificación:** Playwright con viewport 375×812 (`expect(toggle).toHaveAttribute('aria-expanded','true')`, tabulación y `Escape`); revisión manual en DevTools (emulación móvil).

---

## 0.4 · Bug de cascada en `.temp-card` — ✅ Aplicado

**Hallazgos:** FE-019 (y el mismo patrón afectaba a `.map--dashboard`).

**Tareas realizadas**

1. Se movió el bloque `@media (max-width: 640px)` de `dashboard.css` desde la parte superior (líneas 55-67) al final de la hoja.
2. `.temp-card` pasa a declarar `flex: 0 0 170px` dentro de la media query, después de la regla base de 188 px.
3. `.map--dashboard` recupera su altura de 340 px en móvil (antes ganaba la base de 430 px).

**Archivos:** `frontend/css/pages/dashboard.css`.

**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo de regresión visual:** bajo y acotado a ≤640 px. Mitigación: comprobar el carrusel de temperaturas y el mapa a 360, 390 y 640 px.

**Criterios de aceptación**

- A 375 px, `getComputedStyle(.temp-card).flexBasis === "170px"`.
- A 375 px, la altura del mapa es 340 px; a 641 px, 430 px.
- El carrusel sigue haciendo scroll horizontal sin desbordar la tarjeta.

**Verificación:** DevTools responsive a 360/390/640/641 px o Playwright con `page.setViewportSize`.

---

# Fase 1 · Quick wins

## 1.1 · Semántica de tablas y landmarks — ⬜

**Hallazgos:** FE-006, FE-008, FE-011.

**Tareas**

1. Añadir `scope="col"` a todos los `<th>` de `alerts.html`, `drivers.html`, `trucks.html` (2 tablas) y `truck-detail.html`.
2. Sustituir el `<th aria-label="Acciones"></th>` por `<th scope="col"><span class="sr-only">Acciones</span></th>`.
3. Nombrar los `aside` complementarios (`aria-label="Panel lateral de estado"` en `dashboard.html:113`, `aria-label="Lista de rutas"` en `routes.html:48`) y convertir `routes.html:40` en `<section>`.
4. Cambiar `ai.html:148` por `role="group" aria-label="Consultas por camión"`.

**Archivos:** `alerts.html`, `drivers.html`, `trucks.html`, `truck-detail.html`, `dashboard.html`, `routes.html`, `ai.html`.

**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo de regresión visual:** nulo.

**Aceptación:** 0 errores `wcag/h63`, `unique-landmark` y `aria-label-misuse`; axe `td-headers-attr`/`th-has-data-cells` sin avisos.

**Verificación:** `npx html-validate "frontend/*.html"` + axe en las 7 páginas.

---

## 1.2 · Encabezados, `<main>` y skip link — ⬜

**Hallazgos:** FE-007, FE-014.

**Tareas**

1. Añadir un `h1` a `driver.html` (puede ser `.sr-only`: «Portal del conductor») y a `index.html` (`.sr-only`: «FrostBase»).
2. Subir los `<h3>` de `settings.html` (líneas 38, 64, 90, 106) a `<h2>`.
3. Envolver el contenido de `login.html` e `index.html` en `<main>`.
4. Insertar en las 12 páginas un skip link como primer elemento del `<body>`:

```html
<a class="skip-link" href="#main">Saltar al contenido</a>
```

5. Añadir `id="main"` al `<main>` de cada página y estilos:

```css
.skip-link {
  position: absolute;
  left: 8px;
  top: -60px;
  z-index: 2000;
  padding: 10px 14px;
  background: var(--surface);
  border: 2px solid var(--border-ink);
  color: var(--text);
}
.skip-link:focus { top: 8px; }
```

**Archivos:** las 12 `.html` y `frontend/css/base.css` (o `components.css`).

**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo de regresión visual:** bajo; el skip link solo aparece al enfocar. Verificar que no tapa el logo en login.

**Aceptación:** un solo `h1` por página, sin saltos de nivel; todas las páginas tienen `<main>`; el skip link aparece con Tab y lleva el foco al contenido.

**Verificación:** axe (`heading-order`, `landmark-one-main`, `region`) + recorrido manual con Tab.

---

## 1.3 · Foco visible en el asistente — ⬜

**Hallazgos:** FE-015.

**Tareas:** en `ai.css:322-325` y `484-487`, sustituir `outline: none` por:

```css
outline: 2px solid var(--accent-mid);
outline-offset: 2px;
```

**Archivos:** `frontend/css/pages/ai.css`.
**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo:** bajo (solo estado de foco).

**Aceptación:** el foco del selector de camión y del textarea es perceptible con teclado y no depende solo del color del borde.

**Verificación:** recorrido con Tab en `ai.html`, captura de pantalla del estado `:focus-visible`.

---

## 1.4 · `prefers-reduced-motion` — ⬜

**Hallazgos:** FE-016.

**Tareas:** añadir al final de `base.css`:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

**Archivos:** `frontend/css/base.css`.
**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo:** bajo; los spinners dejarán de girar con la preferencia activa (comportamiento esperado).

**Aceptación:** con «reducir movimiento» activado en el SO, no hay animaciones de entrada ni transiciones largas; el spinner no gira pero sigue visible.

**Verificación:** DevTools → Rendering → `prefers-reduced-motion: reduce`; revisar `dashboard`, modal y dropdown.

---

## 1.5 · Errores de formulario y toasts — ⬜

**Hallazgos:** FE-012, FE-013, FE-017.

**Tareas**

1. En `login.js`, `settings.js` y `drivers.js`: al fallar la validación, marcar el campo con `aria-invalid="true"`, añadir `aria-describedby` a un `<p class="field-error" id="<campo>-error" role="alert">` y enfocar el primer campo inválido.
2. Limpiar `aria-invalid` y el mensaje al corregir el valor.
3. En `notifications.js`: usar `role="alert"` para `type === "error"`, pausar el temporizador en `focusin` (además de `mouseenter`) y no autodescartar errores o ampliar su duración a 10 s.
4. En `feedback.js`: `aria-busy` mientras carga y un `role="status"` con el resultado (nº de filas o error).

**Archivos:** `frontend/js/pages/login.js`, `settings.js`, `drivers.js`, `trucks.js`; `frontend/js/core/notifications.js`; `frontend/js/components/feedback.js`; `frontend/css/components.css` (estilo `.field-error`).

**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** 0.1.
**Riesgo de regresión visual:** bajo; el mensaje inline cambia la altura del formulario. Reservar espacio o usar `min-height` para evitar saltos.

**Aceptación:** al enviar el login vacío, el foco va al campo, se anuncia el error y el campo queda marcado; el toast de error se anuncia como alerta y se puede pausar con teclado.

**Verificación:** axe en login/settings/drivers; prueba manual con NVDA; Playwright `critical-flows.spec.js`.

---

## 1.6 · Patrón de tabs accesible — ⬜

**Hallazgos:** FE-009.

**Tareas**

1. En `trucks.html`: añadir `id` a los botones (`tab-trucks`, `tab-devices`), `aria-controls` hacia los paneles, `role="tabpanel"` y `aria-labelledby` en `#trucksPanel` y `#devicesPanel`, y `tabindex="-1"` en el panel inactivo.
2. En `trucks.js`: manejar `ArrowLeft`, `ArrowRight`, `Home` y `End` moviendo foco y activando el tab; mantener `aria-selected` sincronizado.
3. Alternativa más simple si no se quiere mantener el patrón: dos botones con `aria-pressed` y paneles con `hidden`.

**Archivos:** `frontend/trucks.html`, `frontend/js/pages/trucks.js`.
**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo:** bajo, pero toca lógica de carga diferida de dispositivos (`switchTab`). Mitigación: probar que `devicesLoaded` sigue funcionando.

**Aceptación:** con foco en un tab, las flechas cambian de pestaña y de panel; el lector anuncia «pestaña 2 de 2, seleccionada».

**Verificación:** manual con teclado + axe (`aria-required-children`, `aria-required-parent`).

---

## 1.7 · Mapas sin `role="application"` — ⬜

**Hallazgos:** FE-010.

**Tareas**

1. Eliminar `role="application"` de los 4 mapas y corregir el `aria-label` copiado de `route-detail.html:52` («Mapa de la ruta»).
2. Añadir un resumen textual (`<p class="sr-only" id="map-summary">`) actualizado por JS con nº de unidades y ruta, y enlazarlo con `aria-describedby`.
3. Mantener el mapa como decorativo/informativo y ofrecer la información equivalente en la tabla o lista ya existente.

**Archivos:** `dashboard.html`, `routes.html`, `route-detail.html`, `truck-detail.html` y sus JS (`dashboard.js`, `routes.js`, `route-detail.js`, `truck-detail.js`).

**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo:** bajo; no cambia el render.

**Aceptación:** el lector de pantalla anuncia el resumen del mapa y no queda atrapado en modo aplicación.

**Verificación:** navegación con lector + inspección de accesibilidad de Chrome.

---

# Fase 2 · Mejoras estructurales

## 2.1 · Fusionar la cascada «Consolidado» — ⬜

**Hallazgos:** FE-018, FE-034.

**Tareas**

1. Por cada hoja con bloque consolidado (`base`, `components`, `layout`, `alerts`, `dashboard`, `login`, `routes`, `settings`, `truck-detail`), fusionar la regla duplicada con la original conservando **el valor final** que hoy gana en cascada.
2. Resolver manualmente los casos donde una media query posterior también participa (p. ej. `.main`, `.sidebar`, `.login-shell`, `.temp-card`).
3. Eliminar los comentarios `Consolidado desde bauhaus.css` una vez fusionado.
4. Un commit por archivo, con capturas antes/después.
5. Meta: `no-duplicate-selectors` = 0.

**Archivos:** las 9 hojas citadas.
**Esfuerzo:** L · **Impacto:** Alto · **Dependencias:** 0.4.
**Riesgo de regresión visual:** **alto** (es el paso más delicado). Mitigación obligatoria: rama propia, capturas de las 12 páginas × 6 breakpoints × 2 temas antes y después, y revisión página por página. Si una hoja no se puede fusionar con seguridad, se deja para un commit posterior.

**Aceptación**

- 0 selectores duplicados (`stylelint no-duplicate-selectors`).
- Diff visual nulo respecto a la rama base (capturas comparadas).
- El CSS resultante mantiene el orden: base → componentes → layout → página → responsive.

**Verificación:** `npx stylelint "frontend/css/**/*.css"` + comparación de capturas + `npm run build`.

---

## 2.2 · Tokens de tipografía y espaciado — ⬜

**Hallazgos:** FE-021, FE-022, FE-023.

**Tareas**

1. Añadir a `tokens.css` una escala de 7–8 pasos (`--text-xs` 11px, `--text-sm` 12px, `--text-md` 13px, `--text-base` 14px, `--text-lg` 16px, `--text-xl` 20px, `--text-2xl` 26px, `--text-3xl` 32px) y otra de espaciado base 4 (`--space-1` … `--space-8`).
2. Sustituir los 30 tamaños sueltos por los tokens; resolver los `.5` px a un paso adyacente.
3. Crear tokens semánticos para los hex repetidos (`--state-success-text`, `--state-warning-text`, `--color-on-accent`, `--color-hover-primary`).
4. Eliminar los hex que pertenecían a la primera generación.

**Archivos:** `tokens.css` y todas las hojas de `css/` y `css/pages/`.
**Esfuerzo:** L · **Impacto:** Alto · **Dependencias:** 2.1.
**Riesgo de regresión visual:** medio (0,5–1 px de diferencia en textos). Mitigación: revisar jerarquía en `dashboard`, `trucks` y `settings`; no tocar tamaños de `clamp()` sin captura.

**Aceptación:** ≤ 8 tamaños de fuente distintos; 0 hex fuera de `tokens.css`; escala documentada.

**Verificación:** búsqueda de `font-size:` con valores literales y de `#[0-9a-f]` fuera de tokens; revisión visual.

---

## 2.3 · Breakpoints unificados mobile-first — ⬜

**Hallazgos:** FE-020.

**Tareas**

1. Definir 4 cortes: `480`, `768`, `1024`, `1280`.
2. Convertir las media queries `max-width` a `min-width` por hoja, empezando por `layout.css` y `components.css`.
3. Documentar el mapa de breakpoints en la guía de estilos (3.5).

**Archivos:** todas las hojas de `css/` y `css/pages/`.
**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** 2.1.
**Riesgo de regresión visual:** alto si se convierte a ciegas. Mitigación: una hoja por commit y capturas en los 4 cortes + 360/390 px.

**Aceptación:** solo 4 breakpoints en el proyecto, todos `min-width`; ninguna página se rompe entre 320 y 1920 px.

**Verificación:** revisión en 360, 390, 480, 768, 1024, 1280, 1440, 1920 px; búsqueda de `@media (max-width`.

---

## 2.4 · Limpieza de CSS muerto — ⬜

**Hallazgos:** FE-025, FE-026, FE-027.

**Tareas**

1. Eliminar `.btn--secondary`, `.btn--danger-soft`, `.card__footer`, `.card__section`, `.two-column`, `.text-success`, `.text-warning`, `.mono`, `.fade-in`, `.spinner--light`, `.divider`, `.kpi-card--clickable`, `.info-tile*`, `.toggle-*`, `.map-supply`, `.detail-actions`, `.truck-status-select`.
2. Eliminar `.brand-name accent`.
3. Decidir sobre `is-ready`: eliminarlo o implementar el estado de carga.
4. Repetir la búsqueda global antes de borrar (las plantillas JS pueden construir clases por concatenación).

**Archivos:** `base.css`, `components.css`, `layout.css`, hojas de página; `app.js`.
**Esfuerzo:** S · **Impacto:** Bajo · **Dependencias:** 2.1.
**Riesgo:** bajo; verificar con búsqueda literal y prueba de las 12 páginas.

**Aceptación:** 0 coincidencias de las clases eliminadas en HTML/JS; build y tests verdes.

**Verificación:** `grep` global + Playwright smoke.

---

## 2.5 · Parciales de `<head>` y sidebar estática — ⬜

**Hallazgos:** FE-001, FE-033.

**Tareas**

1. Extraer el bloque `<head>` (metas, preload, hojas, theme-boot) a un parcial que consuma el build (11ty, Vite o una función `include()` en `scripts/build.mjs`).
2. Renderizar el sidebar y el nav en el HTML de cada página (o generarlo en el build), dejando JS solo para el estado activo y el drawer.
3. Eliminar la duplicación de 16 líneas × 12 archivos.

**Archivos:** las 12 `.html`, `frontend/scripts/build.mjs`, `frontend/js/components/sidebar.js`.
**Esfuerzo:** L · **Impacto:** Medio · **Dependencias:** 2.1.
**Riesgo:** medio (el build cambia). Mitigación: comparar HTML generado con el actual; mantener el mismo orden de hojas.

**Aceptación:** una sola fuente para el `<head>`; el HTML servido incluye la navegación sin JS; el build produce el mismo conjunto de assets.

**Verificación:** `npm run build` + diff del HTML generado + navegación con JS deshabilitado.

---

## 2.6 · Pesos tipográficos coherentes — ⬜

**Hallazgos:** FE-024.

**Tareas:** bajar los `font-weight: 800/900` a 700 (o cargar el eje completo si se quiere mantener el contraste actual). Ajustar `base.css:42-49`, `components.css:1665-1669`, `.btn` y los badges.

**Archivos:** `base.css`, `components.css`, `fonts.css` (si se opta por el eje completo).
**Esfuerzo:** S · **Impacto:** Bajo · **Dependencias:** 2.2.
**Riesgo:** visible en titulares; comparar capturas. Si el diseño exige 900, cargar el eje variable completo (verificar peso del archivo).

**Aceptación:** ningún `font-weight` fuera del rango declarado en `@font-face`; los titulares mantienen el aspecto acordado.

**Verificación:** `grep font-weight` + capturas de `login`, `dashboard` y `driver`.

---

# Fase 3 · Calidad sostenible

## 3.1 · Linters y validación en CI — ⬜

**Hallazgos:** FE-034, FE-036.

**Tareas**

1. Añadir `stylelint` + `stylelint-config-standard` como `devDependency` y un `.stylelintrc` con `no-duplicate-selectors`, `declaration-block-no-duplicate-properties`, `shorthand-property-no-redundant-values`, `custom-property-pattern`.
2. Añadir `html-validate` con `void-style: "selfclosing"` y `doctype-style` configurados para no generar 198 falsos positivos, y activar `no-dup-id`.
3. Enganchar ambos a `.pre-commit-config.yaml` y a GitHub Actions, junto con `npm run build` y Playwright.
4. Sustituir `check-css.mjs` por `stylelint` (o ampliarlo para duplicados intra-archivo).

**Archivos:** `frontend/package.json`, `.stylelintrc*`, `.htmlvalidate.json`, `.github/workflows/*`, `.pre-commit-config.yaml`, `frontend/scripts/check-css.mjs`.
**Esfuerzo:** M · **Impacto:** Alto · **Dependencias:** 2.1.
**Riesgo:** bajo; puede requerir silenciar reglas de estilo heredadas (documentar cada excepción).

**Aceptación:** CI falla ante un selector duplicado o un `<th>` sin `scope`; `npm run lint` disponible en local.

**Verificación:** PR de prueba que introduzca una violación y comprobar que el job falla.

---

## 3.2 · Rendimiento de carga — ⬜

**Hallazgos:** FE-028, FE-030, FE-031, FE-032.

**Tareas**

1. Inline de `theme-boot.js` (11 líneas) con hash en la CSP, para eliminar la petición bloqueante.
2. CSS crítico inline para `login` y `dashboard`; `preload` de la hoja de página.
3. Sustituir `logo.png` por SVG + `favicon-32.png` + `apple-touch-icon`.
4. Unificar la ruta de la fuente en `fonts.css` (relativa o reescrita en build).
5. Evaluar un subset real de FontAwesome o pasar los iconos de navegación a SVG inline.

**Archivos:** `scripts/build.mjs`, todas las `.html`, `assets/`, `css/fonts.css`, `backend/app/main.py` (CSP con hash).
**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** 2.5.
**Riesgo:** medio (CSP y build). Mitigación: probar `csp.spec.js` y comparar el HTML generado.

**Aceptación:** 0 peticiones bloqueantes distintas del CSS crítico; LCP < 2,5 s en 4G simulada; CLS < 0,1; CSP sin violaciones.

**Verificación:** Lighthouse (mobile y desktop), pestaña Network, `tests/e2e/csp.spec.js`.

---

## 3.3 · `100dvh` y Safari — ⬜

**Hallazgos:** FE-029.

**Tareas:** sustituir `100vh` por `100dvh` con fallback en `base.css:18`, `components.css:1277,1619`, `layout.css:2`, `ai.css:6,235`, `driver.css:4`, `index.css:6`, `login.css:2`.

**Archivos:** las hojas citadas.
**Esfuerzo:** S · **Impacto:** Bajo · **Dependencias:** ninguna.
**Riesgo:** bajo; verificar en Safari iOS o en el simulador de responsive de Chrome.

**Aceptación:** los modales caben en el viewport visible y el login no genera scroll vertical innecesario en iOS.

**Verificación:** Safari iOS (o BrowserStack) en login, dashboard y un modal.

---

## 3.4 · Ampliar la suite de accesibilidad — ⬜

**Hallazgos:** FE-036.

**Tareas:** incluir las 12 páginas y ambos temas; bajar el umbral a `moderate`; añadir comprobaciones específicas de foco (skip link, drawer, tabs) y de errores de formulario.

**Archivos:** `frontend/tests/e2e/accessibility.spec.js`.
**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** 1.x.
**Riesgo:** bajo; puede revelar violaciones nuevas (esperado).

**Aceptación:** la suite cubre todas las páginas y falla con violaciones `moderate` o superiores.

**Verificación:** `npx playwright test tests/e2e/accessibility.spec.js`.

---

## 3.5 · Guía de estilos y README frontend — ⬜

**Tareas:** documentar tokens, escala tipográfica, espaciado, breakpoints, convención BEM, estados de componentes (hover/focus/active/disabled/error), checklist de PR y comandos de validación.

**Archivos:** `docs/guia-estilos.md` (nuevo), `frontend/README.md` (nuevo o ampliación del raíz).
**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** 2.x.

**Aceptación:** un desarrollador nuevo puede crear una página siguiendo la guía sin consultar el CSS existente.

---

# Fase 4 · Mejoras opcionales

## 4.1 · Container queries y detalles UI — ⬜

Aplicar `container-type: inline-size` a las tarjetas y adaptar `.kpi-grid`/`.temp-card` al ancho de su contenedor en lugar del viewport; cabeceras de tabla sticky; `aspect-ratio` en mapas y medios; iconografía SVG inline.

**Esfuerzo:** M · **Impacto:** Bajo · **Dependencias:** 2.3.

## 4.2 · Tema automático del sistema — ⬜

Usar `prefers-color-scheme` como valor inicial cuando no haya preferencia guardada, manteniendo el toggle manual y la persistencia actual (`theme.js`).

**Esfuerzo:** S · **Impacto:** Bajo · **Dependencias:** 0.2.

---

# Estrategia de implementación segura

1. **Rama nueva** desde `devolp`:
   ```bash
   git switch devolp
   git switch -c audit/frontend-hardening
   ```
2. **Un commit por paso**, con el ID en el mensaje:
   ```bash
   git commit -m "fix(a11y): nombres accesibles y etiquetas de búsqueda (FE-003, FE-004)"
   ```
3. **Antes de cada commit**: comprobar las 12 páginas en **360 / 480 / 768 / 1024 / 1440 / 1920 px**, en tema claro y oscuro. Para los pasos de CSS estructural (2.x), guardar capturas antes/después en `frontend/test-results/visual/` (ignorado por git).
4. **Después de cada paso**: `npm run build`, `html-validate`, `stylelint` y, si el stack está levantado, `playwright test`.
5. **No mezclar** pasos de la Fase 2 con cambios funcionales ni con la Fase 3.
6. Si un paso de la Fase 2 no se puede cerrar sin diff visual, **revertir ese archivo** y dejarlo documentado; no forzar.

---

# Métricas objetivo

| Métrica | Antes | Objetivo |
|---|---|---|
| `html-validate` (errores reales) | 44 (42 tras 0.1) | **0** |
| `stylelint no-duplicate-selectors` | 130 | **0** |
| axe (`wcag2a/aa`, incl. moderate) | Sin medir (≥2 probables) | **0 violaciones** en 12 páginas × 2 temas |
| Lighthouse accesibilidad (login, dashboard, trucks) | Sin medir | **≥ 95** |
| Contraste | 4 fallos AA | **100 %** textos ≥ 4.5:1 y UI ≥ 3:1 |
| `!important` | 3 | **≤ 1** (solo `.hidden`) |
| Tamaños de fuente distintos | 30 | **≤ 8** |
| Breakpoints | 13 | **4** |
| Clases CSS muertas | ≈17 | **0** |
| CSS por página | 1 petición (build) | **1 petición ≤ 45 KB** |
| `100vh` en layout | 9 | **0** (sustituido por `dvh`) |
| Suite Playwright a11y | 7 páginas, serious/critical | **12 páginas, moderate** |
| CLS / LCP | Sin medir | **< 0,1 / < 2,5 s** en 4G |

---

# Verificación global (comandos)

```bash
# HTML
npx html-validate "frontend/*.html"

# CSS (sin instalar en el proyecto)
npx --package stylelint@16 --package stylelint-config-standard@36 \
  stylelint "frontend/css/**/*.css"

# Build
cd frontend && npm run build

# Tests (requiere stack levantado)
cd frontend && npx playwright test

# Lighthouse
npx lighthouse http://localhost:8050/dashboard.html \
  --only-categories=accessibility,performance --preset=desktop
```

---

# Registro de ejecución

| Fecha | Paso | Archivos | Resultado |
|---|---|---|---|
| 2026-11-25 | 0.1 | `driver.html`, `trucks.html`, `routes.html` | `text-content` eliminado; inputs con nombre accesible |
| 2026-11-25 | 0.2 | `tokens.css`, `components.css`, `pages/login.css` | Ratios AA corregidos (5.07 / 5.11 / 6.00 / 6.15) |
| 2026-11-25 | 0.4 | `pages/dashboard.css` | Media query al final; 170 px y 340 px aplican en móvil |

**Próximo paso recomendado:** **0.3 · Drawer móvil accesible**. Es el último hallazgo de severidad Alta de la Fase 0, tiene esfuerzo M y no depende de la refactorización de cascada.
