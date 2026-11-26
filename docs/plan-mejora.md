# Plan de mejora frontend — FrostBase

**Fecha:** 2026-11-25
**Base:** `docs/auditoria-frontend.md` (38 hallazgos: 0 críticos · 5 altos · 23 medios · 10 bajos)
**Alcance:** `frontend/*.html`, `frontend/css/**`, `frontend/js/**` y `frontend/scripts/**`.

Este plan solo contiene acciones derivadas de hallazgos verificados. No incluye rediseño visual: la estética actual se conserva.

---

## Leyenda

- **Esfuerzo:** S < 2 h · M ½–1 día · L 2–3 días · XL > 3 días.
- **Impacto:** Alto / Medio / Bajo (sobre accesibilidad, rendimiento o mantenibilidad).
- **Riesgo de regresión visual:** probabilidad de que el diseño cambie sin querer y cómo mitigarlo.
- **Estado:** ✅ aplicado · 🟡 parcial · ⬜ pendiente.

---

## Matriz impacto / esfuerzo

| Paso | Título | Hallazgos | Esfuerzo | Impacto | Depende de | Estado |
|---|---|---|---|---|---|---|
| 0.1 | Nombres accesibles y etiquetas | FE-003, FE-004 | S | Alto | — | ✅ |
| 0.2 | Contraste AA | FE-005 | S | Alto | — | ✅ |
| 0.3 | Drawer móvil accesible | FE-002 | M | Alto | — | ✅ |
| 0.4 | Bug de cascada `.temp-card` | FE-019 | S | Medio | — | ✅ |
| 1.1 | Semántica de tablas y landmarks | FE-006, FE-008, FE-011 | S | Medio | — | ✅ |
| 1.2 | Encabezados, `<main>` y skip link | FE-007, FE-014 | S | Medio | — | ✅ |
| 1.3 | Foco visible en el asistente | FE-015 | S | Medio | — | ✅ |
| 1.4 | `prefers-reduced-motion` | FE-016 | S | Medio | — | ✅ |
| 1.5 | Errores de formulario y toasts | FE-012, FE-013, FE-017 | M | Medio | 0.1 | ✅ |
| 1.6 | Patrón de tabs accesible | FE-009 | M | Medio | — | ✅ |
| 1.7 | Mapas sin `role="application"` | FE-010 | M | Medio | — | ✅ |
| 1.8 | Rol de región en mapas interactivos | FE-037 | S | Medio | 1.7 | ✅ |
| 1.9 | Tablas desplazables accesibles | FE-038 | S | Medio | 1.8 | ✅ |
| 2.1 | Fusionar la cascada «Consolidado» | FE-018, FE-034 | L | Alto | 0.4 | ✅ |
| 2.2 | Tokens de tipografía y espaciado | FE-021, FE-022, FE-023 | L | Alto | 2.1 | ✅ |
| 2.3 | Breakpoints unificados mobile-first | FE-020 | M | Medio | 2.1 | 🟡 parcial |
| 2.4 | Limpieza de CSS muerto | FE-025, FE-026, FE-027 | S | Bajo | 2.1 | ✅ |
| 2.5 | Parciales de `<head>` y sidebar estática | FE-001, FE-033 | L | Medio | 2.1 | ✅ |
| 2.6 | Pesos tipográficos coherentes | FE-024 | S | Bajo | 2.2 | ✅ |
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

## 0.3 · Drawer móvil accesible — ✅ Aplicado

**Hallazgos:** FE-002.

**Tareas realizadas**

1. En `sidebar.js`, el botón se inserta como primer elemento del `<body>` (`body.prepend`), antes de `<main>`, con `aria-controls="sidebar"` y `aria-expanded="false"` inicial.
2. Al abrir: `aria-expanded="true"`, etiqueta «Cerrar menú de navegación», icono `fa-xmark`, foco al enlace activo, `inert` en `.main` y `overflow: hidden` en `body`. El botón se recoloca dentro del drawer (202 px) para no tapar el logotipo.
3. Al cerrar (botón, overlay, `Escape` o clic en un enlace): `aria-expanded="false"`, foco de vuelta al botón, `inert` retirado del contenido y scroll restaurado.
4. Trampa de foco con `Tab`/`Shift+Tab` entre el botón y los controles del menú.
5. En `layout.css`, el sidebar cerrado en móvil usa `visibility: hidden` con salida animada de 220 ms, `overscroll-behavior: contain` y `body.sidebar-open { overflow: hidden }`.
6. En JS, el sidebar cerrado recibe `inert` en móvil (y lo pierde al abrir o al pasar a escritorio), de modo que sus enlaces no son tabulables aunque la animación de salida siga en curso.
7. Al cambiar a escritorio con el menú abierto, se cierra, se retira `inert` del contenido y se restaura el estado del sidebar.

> El `aria-label` del `<aside>` se pospone a **1.1** (FE-008): nombrar el complementario duplicaría el nombre del `<nav>` «Navegación principal» y debe resolverse junto con la semántica de los landmarks.

**Archivos:** `frontend/js/components/sidebar.js`, `frontend/css/layout.css`.

**Esfuerzo:** M · **Impacto:** Alto · **Dependencias:** ninguna.
**Riesgo de regresión visual:** medio (interacción móvil). Mitigación aplicada: harness temporal + Chromium headless a 375×812 y 1200×800.

**Criterios de aceptación**

- El toggle es el primer control tabulable tras el skip link.
- `aria-expanded` refleja el estado real.
- Con el menú cerrado no se puede tabular a ningún enlace del sidebar.
- El fondo no hace scroll con el menú abierto; `Escape` cierra y devuelve el foco.

**Verificación:** Playwright/Chromium con viewport 375×812 — 25 comprobaciones de estado, foco, trampa de tabulación, `inert`, scroll y cambio a escritorio. Todas en verde, sin errores de página. Repetible con `npx playwright test` una vez ampliada la suite (3.4).

**Resultado:** 25/25 comprobaciones correctas; `npm run build` correcto (760 KB, 25 assets).

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

## 1.1 · Semántica de tablas y landmarks — ✅ Aplicado

**Hallazgos:** FE-006, FE-008, FE-011.

**Tareas realizadas**

1. `scope="col"` en los **33 `<th>`** de las 5 tablas: `alerts.html`, `drivers.html`, `trucks.html` (2 tablas) y `truck-detail.html`.
2. `<th aria-label="Acciones">` → `<th scope="col"><span class="sr-only">Acciones</span></th>` en las 4 tablas con columna de acciones.
3. Landmarks: el envoltorio del sidebar pasó de `<aside>` a `<div>` en las 9 páginas internas (la navegación ya está en su `<nav>`); `dashboard-side` pasó a `<div>`; las dos tarjetas de `routes.html` pasaron a `<section>` porque tienen encabezado propio.
4. `ai.html`: `role="group"` en el contenedor de sugerencias por camión.

> No se usó `aria-label` en los `aside` de contenido: no eran complementarios y habría duplicado el nombre del `<nav>` «Navegación principal».

**Archivos:** `ai.html`, `alerts.html`, `dashboard.html`, `drivers.html`, `route-detail.html`, `routes.html`, `settings.html`, `truck-detail.html`, `trucks.html`.

**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo de regresión visual:** nulo (cambian etiquetas y roles, no clases ni estilos).

**Aceptación:** 0 errores `wcag/h63`, `unique-landmark` y `aria-label-misuse`; axe `td-headers-attr`/`th-has-data-cells` sin avisos.

**Verificación:** `npx html-validate "frontend/*.html"` + axe en las 9 páginas.

**Resultado:** `html-validate` pasa de 240 a **200 problemas** y de **42 a 2 errores reales**; los 2 restantes son `prefer-native-element` en `ai.html` (sugerencias de mejora, fuera del alcance de 1.1). `npm run build`, `check:css` y `check:html` correctos.

---

## 1.2 · Encabezados, `<main>` y skip link — ✅ Aplicado

**Hallazgos:** FE-007, FE-014.

**Tareas realizadas**

1. `h1` `.sr-only` en `driver.html` («Portal del conductor») e `index.html` («FrostBase»).
2. Los cuatro `<h3>` de `settings.html` pasaron a `<h2>`; se actualizó `.settings-section__head h2` en `settings.css` (mantiene 14 px, sin cambio visual).
3. `login.html`: el `.login-shell` es ahora `<main class="login-shell" id="main" tabindex="-1">`; `index.html`: `.splash` es ahora `<main class="splash" …>`. No hizo falta CSS nuevo y se conserva el centrado de ambos layouts.
4. Skip link `<a class="skip-link" href="#main">` como primer elemento del `<body>` en las 12 páginas.
5. `id="main" tabindex="-1"` en los `<main>` de las 12 páginas.
6. Estilos `.skip-link` en `base.css`: `position: fixed`, oculto con `transform: translateY(-200%)` y visible en `:focus`, con borde y sombra del sistema.
7. `sidebar.js` inserta el toggle del drawer **después del skip link** para conservar el orden de tabulación.

**Archivos:** las 12 `.html`, `css/base.css`, `css/pages/settings.css`, `js/components/sidebar.js`.

**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** 0.3 (orden del drawer).
**Riesgo de regresión visual:** bajo; el skip link solo aparece al enfocar y los nuevos `<main>` reutilizan las mismas clases.

**Aceptación:** un solo `h1` por página y sin saltos de nivel; las 12 páginas tienen `<main id="main">`; el skip link es el primer tabulable, se ve al enfocarse y lleva el foco al contenido.

**Verificación:** Chromium headless a 1280×800 y 375×812 + `html-validate` + recorrido manual con Tab.

**Resultado:** 12/12 páginas con skip link y `main`; login e index centrados igual que antes (2 columnas en escritorio, 1 en móvil); el skip link recibe el foco y `Enter` lo mueve a `main`; el drawer sigue funcionando (abre, atrapa el foco, `Escape` cierra y devuelve el foco). `html-validate` se mantiene en 200 problemas (2 reales).

---

## 1.3 · Foco visible en el asistente — ✅ Aplicado

**Hallazgos:** FE-015.

**Tareas realizadas:** en `ai.css` se sustituyó `outline: none` por `outline: 2px solid var(--accent-mid); outline-offset: 2px;` en `.ai-truck-picker__select:focus-visible` y `.ai-composer__input:focus-visible`, conservando el refuerzo del `border-color`.

**Archivos:** `frontend/css/pages/ai.css`.
**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo:** bajo (solo estado de foco).

**Aceptación:** el foco del selector de camión y del textarea es perceptible con teclado y no depende solo del color del borde.

**Verificación:** Chromium headless: ambos elementos coinciden con `:focus-visible` y calculan `outline: 2px solid rgb(27, 134, 214)` con `outline-offset: 2px`; captura del textarea enfocado revisada visualmente.

**Resultado:** foco visible en ambos controles, sin errores de página; `npm run build`, `check:css` y `check:html` correctos.

---

## 1.4 · `prefers-reduced-motion` — ✅ Aplicado

**Hallazgos:** FE-016.

**Tareas realizadas:** bloque global al final de `base.css`:

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
**Riesgo:** bajo; los spinners dejan de girar con la preferencia activa (comportamiento esperado).

**Aceptación:** con «reducir movimiento» activado en el SO, no hay animaciones de entrada ni transiciones largas; el spinner no gira pero sigue visible.

**Verificación:** Chromium con `reducedMotion: "reduce"` y `"no-preference"` sobre `dashboard.html`; comprobación de `animation-duration`, `animation-iteration-count` y `transition-duration` calculados.

**Resultado:** con `reduce`, el spinner pasa de `0.7s infinite` a `1e-05s` con una iteración y las transiciones de `body` y `.icon-button` de `0.16s/0.15s` a `1e-05s`; con `no-preference` se mantienen los valores originales. Sin errores de página. `build`, `check:css` y `check:html` correctos.

> Las 4 declaraciones `!important` están acotadas a este bloque y son necesarias para vencer la especificidad de las animaciones y transiciones declaradas por componente.

---

## 1.5 · Errores de formulario y toasts — ✅ Aplicado

**Hallazgos:** FE-012, FE-013, FE-017.

**Tareas realizadas**

1. Nuevo módulo `frontend/js/components/form-errors.js` con `setFieldError`, `clearFieldError`, `clearFormErrors` y `focusFirstError`: crea un `<p class="field-error" role="alert">` dentro del `.form-field`, gestiona `aria-invalid` y `aria-describedby`, y limpia el error al escribir o cambiar el valor.
2. `login.js`: los campos vacíos generan error inline (usuario y contraseña), foco en el primero y sin toast duplicado.
3. `settings.js`: validación por campo; los 8 campos obligatorios se marcan individualmente y los rangos se asocian a la tolerancia correspondiente. `numberValue` ahora devuelve `null` para un campo vacío (antes `Number("")` lo convertía en 0 y ocultaba el error).
4. `drivers.js`: validación de los 5 campos obligatorios y del formato de correo (`validity.typeMismatch`) antes de llamar a la API; se limpian al abrir el modal.
5. `notifications.js`: `role="alert"` para errores, `aria-atomic="true"`, errores persistentes sin barra de progreso y pausa en `focusin` además de `mouseenter`. Se retiró `aria-live="polite"` de los 10 `#toastRoot` para evitar el doble live region.
6. Tablas: `role="status"` en los contadores `#trucksCount`, `#devicesCount`, `#driversCount`, `#alertsCount`, `#routesCount` y `#readingsSummary`, que anuncian el resultado; `aria-busy` ya se aplicaba con `setAriaBusy`.
7. CSS: `.field-error` y borde de error para `[aria-invalid="true"]`.

**Archivos:** `js/components/form-errors.js` (nuevo), `js/pages/login.js`, `js/pages/settings.js`, `js/pages/drivers.js`, `js/core/notifications.js`, `css/components.css`, 10 `.html` (toast roots) y 5 `.html` (contadores).

**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** 0.1.
**Riesgo de regresión visual:** bajo; el mensaje inline ocupa el `gap` del `.form-field` y puede aumentar la altura del formulario.

**Aceptación:** al enviar los formularios con campos vacíos, cada campo queda marcado, el foco va al primero y el error se anuncia; el toast de error es `role="alert"`, no se autodescarta y se puede pausar con teclado.

**Verificación:** Chromium headless con API simulada en `login`, `settings` y `drivers`; comprobación de roles, `aria-*`, foco, limpieza al corregir, persistencia/pausa de toasts y guardado correcto.

**Resultado:** login 2 errores y foco en `identifier`; settings 8 errores vacíos + 1 de rango en `temperatureTolerance` y guardado correcto sin errores; drivers 5 errores y correo inválido detectado; toast de error `alert` persistente sin progreso y toast info `status` que se mantiene al enfocar; 0 errores de página. Build, `check:css`, `check:html` y ESLint correctos.

---

## 1.6 · Patrón de tabs accesible — ✅ Aplicado

**Hallazgos:** FE-009.

**Tareas realizadas**

1. `trucks.html`: `id` en los tabs (`tab-trucks`, `tab-devices`), `aria-controls` hacia sus paneles, `tabindex` móvil (`0` en el activo, `-1` en el inactivo) y paneles con `role="tabpanel"` y `aria-labelledby`.
2. `trucks.js`: `switchTab` sincroniza `aria-selected`, `tabindex` y los paneles; se añadió navegación con `ArrowLeft`, `ArrowRight`, `Home` y `End`, moviendo el foco al tab destino.
3. Se conserva el clic y la carga diferida de dispositivos (`devicesLoaded`).

**Archivos:** `frontend/trucks.html`, `frontend/js/pages/trucks.js`.
**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo:** bajo; solo cambia la interacción de las pestañas.

**Aceptación:** con foco en un tab, las flechas cambian de pestaña y de panel; el lector anuncia «pestaña 2 de 2, seleccionada».

**Verificación:** Chromium headless con API simulada: estado inicial, `ArrowRight`/`ArrowLeft`, `Home`/`End`, clic y visibilidad de paneles.

**Resultado:** ambos tabs con `aria-controls`, `aria-selected` y `tabindex` correctos; paneles `tabpanel` vinculados; flechas y Home/End cambian foco, selección y panel; la carga diferida de dispositivos sigue funcionando. 0 errores de página. Build, `check:css`, `check:html` y ESLint correctos.

---

## 1.7 · Mapas sin `role="application"` — ✅ Aplicado

**Hallazgos:** FE-010.

**Tareas realizadas**

1. Los 4 mapas usaron inicialmente `role="img"` con `aria-label` descriptivo y `aria-describedby` hacia un resumen textual; se eliminó `role="application"`. En 1.8 se sustituyó por `role="region"` al detectar `nested-interactive`.
2. Se corrigió el label copiado de `route-detail.html` («Mapa de la ruta») y el de `truck-detail` («Mapa de ubicación del camión»).
3. Resúmenes: `#mapSummary` visible en dashboard (ya existente), `#routeMapSummary`, `#routeDetailMapSummary` y `#truckMapSummary` (sr-only), actualizados por JS con el número de camiones/puntos o la ubicación y ruta del camión.
4. El mapa sigue siendo enfocable y operable con Leaflet (flechas y `+`/`-`), pero ya no secuestra el modo aplicación.

**Archivos:** `dashboard.html`, `routes.html`, `route-detail.html`, `truck-detail.html`, `js/pages/routes.js`, `route-detail.js`, `truck-detail.js` (`dashboard.js` no necesitó cambios: ya actualizaba `#mapSummary`).

**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** ninguna.
**Riesgo:** bajo; no cambia el render.

**Aceptación:** el lector de pantalla anuncia el resumen del mapa y no queda atrapado en modo aplicación.

**Verificación:** Chromium headless con API simulada en las 4 páginas; atributos estáticos y resúmenes dinámicos.

**Resultado:** 0 `role="application"` en las 4 páginas; `aria-describedby` enlaza con un resumen existente; detalle de ruta «Mapa de la ruta con 2 puntos de entrega y geometría calculada», detalle de camión con placa/coordenadas/geometría y editor de rutas con «2 puntos de entrega». 0 errores de página. Build, `check:css`, `check:html`, ESLint y Prettier correctos.

---

## 1.8 · Rol de región en mapas interactivos — ✅ Aplicado

**Hallazgos:** FE-037 (detectado al ejecutar la suite E2E en 2.5).

**Tareas realizadas**

1. Los 4 mapas pasan de `role="img"` a `role="region"` conservando `aria-label` y `aria-describedby`. Un `role="img"` con marcadores focusables (`tabindex="0"`, `role="button"`) es un `nested-interactive` grave: el lector trata el mapa como una imagen y oculta los controles mientras el teclado sigue entrando en ellos.
2. No se desactiva el teclado de Leaflet: los marcadores siguen siendo operables y el resumen textual se mantiene como descripción del landmark.
3. Se corrigió el plural del resumen de flota («camiónes» → «camiones») en `dashboard.js` y `trucks.js`.

**Archivos:** `dashboard.html`, `routes.html`, `route-detail.html`, `truck-detail.html`, `js/pages/dashboard.js`, `js/pages/trucks.js`.
**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** 1.7.
**Riesgo:** bajo; no cambia el render ni la lógica del mapa.

**Aceptación:** 0 violaciones `nested-interactive`; mapas con nombre accesible y resumen enlazado; suite a11y en verde.

**Verificación:** axe 4.14 (`wcag2a`/`wcag2aa`) en las 4 páginas × 2 temas, abriendo una ruta existente en el editor; `npx playwright test` completo.

**Resultado:** `nested-interactive` **2 → 0** (dashboard light/dark) y 0 en los otros 3 mapas; los 274 marcadores del dashboard siguen enfocables y el resumen se anuncia («467 camiones · 274 con GPS»). Suite de accesibilidad **16/16** y E2E **39/39**. Sin cambios visuales ni errores de consola. Al ampliar la verificación apareció FE-038 en `truck-detail`, que se resolvió en 1.9.

---

## 1.9 · Tablas desplazables accesibles — ✅ Aplicado

**Hallazgos:** FE-038.

**Tareas realizadas**

1. Los 5 contenedores `.table-wrap` (camiones, dispositivos, conductores, alertas e historial de lecturas) pasan a `role="region"` con `aria-label` propio y `tabindex="0"`. Si la tabla desborda, el contenedor recibe foco y las flechas la desplazan horizontalmente.
2. En el detalle del camión se ajustó la tabla compacta a `min-width: 620px`: a 1440 px ya no desborda (657/657) y en móvil sigue desplazándose (620 vs 356).
3. Se mantiene el scroll horizontal como comportamiento responsive; no se oculta ninguna columna ni se cambia el marcado de las tablas.

**Archivos:** `alerts.html`, `drivers.html`, `trucks.html`, `truck-detail.html`, `css/components.css`.
**Esfuerzo:** S · **Impacto:** Medio · **Dependencias:** 1.8.
**Riesgo:** bajo; añade un tab stop por tabla y reduce 23 px el ancho mínimo de la tabla de lecturas.

**Aceptación:** 0 `scrollable-region-focusable`; regiones con nombre; scroll por teclado operativo; suite en verde.

**Verificación:** axe 4.14 en las 4 páginas × 2 anchos (1440/390) y las 2 pestañas de flota; foco + `ArrowRight` sobre `.table-wrap`; suite E2E completa.

**Resultado:** `scrollable-region-focusable` **1 → 0** en `truck-detail` y 0 en el resto (a 390 px todas las tablas desbordan y quedan accesibles). A 1440 px la tabla de lecturas ya cabe entera; a 390 px las flechas desplazan 120 px y el foco se anuncia como «Historial de lecturas». E2E **39/39**, 0 errores de consola. Build 702,1 → 702,5 KB.

---

# Fase 2 · Mejoras estructurales

## 2.1 · Fusionar la cascada «Consolidado» — ✅ Aplicado

**Hallazgos:** FE-018, FE-034.

**Tareas realizadas**

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
- Diff visual nulo salvo la flecha de los selects, restaurada intencionalmente (el CSS base ya la definía y la consolidación la anulaba).
- El CSS resultante mantiene el orden: base → componentes → layout → página → responsive.

**Verificación:** `npx stylelint "frontend/css/**/*.css"` + comparación de estilos computados A/B + `npm run build`.

**Resultado (2026-11-26):** se fusionaron **90 reglas** en las 9 hojas con bloque consolidado y se retiraron los comentarios `Consolidado desde bauhaus.css`. `no-duplicate-selectors` pasa de **87 a 0** y el CSS de producción de **722,3 a 682,3 KB**.

La verificación A/B de estilos computados se ejecutó en la app real (login, dashboard, flota, conductores, rutas, alertas, configuración, asistente, detalle de camión y detalle de ruta): **0 diferencias** en todas las páginas salvo la **flecha de los selects**, que el CSS base ya definía y la capa consolidada anulaba por orden. Se acepta como corrección visual intencional (mejora de UX). Los iconos KPI, la sombra de `.btn--sm`, el login, la configuración, la IA y los detalles quedan idénticos. Los selectores con conflicto de orden (`.btn--sm`, `.kpi-card__icon`) se fusionaron en su última aparición para reproducir la cascada original.

---

## 2.2 · Tokens de tipografía y espaciado — ✅ Aplicado

**Hallazgos:** FE-021, FE-022, FE-023.

**Tareas realizadas**

1. `tokens.css`: escala de 8 pasos (`--text-xs` 11px → `--text-3xl` 32px) + `--icon-xs` 8px; escala de espaciado `--space-1` 2px → `--space-12` 40px; tokens semánticos de estado (`--success-text`, `--warning-text`, `--danger-text` y variantes oscuras) y `--accent-periwinkle`.
2. 201 declaraciones `font-size` migradas a los tokens (incluidas las `rem` del asistente); los `clamp()` se conservan.
3. 368 valores de `gap`/`margin`/`padding` tokenizados al coincidir exactamente con la escala.
4. 18 hex sustituidos por tokens; 0 hex fuera de `tokens.css`.
5. `overflow-x: clip` en `.main` para contener el desbordamiento del carrusel/mapa que la nueva escala provocaba a 390 px.

**Archivos:** `tokens.css` y todas las hojas de `css/` y `css/pages/`; `layout.css` para el clip.
**Esfuerzo:** L · **Impacto:** Alto · **Dependencias:** 2.1.
**Riesgo de regresión visual:** medio; la escala cambia tamaños en 0,5–2 px. Mitigación: comprobación de overflow en 32 combinaciones y capturas en 1440/390.

**Aceptación:** ≤ 8 tamaños de fuente distintos; 0 hex fuera de `tokens.css`; escala documentada.

**Verificación:** medición de `font-size:`/hex; `layout-check` en 9 páginas × 4 anchos; capturas; build/checks.

**Resultado:** tamaños literales 29 → **0** (8 pasos + icono); hex fuera de tokens 18 → **0**; **368** usos de `var(--space-*)`; **0 desbordamientos** en 32 combinaciones; capturas de login, dashboard, configuración y móvil revisadas. El CSS de producción sube de 682,3 a **718,4 KB** por la verbosidad de `var()` (trade-off de mantenibilidad).

---

## 2.3 · Breakpoints unificados mobile-first — 🟡 Parcial (4 cortes; falta inversión)

**Hallazgos:** FE-020.

**Tareas realizadas**

1. Se remapearon **32 media queries** a 4 cortes: `480`, `768`, `1024` y `1280` px (antes 13 valores entre 360 y 1180).
2. Se mantiene `max-width` (desktop-first): la inversión a `min-width` exige mover los valores base de todos los componentes a reglas `min-width`, no solo cambiar la consulta; un cambio mecánico rompería los layouts.
3. Verificación en **70 combinaciones** (7 páginas × 10 anchos) y capturas en los rangos que cambian. Se corrigió el badge «Dispositivo desconectado» que se recortaba a 1100/1280 añadiendo `flex-wrap` a `.alert-carousel__top`.

**Resultado:** **13 → 4 breakpoints** (32 consultas), **0 desbordamientos** y 0 errores entre 320 y 1440 px. Login a 800, rutas a 1024 y dashboard a 1100/1280 revisados. La inversión completa a mobile-first queda pendiente como **2.3b**.

**Archivos:** todas las hojas de `css/` y `css/pages/`; `components.css` para el badge.
**Esfuerzo:** M · **Impacto:** Medio · **Dependencias:** 2.1.
**Riesgo de regresión visual:** alto si se convierte a ciegas. Mitigación aplicada: una estrategia única de 4 cortes y verificación en 10 anchos.

**Aceptación:** 4 breakpoints ✅; todos `min-width` ❌ (pendiente 2.3b); ninguna página se rompe entre 320 y 1440 ✅.

**Verificación:** búsqueda de `@media (max-width` (4 valores), `layout-check` en 10 anchos y capturas.

---

## 2.4 · Limpieza de CSS muerto — ✅ Aplicado

**Hallazgos:** FE-025, FE-026, FE-027.

**Tareas realizadas**

1. Búsqueda global en HTML/JS de todas las clases candidatas (incluidas las dinámicas) y confirmación de que no se usan.
2. Eliminadas de `base.css`: `.text-success`, `.text-warning`, `.mono`, `.fade-in` (se conserva `@keyframes fadeIn`, usado por modales) y `.spinner--light`.
3. Eliminadas de `components.css`: `.btn--secondary`, `.btn--danger-soft`, `.card__footer`, `.card__section`, `.two-column`, `.divider`, `.kpi-card--clickable`, `.info-grid`/`.info-tile*`, `.toggle-row*`/`.toggle-switch*`, `.map-supply` (solo el selector), `.input-group*`, `.cell-strong`, `.notice--danger` y `.filter-bar*`.
4. Eliminadas de `layout.css`: `.two-column` (base y media) y `.brand-name accent`.
5. Eliminadas de `truck-detail.css`: `.detail-actions` (base y media); de `trucks.css`: `.truck-status-select`.
6. `app.js`: eliminada la clase `is-ready`, que no tenía CSS asociado.

**Archivos:** `base.css`, `components.css`, `layout.css`, `truck-detail.css`, `trucks.css`, `app.js`.
**Esfuerzo:** S · **Impacto:** Bajo · **Dependencias:** 2.1 (parcial).
**Riesgo:** bajo; solo se eliminaron selectores sin coincidencias en HTML/JS.

**Aceptación:** 0 coincidencias de las clases eliminadas en HTML/JS; build y checks verdes.

**Verificación:** búsqueda global + `npm run build` + `check:css`/`check:html` + ESLint + Prettier.

**Resultado:** 0 coincidencias restantes; CSS de producción 756,1 → **722,3 KB**; duplicados de stylelint 91 → 87 (algunos selectores muertos también estaban duplicados). Build y checks correctos.

---

## 2.5 · Parciales de `<head>` y sidebar estática — ✅ Aplicado

**Hallazgos:** FE-001, FE-033.

**Tareas realizadas**

1. `frontend/partials/head.html` concentra el `<head>` completo (metas, preload de la fuente, hojas por página y `theme-boot`). `frontend/pages.config.json` declara por página `title`, `description` y `styles`, sustituyendo las 12 copias.
2. `frontend/partials/sidebar.html` contiene el sidebar y el nav completos. El build resuelve los includes, marca el enlace activo (`is-active` + `aria-current="page"`) y aplica los alias `truck-detail → trucks` y `route-detail → routes`.
3. `scripts/build.mjs` lee la configuración y los parciales, falla si una página no declara metadata o si queda un include sin resolver, y mantiene igual el resto del pipeline (CSS/JS hasheados y `manifest.json`).
4. `js/components/sidebar.js` elimina `NAV_ITEMS` y el `innerHTML`: solo rellena el nombre del usuario, enlaza tema/logout y monta el drawer. La navegación ya viaja en el HTML servido.

**Archivos:** las 12 `.html`, `scripts/build.mjs`, `js/components/sidebar.js`, `partials/head.html`, `partials/sidebar.html`, `pages.config.json`.
**Esfuerzo:** L · **Impacto:** Medio · **Dependencias:** 2.1.
**Riesgo:** medio (el build cambia). Mitigación: comparación del HTML generado con el anterior y suite E2E.

**Aceptación:** una sola fuente para el `<head>` ✅; el HTML servido incluye la navegación sin JS ✅; el build produce el mismo conjunto de assets ✅ (25 assets).

**Verificación:** `npm run build` + comparación normalizada de las 12 páginas + Playwright con y sin JS + `check:css`/`check:html`.

**Resultado:** las 12 páginas comparten `<head>` y las 9 internas llevan el sidebar en el HTML (7 enlaces, 1 activo correcto). Build: 25 assets, **718,6 → 702,1 KB** (el marcado sale del bundle JS). Comparación del HTML generado: `index.html` idéntico; el resto solo difiere en el orden de `<meta>`/`<title>`, el `noindex` añadido a `login.html` (ahora igual que las demás) y el sidebar estático. 9/9 páginas con 7 enlaces, `aria-current="page"`, usuario y 0 errores de consola; drawer (apertura, foco, Escape y retorno del foco), tema persistente y logout correctos. E2E: **37 pasan**; los 2 fallos de `dashboard` son previos (FE-037) y se reproducen igual con el build anterior.

**Nota de despliegue:** las páginas fuente ya no son autónomas; el frontend se sirve desde `frontend/build`. `make dev` y la imagen Docker ya ejecutan el build. README actualizado.

---

## 2.6 · Pesos tipográficos coherentes — ✅ Aplicado

**Hallazgos:** FE-024.

**Tareas realizadas:** se comprobó con `fontTools` que el WOFF2 es una fuente variable con eje `wght` **100–900**. En lugar de bajar los pesos, se declaró el rango real en `@font-face` (`font-weight: 400 900`) y se actualizó `vendor_assets.py` (URL `wght@400..900` y CSS generado) para que una regeneración no lo revierta.

**Archivos:** `css/fonts.css`, `tools/vendor_assets.py`.
**Esfuerzo:** S · **Impacto:** Bajo · **Dependencias:** 2.2.
**Riesgo:** visible en titulares; se comparó la captura del login.

**Aceptación:** ningún `font-weight` fuera del rango declarado; los titulares mantienen el aspecto.

**Verificación:** `fontTools` (`fvar` 100–900), `document.fonts.check("900 …")`, `FontFace.weight = "400 900"` cargado, `getComputedStyle` de `h1/h2` = 900, captura comparada, build/checks.

**Resultado:** el navegador usa la instancia real 900 (sin negrita sintética); la captura del login no muestra diferencias apreciables. `npm run build`, `check:css` y `check:html` correctos.

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
| `html-validate` (errores reales) | 44 (2 tras 1.1) | **0** |
| `stylelint no-duplicate-selectors` | 87 | **0** ✅ |
| axe (`wcag2a/aa`, incl. moderate) | Sin medir (≥2 probables) | **0 violaciones** en 12 páginas × 2 temas |
| Lighthouse accesibilidad (login, dashboard, trucks) | Sin medir | **≥ 95** |
| Contraste | 4 fallos AA | **100 %** textos ≥ 4.5:1 y UI ≥ 3:1 |
| `!important` | 3 | **3 en utilidades + 4 acotados a `prefers-reduced-motion`** |
| Tamaños de fuente distintos | 29 | **8** ✅ |
| Breakpoints | 13 | **4** ✅ (aún `max-width`) |
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
| 2026-11-25 | 0.3 | `js/components/sidebar.js`, `css/layout.css` | Drawer accesible: `aria-expanded`, foco atrapado, `inert`, scroll bloqueado; 25/25 comprobaciones |
| 2026-11-25 | 0.4 | `pages/dashboard.css` | Media query al final; 170 px y 340 px aplican en móvil |
| 2026-11-25 | 1.1 | 9 `.html` (`ai`, `alerts`, `dashboard`, `drivers`, `route-detail`, `routes`, `settings`, `truck-detail`, `trucks`) | 33 `<th scope="col">`, sidebar a `<div>`, tarjetas de rutas a `<section>`, `role="group"` en IA; errores reales 42 → 2 |
| 2026-11-25 | 1.2 | 12 `.html`, `css/base.css`, `css/pages/settings.css`, `js/components/sidebar.js` | Skip link + `<main id="main">` en 12/12, `h1` en driver/index, `h3 → h2` en settings; foco verificado en Chromium |
| 2026-11-25 | 1.3 | `css/pages/ai.css` | Outline de 2 px restaurado en el selector de camión y el textarea; `:focus-visible` verificado en Chromium |
| 2026-11-25 | 1.4 | `css/base.css` | Guard de `prefers-reduced-motion`: animaciones y transiciones a `1e-05s`; spinner estático; valores normales intactos |
| 2026-11-25 | 1.5 | `js/components/form-errors.js` (nuevo), `js/pages/{login,settings,drivers}.js`, `js/core/notifications.js`, `css/components.css`, 10 `.html` | Errores inline con `aria-invalid`/`aria-describedby` y foco; toasts `alert` persistentes y pausables; contadores `role="status"` |
| 2026-11-25 | 1.6 | `trucks.html`, `js/pages/trucks.js` | Tabs con `aria-controls`/`tabpanel`, roving tabindex y navegación con flechas/Home/End; verificado en Chromium |
| 2026-11-25 | 1.7 | `dashboard.html`, `routes.html`, `route-detail.html`, `truck-detail.html`, `js/pages/{routes,route-detail,truck-detail}.js` | `role="img"` + `aria-describedby`, resúmenes dinámicos y 0 `role="application"`; verificado en Chromium |
| 2026-11-26 | 2.1 (parte 1) | 8 hojas CSS (`base`, `components`, `layout`, `dashboard`, `login`, `routes`, `settings`, `truck-detail`) | 39 reglas totalmente sobrescritas eliminadas; duplicados 130 → 91; sin cambios de cascada |
| 2026-11-26 | 2.4 | `base/components/layout/truck-detail/trucks` CSS + `app.js` | Clases muertas y `.brand-name accent` eliminadas; `is-ready` retirada; CSS 756,1 → 722,3 KB; duplicados 91 → 87 |
| 2026-11-26 | 2.1 (parte 2) | 9 hojas CSS | 90 reglas fusionadas y comentarios consolidados retirados; duplicados 87 → 0; CSS 722,3 → 682,3 KB; A/B sin diferencias salvo la flecha de los selects |
| 2026-11-26 | 2.2 | `tokens.css` + 14 hojas CSS | 201 `font-size` y 368 espaciados tokenizados; 18 hex → tokens; 0 desbordamientos; CSS 682,3 → 718,4 KB |
| 2026-11-26 | 2.3 (parte 1) | 15 hojas CSS | 32 media queries remapeadas a 4 cortes (480/768/1024/1280); 70 combinaciones sin overflow; badge de alerta corregido |
| 2026-11-26 | 2.6 | `css/fonts.css`, `tools/vendor_assets.py` | Rango `wght` 400–900 declarado; 800/900 reales; verificado con fontTools y `document.fonts` |
| 2026-11-26 | 2.5 | 12 `.html`, `partials/{head,sidebar}.html`, `pages.config.json`, `scripts/build.mjs`, `js/components/sidebar.js` | `<head>` y sidebar únicos; 9/9 páginas con 7 enlaces sin JS; build 718,6 → 702,1 KB; E2E 37 pasan (2 fallos previos del mapa, FE-037) |
| 2026-11-26 | 1.8 | 4 `.html` + `js/pages/{dashboard,trucks}.js` | Mapas con `role="region"`; `nested-interactive` 2 → 0; a11y 16/16 y E2E 39/39; plural «camiones» corregido; FE-038 registrado |
| 2026-11-26 | 1.9 | 4 `.html` + `css/components.css` | 5 tablas con `role="region"`, nombre y `tabindex`; `scrollable-region-focusable` 1 → 0; tabla compacta 620 px; E2E 39/39 |

**Próximo paso recomendado:** **3.1 · Linters en CI** (M) para fijar los avances. La inversión mobile-first (2.3b) sigue pendiente como sesión dedicada.
