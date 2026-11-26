# Auditoría frontend — FrostBase

**Fecha:** 2026-11-25
**Rama auditada:** `devolp`
**Alcance:** capa visual del proyecto — `frontend/*.html`, `frontend/css/**` y los módulos JS que generan marcado o modifican estilos.
**Fuera de alcance:** `frontend/assets/vendors`, `frontend/node_modules`, `frontend/build`, `dist`, backend y base de datos (salvo cabeceras de seguridad y CSP, revisadas como contexto).

**Herramientas ejecutadas** (sin instalar nada en el proyecto):

```bash
npx html-validate@8 "frontend/*.html"
npx --package stylelint@16 --package stylelint-config-standard@36 stylelint "frontend/css/**/*.css"
npm run build
```

**Estado de git al iniciar:** rama `devolp`, con un archivo no rastreado (`plan_implementacion_modulo_conductores.md`, del equipo, excluido de esta auditoría). No se modificó ningún archivo durante la auditoría.

> **Actualización posterior:** tras la auditoría se aplicaron los pasos **0.1, 0.2, 0.3, 0.4, 1.1, 1.2, 1.3, 1.4 y 1.5** del plan (`docs/plan-mejora.md`). Los hallazgos afectados aparecen marcados como **Resuelto**. El resto sigue pendiente.

---

## 1. Resumen ejecutivo

Proyecto con una base mejor que la media: sistema de tokens real con tema claro/oscuro, build con assets hasheados y caché inmutable, CSP y cabeceras de seguridad en servidor, cero estilos en línea, solo 3 `!important`, imágenes con dimensiones reservadas y una suite de accesibilidad con axe ya escrita. El diseño es coherente y el uso de Grid/Flexbox es correcto.

Los riesgos se concentran en tres frentes: (1) la cascada está construida en dos generaciones superpuestas (130 selectores duplicados), lo que ya produjo un bug real y hace impredecible cada cambio; (2) existen barreras de accesibilidad concretas (botones sin nombre, buscadores sin etiqueta, contraste AA insuficiente, drawer móvil sin gestión de foco); (3) la escala tipográfica y los breakpoints son ad hoc (30 tamaños de fuente, 13 breakpoints).

**Nota global: 6/10** en el momento de la auditoría; **6,5/10** tras 0.1, 0.2 y 0.4, **7/10** tras 0.3, **7,5/10** tras 1.1, **8/10** tras 1.2 y **8,5/10** tras 1.5. Aprueba en intención e infraestructura; la deuda de cascada y los fallos de rendimiento impiden una nota mayor. Todo es corregible sin rediseño.

---

## 2. Estructura del proyecto y stack detectado

```
frontend/
├── index.html … ai.html          12 páginas HTML estáticas
├── css/
│   ├── fonts.css                 @font-face (Outfit, woff2, font-display: swap)
│   ├── tokens.css                73 custom properties + tema oscuro
│   ├── base.css                  reset mínimo, tipografía base, utilidades
│   ├── layout.css                app-shell, sidebar, page-header
│   ├── components.css            tarjetas, botones, badges, tablas, modales, toasts
│   └── pages/                    11 hojas por página
├── js/
│   ├── core/                     app, api, auth, theme, theme-boot, helpers, notifications
│   ├── components/               sidebar, modal, map, feedback, pagination
│   └── pages/                    12 controladores
├── assets/
│   ├── logo.png                  71,3 KB (logo + favicon)
│   ├── fonts/outfit-latin.woff2  31,5 KB
│   └── vendors/                  FontAwesome subset, Leaflet
├── scripts/                      build.mjs (esbuild), check-css.mjs, check-innerhtml.mjs
└── tests/e2e/                    accessibility, csp, critical-flows, ai-assistant
```

**Stack real**

- HTML5 estático multipágina, sin plantillas ni parciales.
- CSS propio, sin preprocesador ni framework. Metodología **BEM parcial** (`card__header`, `btn--primary`) combinada con utilidades (`.hidden`, `.sr-only`, `.muted`, `.mono`).
- JavaScript ES modules nativo, sin framework. El sidebar y los modales se generan en cliente.
- Build con **esbuild** (`scripts/build.mjs`): agrupa y minifica el CSS por página, bundlea el módulo JS y hashea los assets. Docker ejecuta el build en producción (`docker/Dockerfile:11-17`).
- **Sin CDNs**: FontAwesome y Leaflet están vendorizados.
- **Sistema de diseño**: 73 tokens (color, radios, sombras, sidebar, transición), tema oscuro vía `[data-theme="dark"]`, `focus-visible` global y utilidad `.sr-only`. No hay tokens de espaciado ni escala tipográfica.

**Organización en 6 líneas:** conviven dos generaciones de CSS. La original (componentes con radios y sombras suaves) y una segunda capa "Bauhaus" añadida al final de 8 hojas bajo el comentario `/* ===== Consolidado desde bauhaus.css (T4.5) ===== */`, que reescribe colores, bordes, sombras y tipografía por orden de cascada. El marcado se repite en las 12 páginas (bloque `<head>` completo) y el sidebar se inyecta por JS. El JS está razonablemente separado en `core`, `components` y `pages`.

---

## 3. Métricas clave

| Métrica | Valor |
|---|---|
| Páginas HTML | 12 |
| Hojas CSS propias | 16 (± 6.050 líneas, ± 104 KB en crudo) |
| Módulos JS | 24 (± 6.116 líneas) |
| `!important` | **7**: 3 en utilidades de ocultación + 4 en el guard de `prefers-reduced-motion` |
| Atributos `style=""` | **0** |
| Selectores duplicados (`no-duplicate-selectors`) | **130** |
| Selectores repetidos en el mismo archivo (conteo propio) | **209** |
| Errores reales de `html-validate` | **44** (2 tras 1.1) |
| Avisos de estilo `html-validate` (`void-style`, `doctype-style`) | 198 |
| Breakpoints distintos | **13** (360 → 1180 px) |
| Tamaños de `font-size` distintos en px | **30** |
| Declaraciones `px` / `rem` | **1.047** / **22** |
| Hex fuera de `tokens.css` | **91** (44 únicos) |
| Clases CSS sin uso confirmado | **≈17** |
| Tokens definidos / sin uso | 73 / 3 (`--color-cream`, `--bg-soft`, `--shadow-lg`) |
| CSS por página (crudo) | 51–63 KB + 4,1 KB FontAwesome |
| Fuentes | Outfit 31,5 KB; FA solid 153,5 KB; FA regular 24,9 KB |
| Imágenes | `logo.png` 71,3 KB (logo + favicon) |
| Imágenes sin `width`/`height` | 0 |
| `target="_blank"`, HTTP mixto, CDN | 0 |
| IDs duplicados por página | 0 |
| Páginas con `<main id="main">` | **12/12** |
| Páginas con skip link funcional | **12/12** |

---

## 4. Tabla resumen de hallazgos

> Severidad: **A** = Alta, **M** = Media, **B** = Baja. No se identificaron hallazgos críticos.

| ID | Categoría | Sev. | Título | Ubicación | Estado |
|---|---|---|---|---|---|
| FE-001 | HTML / Semántica | M | Navegación principal inyectada por JS en `<aside>` vacío | `dashboard.html:23`; `js/components/sidebar.js:40` | Pendiente |
| FE-002 | Accesibilidad | **A** | Drawer móvil sin foco, `aria-expanded` ni bloqueo de scroll | `css/layout.css:280-291`; `sidebar.js:87-108` | **Resuelto (0.3)** |
| FE-003 | Accesibilidad | **A** | Botones solo-icono sin nombre accesible | `driver.html:58-67` | **Resuelto (0.1)** |
| FE-004 | Accesibilidad | **A** | Buscadores sin etiqueta (solo `placeholder`) | `trucks.html:57,95`; `routes.html:56` | **Resuelto (0.1)** |
| FE-005 | Accesibilidad | **A** | Contraste AA insuficiente en tokens y badges | `tokens.css:33`; `components.css:1835`; `login.css:314` | **Resuelto (0.2)** |
| FE-006 | HTML / Semántica | M | `<th>` sin `scope` en 5 tablas | `alerts.html:80-86`; `drivers.html:89-95`; `trucks.html:72-79,109-114`; `truck-detail.html:92-96` | **Resuelto (1.1)** |
| FE-007 | HTML / Semántica | M | Sin `h1` o saltos de nivel | `driver.html:38-113`; `settings.html:38,64,90,106`; `index.html:17` | **Resuelto (1.2)** |
| FE-008 | Accesibilidad | M | Landmarks `aside` sin nombre único | `dashboard.html:113`; `routes.html:40,48` | **Resuelto (1.1)** |
| FE-009 | Accesibilidad | M | Patrón `tablist` incompleto (sin `aria-controls`, `tabpanel`, flechas) | `trucks.html:39-46`; `trucks.js:498-518` | Pendiente |
| FE-010 | Accesibilidad | M | `role="application"` en 4 mapas | `dashboard.html:79`; `routes.html:129`; `route-detail.html:52`; `truck-detail.html:60` | Pendiente |
| FE-011 | HTML / Semántica | M | `aria-label` en elemento no interactivo | `ai.html:146-149` | **Resuelto (1.1)** |
| FE-012 | Accesibilidad | M | Errores de formulario no asociados al campo | `login.html:48`; `login.js:54-66`; `settings.html:32` | **Resuelto (1.5)** |
| FE-013 | Accesibilidad | M | Toasts de error con `role="status"` y autodescarte sin pausa por teclado | `notifications.js:30,52` | **Resuelto (1.5)** |
| FE-014 | Accesibilidad | M | `login` e `index` sin `<main>`; no hay skip link | `login.html:23`; `index.html:17` | **Resuelto (1.2)** |
| FE-015 | Accesibilidad | M | Foco visible eliminado en inputs del asistente | `ai.css:322-325,484-487` | **Resuelto (1.3)** |
| FE-016 | Accesibilidad | M | Sin `prefers-reduced-motion` pese a 14 animaciones | `base.css:161-202`; `components.css:1229-1301` | **Resuelto (1.4)** |
| FE-017 | Accesibilidad | B | Tablas dinámicas sin anuncio del resultado | `feedback.js:68-73`; contadores de tablas | **Resuelto (1.5)** |
| FE-018 | CSS / Arquitectura | **A** | Cascada de dos generaciones: 130 selectores duplicados | `base.css:214`; `components.css:1639`; `layout.css:326`; `login.css:225` (+5) | Pendiente |
| FE-019 | CSS / Arquitectura | M | Bug de cascada: media query de `.temp-card` anulada | `css/pages/dashboard.css:55-67,69` | **Resuelto (0.4)** |
| FE-020 | Responsive | M | 13 breakpoints, desktop-first e inconsistente | todas las hojas | Pendiente |
| FE-021 | CSS / Calidad | M | Sin escala tipográfica: 30 tamaños px distintos | `base.css:51-62`; `components.css` | Pendiente |
| FE-022 | CSS / Calidad | M | Sin tokens de espaciado; valores ad hoc | `tokens.css`; toda la CSS | Pendiente |
| FE-023 | CSS / Calidad | M | 91 hex fuera de tokens | `components.css:92,101,120`; `trucks.css`; `login.css` | Pendiente |
| FE-024 | UI/UX | M | `font-weight: 800/900` con fuente declarada 400–700 | `fonts.css:5`; `base.css:46`; `components.css:1667` | Pendiente |
| FE-025 | CSS / Calidad | B | ≈17 clases/componentes muertos | `components.css:43-50,95-102`; `layout.css:263-267` | Pendiente |
| FE-026 | CSS / Calidad | B | Selector imposible `.brand-name accent` | `layout.css:61-63` | Pendiente |
| FE-027 | CSS / Calidad | B | Clase `is-ready` añadida sin CSS que la use | `app.js:160` | Pendiente |
| FE-028 | Rendimiento | M | 6 CSS render-blocking + fuente FA de 153 KB | `dashboard.html:11-18`; `assets/vendors/fontawesome/` | Pendiente |
| FE-029 | Compatibilidad | M | `100vh` en 9 sitios (salto en Safari iOS) | `base.css:18`; `components.css:1277`; `layout.css:2`; `login.css:2`; `ai.css:6,235`; `driver.css:4`; `index.css:6` | Pendiente |
| FE-030 | Rendimiento | B | `theme-boot.js` bloqueante en `<head>` siendo 11 líneas | `login.html:16` (y 11 páginas más) | Pendiente |
| FE-031 | Rendimiento | B | `logo.png` de 71 KB usado como logo y favicon | `assets/logo.png`; `login.html:8,27` | Pendiente |
| FE-032 | Compatibilidad | B | `fonts.css` usa ruta absoluta y el preload relativa | `fonts.css:7` vs `dashboard.html:10` | Pendiente |
| FE-033 | Mantenibilidad | M | Bloque `<head>` duplicado literalmente en 12 páginas | todas las `.html` | Pendiente |
| FE-034 | Mantenibilidad | B | `check:css` no detecta duplicados intra-archivo; sin stylelint | `scripts/check-css.mjs:44`; `package.json:6-10` | Pendiente |
| FE-035 | Mantenibilidad | B | `escapeHtml` duplicado en `modal.js` | `modal.js:119-127` vs `helpers.js` | Pendiente |
| FE-036 | Testing | B | Suite a11y solo falla con `serious/critical` y omite `driver/index` | `tests/e2e/accessibility.spec.js:16-19,4-12` | Pendiente |

**Distribución:** 0 Críticas · **5 Altas** · **21 Medias** · **10 Bajas**.

---

## 5. Detalle de hallazgos

### 5.1 HTML: estructura y semántica

#### FE-001 · Navegación principal inyectada por JS en un `<aside>` vacío — Media · Riesgo

**Ubicación:** `frontend/dashboard.html:23` y `frontend/js/components/sidebar.js:40`.

**Evidencia:**

```html
<!-- dashboard.html:23 -->
<aside class="sidebar" id="sidebar"></aside>
```

```js
// sidebar.js:40
sidebar.innerHTML = `
  <a class="sidebar__brand" ...>
  <nav class="sidebar__nav" aria-label="Navegación principal">…
```

**Descripción e impacto:** el landmark de navegación no existe en el HTML; hasta que se ejecuta el módulo, el `<aside>` está vacío y es el único `<nav>` de la página. Si el JS falla o se bloquea, no hay navegación. Además la navegación principal queda dentro de un landmark `complementary`, semánticamente incorrecto.

**Recomendación:** renderizar sidebar y nav en HTML estático (parcial de build) y dejar JS solo para el estado activo y el drawer. Mientras tanto, añadir `aria-label` al `aside` y un `noscript` con enlaces.

---

#### FE-006 · `<th>` sin `scope` — Media · Error · **Resuelto (1.1)**

**Ubicación:** `alerts.html:80-86`, `drivers.html:89-95`, `trucks.html:72-79` y `109-114`, `truck-detail.html:92-96`.

**Evidencia:**

```html
<!-- trucks.html:72-79 -->
<th>Placas</th>
<th>Vehículo</th>
<th>Estado</th>
<th>Ruta</th>
<th>Temperatura</th>
<th>Humedad</th>
<th>Última comunicación</th>
<th aria-label="Acciones"></th>
```

**Impacto:** `html-validate` reporta 33 errores `wcag/h63`. Los lectores de pantalla no siempre infieren la relación columna/celda en tablas de datos, sobre todo cuando hay columnas vacías de acciones.

**Recomendación:**

```html
<th scope="col">Placas</th>
…
<th scope="col"><span class="sr-only">Acciones</span></th>
```

**Corrección aplicada:** `scope="col"` en los **33 `<th>`** de las 5 tablas y sustitución de `<th aria-label="Acciones">` por `<th scope="col"><span class="sr-only">Acciones</span></th>` para no depender de un nombre accesible sin texto. `html-validate` ya no reporta `wcag/h63`.

---

#### FE-007 · Sin `h1` o saltos de nivel — Media · Error · **Resuelto (1.2)**

**Ubicación:** `driver.html` (todo el documento), `settings.html:38,64,90,106`, `index.html:17`.

**Evidencia:**

```html
<!-- driver.html:38-113: el documento empieza en <h2>, no hay <h1> -->
<h2 class="card__title"><i class="fa-solid fa-route"></i> Ruta de hoy</h2>
```

```html
<!-- settings.html:27 h1 → settings.html:38 h3 -->
<h1>Configuración</h1>
…
<h3>Rango de temperatura</h3>
```

**Impacto:** la jerarquía de encabezados es el mecanismo principal de navegación por lector de pantalla. Un salto `h1 → h3` oculta un nivel y `driver.html` no tiene título de página.

**Recomendación:** `h1` (puede ser `.sr-only` si el diseño no lo contempla) en `driver.html` y `index.html`; subir los `h3` de `settings.html` a `h2` (los `h2` de las tarjetas laterales ya existen y quedarían al mismo nivel, que es lo correcto).

**Corrección aplicada:** `h1` con `.sr-only` en `driver.html` («Portal del conductor») e `index.html` («FrostBase»); los cuatro `h3` de `settings.html` pasaron a `h2` y el selector `.settings-section__head h2` conserva los 14 px, sin cambio visual. La secuencia resultante es `h1 → h2` en las 12 páginas.

---

#### FE-011 · `aria-label` en un elemento no interactivo — Media · Error · **Resuelto (1.1)**

**Ubicación:** `frontend/ai.html:146-149`.

**Evidencia:**

```html
<div class="ai-suggestions ai-suggestions--truck" aria-label="Consultas por camión">
```

**Impacto:** `html-validate` (`aria-label-misuse`). En un `div` sin rol, el nombre accesible se ignora o se anuncia de forma inconsistente. El grupo de botones queda sin contexto.

**Recomendación:** `<div role="group" aria-label="Consultas por camión">` o convertir el contenedor en `<fieldset>` con `<legend class="sr-only">`.

**Corrección aplicada:** se añadió `role="group"` al contenedor, que ahora expone el nombre «Consultas por camión» como grupo de la barra de sugerencias. `html-validate` ya no reporta `aria-label-misuse`.

---

### 5.2 CSS: calidad y arquitectura

#### FE-018 · Cascada de dos generaciones — Alta · Deuda técnica

**Ubicación:** `base.css:214`, `components.css:1639`, `layout.css:326`, `alerts.css:122`, `dashboard.css:146`, `login.css:225`, `routes.css:372`, `settings.css:138`, `truck-detail.css:174`.

**Evidencia:**

```css
/* components.css:1639 en adelante */
/* ===== Consolidado desde bauhaus.css (T4.5) ===== */
.card { border: 3px solid var(--border-ink); border-radius: 0; box-shadow: 6px 6px 0 var(--ink); }
.btn  { border: 2px solid var(--border-ink); border-radius: 0; … }
```

**Métricas:** `stylelint` detecta **130 selectores duplicados**. Dentro de un mismo archivo, `.main` se declara **8 veces** (`layout.css`), `.login-panel` **5 veces**, `.temp-card`, `.card` y `.btn` **3 veces**. En total, 209 repeticiones de selector en 12 archivos.

**Impacto:** cada cambio exige razonar sobre orden de archivo, orden dentro del archivo y media queries posteriores. Ya ha generado el bug FE-019 y hace que los tokens se mezclen con hex sueltos de la segunda generación.

**Recomendación:** fusionar cada bloque "Consolidado" con su regla original conservando el valor final, hoja por hoja, con revisión visual. Después, activar `no-duplicate-selectors` en CI. No hacerlo de golpe: un commit por archivo.

---

#### FE-019 · Media query anulada por orden de cascada — Media · Error · **Resuelto (0.4)**

**Ubicación:** `frontend/css/pages/dashboard.css:55-67` y `:69-70` (estado original).

**Evidencia original:**

```css
@media (max-width: 640px) {
  .map--dashboard { height: 340px; }
  .temp-card { flex-basis: 170px; }   /* línea 65 */
}

.temp-card { flex: 0 0 188px; }       /* línea 69: gana por orden */
.map--dashboard { height: 430px; }    /* línea 142: gana por orden */
```

**Impacto:** en móvil, las tarjetas de temperatura se quedaban en 188 px y el mapa en 430 px en lugar de 170/340. La intención responsive del diseño no se aplicaba.

**Corrección aplicada:** se movió el bloque `@media (max-width: 640px)` al final de la hoja y se declaró `flex: 0 0 170px`. Verificado con `npm run build`.

**Recomendación estructural:** al fusionar la cascada (2.1), mantener las media queries al final de cada hoja o migrar a mobile-first (2.3).

---

#### FE-021 · Sin escala tipográfica — Media · Deuda técnica

**Ubicación:** `frontend/css/base.css:51-62` y resto de hojas.

**Evidencia:** 30 tamaños distintos en px: `8, 10, 10.5, 11, 11.5, 11.8, 12, 12.5, 12.8, 13, 13.5, 14, 14.5, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 32` (y `body` cambia de `14px` en `base.css:22` a `14.5px` en `base.css:217`).

**Impacto:** la jerarquía visual depende de diferencias de 0,5 px, imposibles de percibir y de mantener. Dificulta el zoom de texto y la consistencia entre páginas.

**Recomendación:** definir 7–8 tokens (`--text-xs` … `--text-3xl`) y sustituir los valores sueltos. Los títulos ya usan `clamp()` (3 usos), patrón a conservar.

---

#### FE-022 · Sin tokens de espaciado — Media · Deuda técnica

**Ubicación:** `frontend/css/tokens.css` (no existen tokens de espacio) y todas las hojas.

**Evidencia:** conviven `gap: 4px`, `6px`, `7px`, `8px`, `10px`, `12px`, `14px`, `18px`, `20px`, `22px`, `26px`, `32px`… elegidos por componente.

**Recomendación:** escala base 4 (`--space-1: 4px` … `--space-8: 48px`) y sustitución progresiva.

---

#### FE-023 · Colores fuera de tokens — Media · Deuda técnica

**Ubicación:** `components.css:92` (`#2469de`), `components.css:101` (`#022f6d`), `components.css:120` (`#d94e58`), `components.css:199/208` (`#0a6f60`, `#a86b00`), `trucks.css`, `login.css:310` (`#0a1b2b`).

**Evidencia:**

```css
/* components.css:91-93 (primera generación, ya inalcanzable por la consolidación) */
.btn--primary:hover { background: #2469de; }
```

**Impacto:** 91 hex fuera de `tokens.css` (44 únicos). Varios pertenecen a la primera generación y ya no se aplican, pero siguen ahí y confunden. Rompen la promesa del sistema de diseño y el cambio de tema.

**Recomendación:** tras 2.1, sustituir por tokens semánticos (`--color-on-accent`, `--state-success-text`…).

---

#### FE-025 · Clases y componentes muertos — Baja · Deuda técnica

**Ubicación:** `components.css:43-50` (`.card__footer`, `.card__section`), `components.css:95-102` (`.btn--secondary`), `components.css:123-130` (`.btn--danger-soft`), `layout.css:263-267` (`.two-column`), `base.css:119-133` (`.text-danger`/`.text-success`/`.text-warning`/`.mono`), `.fade-in`, `.spinner--light`, `.divider`, `.kpi-card--clickable`, `.info-tile`, `.toggle-switch`, `.map-supply`, `.detail-actions`, `.truck-status-select`.

**Verificación:** búsqueda literal en `frontend/**/*.html` y `frontend/**/*.js` sin coincidencias (excluyendo build y vendors). Las clases construidas dinámicamente por plantilla (`toast--${type}`) se excluyeron del análisis.

**Recomendación:** eliminar en el paso 2.4 después de confirmar con una búsqueda global y una revisión visual.

---

#### FE-026 · Selector imposible `.brand-name accent` — Baja · Error

**Ubicación:** `frontend/css/layout.css:61-63`.

**Evidencia:**

```css
.brand-name accent { color: var(--color-electric); }
```

**Impacto:** `accent` no es un elemento HTML; el selector nunca coincide. Probablemente se pretendía `<span class="brand-name__accent">`. Es código muerto que sugiere una intención de diseño no implementada.

---

#### FE-027 · Clase `is-ready` sin estilos — Baja · Deuda técnica

**Ubicación:** `frontend/js/core/app.js:160`.

**Evidencia:**

```js
document.documentElement.classList.add("is-ready");
```

**Impacto:** se añade una clase que ninguna hoja usa. O bien falta el CSS que debía revelar la interfaz tras autenticar (riesgo de parpadeo), o es un resto. En el estado actual, la interfaz es visible antes de resolver la sesión.

**Recomendación:** eliminar la clase o implementar el estado de carga asociado.

---

### 5.3 Diseño responsive

#### FE-020 · 13 breakpoints y estrategia desktop-first — Media · Deuda técnica

**Ubicación:** todas las hojas.

**Evidencia (breakpoints por archivo):**

```
components.css  900, 720, 640, 640
layout.css      1120, 900, 640, 1120, 900, 640
ai.css          1100, 960, 720
alerts.css      1100, 700
dashboard.css   1180, 980, 640
driver.css      480, 360
drivers.css     900
login.css       860, 480, 360
routes.css      1050, 900, 640
settings.css    980, 640
truck-detail.css 1050, 640
trucks.css      640
```

**Impacto:** 13 cortes distintos, todos `max-width` (desktop-first). Los cambios de layout no son predecibles entre páginas y `360px` es un breakpoint por debajo de móviles actuales (320–390).

**Recomendación:** 4 cortes mobile-first (`480`, `768`, `1024`, `1280`) definidos en un único lugar documentado.

---

### 5.4 Accesibilidad (WCAG 2.2 AA)

#### FE-002 · Drawer móvil inaccesible — Alta · Error · **Resuelto (0.3)**

**Ubicación:** `frontend/css/layout.css:280-291` y `frontend/js/components/sidebar.js:87-108`.

**Evidencia:**

```css
.sidebar { transform: translateX(-105%); }
body.sidebar-open .sidebar { transform: translateX(0); }
body.sidebar-open .sidebar-overlay { display: block; }
```

```js
const toggle = document.createElement("button");
toggle.setAttribute("aria-label", "Abrir menú de navegación");
toggle.innerHTML = '<i class="fa-solid fa-bars"></i>';
document.body.appendChild(toggle);     // queda al final del DOM, tras <main>
```

**Impacto:** un usuario de teclado recorre todo el contenido antes de alcanzar el botón de menú; el estado abierto/cerrado no se anuncia (`aria-expanded`); los enlaces del sidebar cerrado siguen siendo tabulables (está fuera de pantalla, no oculto); el fondo hace scroll detrás del overlay; el foco no se mueve al menú ni vuelve al botón al cerrar.

**Recomendación:**

```js
toggle.setAttribute("aria-expanded", "false");
toggle.setAttribute("aria-controls", "sidebar");
// insertarlo antes de <main> (o dentro del page-header)
// al abrir: aria-expanded="true", body.style overflow hidden, foco al primer enlace
// al cerrar: aria-expanded="false", foco al toggle
```

y en CSS, para el sidebar cerrado en móvil, `visibility: hidden` / `inert` además de `transform`.

**Corrección aplicada:** el toggle se inserta como primer elemento del `<body>` y anuncia el estado con `aria-expanded` + `aria-controls`; al abrir, el foco va al enlace activo, `.main` recibe `inert` y el `body` bloquea el scroll; el foco queda atrapado entre el toggle y el menú; `Escape`, el overlay y los enlaces cierran devolviendo el foco al toggle. En móvil cerrado, el sidebar combina `visibility: hidden` (con salida animada de 220 ms) e `inert`, de modo que sus enlaces nunca son tabulables. Al pasar a escritorio con el menú abierto, se cierra y se libera `inert`. Verificado en Chromium headless a 375×812 con 25 comprobaciones de estado, foco y tabulación.

---

#### FE-003 · Botones sin nombre accesible — Alta · Error · **Resuelto (0.1)**

**Ubicación original:** `frontend/driver.html:58-67`.

**Evidencia original:**

```html
<button class="btn btn--ghost btn--sm" id="changePasswordButton" type="button">
  <i class="fa-solid fa-key"></i>
</button>
<button class="btn btn--primary btn--sm" id="logoutButton" type="button">
  <i class="fa-solid fa-right-from-bracket"></i>
</button>
```

**Corrección aplicada:** `aria-label="Cambiar contraseña"` y `aria-label="Cerrar sesión"`, con `aria-hidden="true"` en los iconos. `html-validate` ya no reporta `text-content` en este archivo.

---

#### FE-004 · Buscadores sin etiqueta — Alta · Error · **Resuelto (0.1)**

**Ubicación original:** `trucks.html:57,95`; `routes.html:56`.

**Evidencia original:**

```html
<input class="input" id="truckSearch" type="search" placeholder="Buscar por placas, marca o modelo" />
<input class="input" id="routeSearch" type="search" placeholder="Buscar ruta" />
```

**Impacto:** el `placeholder` no es nombre accesible (desaparece al escribir). Incoherencia con `drivers.html:58`, que sí usa `aria-label`, y con `ai.html:151`, que usa `.sr-only`.

**Corrección aplicada:** `aria-label="Buscar camiones"`, `aria-label="Buscar dispositivos IoT"` y `aria-label="Buscar ruta"`.

---

#### FE-005 · Contraste AA insuficiente — Alta · Error · **Resuelto (0.2)**

**Ubicación original:** `tokens.css:33`, `components.css:220-223,1835-1837`, `login.css:314-319`.

**Evidencia y ratios originales:**

| Combinación | Ratio | Uso |
|---|---|---|
| `--text-soft #5b7288` sobre `--bg #e8f1f7` | **4.36** | etiquetas de `ai-usage`, hints (`ai.css:98,110`) |
| `.badge--muted #6b8199` sobre `--offline-soft` + blanco | **3.35** | badge «Sin ruta» (`driver.html:114`) |
| `.badge--muted` en tema oscuro | **3.13** | mismo badge |
| `.login-brand__footer rgba(255,255,255,.6)` sobre `#0b4c9c` | **4.03** | `login.html:40` |

**Nota:** `.badge--danger` se comprobó con su valor final (`#a8232f`, consolidado), que da **5.84** y sí pasa; no se modificó. `.badge--success` (5.18) y `.badge--warning` (5.10) también pasan.

**Corrección aplicada:**

- `--text-soft: #50687e` → **5.07** sobre `--bg` y 5.51 sobre `--surface-soft`.
- Nuevo token `--offline-text: #4f6479` (claro) / `#9fb6c8` (oscuro), usado por `.badge--muted` → **5.11** en claro y **6.00** en oscuro.
- Footer del login a `rgba(255,255,255,.82)` → **6.15**.

---

#### FE-008 · Landmarks `aside` sin nombre único — Media · Error · **Resuelto (1.1)**

**Ubicación:** `dashboard.html:113`, `routes.html:40,48` (y el sidebar de todas las páginas).

**Evidencia:**

```html
<!-- dashboard.html:113 -->
<aside class="dashboard-side">
<!-- routes.html:40 y :48 -->
<aside class="card route-hint" id="routeEditorEmpty">
<aside class="card routes-list-card">
```

**Impacto:** `html-validate` (`unique-landmark`): un lector de pantalla muestra varios «complementary» indistinguibles. Además, tarjetas de contenido usan `<aside>` sin ser contenido complementario.

**Recomendación:** nombrar con `aria-label` los que de verdad sean complementarios y cambiar las tarjetas a `<section>`/`<div>`.

**Corrección aplicada:** el envoltorio del sidebar pasó de `<aside>` a `<div>` en las 9 páginas internas (la navegación ya vive en su `<nav>`); `dashboard-side` pasó a `<div>`; y las dos tarjetas de `routes.html` pasaron a `<section>` (tienen encabezado propio). El único `aside` restante es `ai-history`, que ya está nombrado. `html-validate` ya no reporta `unique-landmark`.

---

#### FE-009 · Patrón `tablist` incompleto — Media · Error

**Ubicación:** `trucks.html:39-46` y `trucks.js:498-518`.

**Evidencia:**

```html
<div class="tabs" role="tablist" aria-label="Secciones de flota">
  <button class="tab is-active" role="tab" data-tab="trucks" aria-selected="true">Camiones</button>
  <button class="tab" role="tab" data-tab="devices" aria-selected="false">Dispositivos IoT</button>
</div>
```

```js
document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => switchTab(button.dataset.tab));
});
```

**Impacto:** faltan `aria-controls`, paneles con `role="tabpanel"` y navegación con flechas/Home/End. El patrón ARIA de tabs está declarado pero no implementado; un usuario de lector de pantalla espera esas teclas y no funcionan.

**Recomendación:** completar el patrón o, si se prefiere simplicidad, sustituirlo por dos enlaces/botones con `aria-pressed` y paneles mostrados/ocultos.

---

#### FE-010 · `role="application"` en los mapas — Media · Riesgo

**Ubicación:** `dashboard.html:79`, `routes.html:129`, `route-detail.html:52`, `truck-detail.html:60`.

**Evidencia:**

```html
<div class="map map--dashboard" id="dashboardMap" role="application" aria-label="Mapa de ubicación de la flota"></div>
```

**Impacto:** `role="application"` hace que el lector entre en modo aplicación y deje de usar sus atajos, pero el mapa Leaflet no ofrece navegación por teclado equivalente. El resultado es una zona que puede atrapar al usuario. Además el `aria-label` de `route-detail` dice «ubicación de la flota» en una página de ruta (texto copiado).

**Recomendación:** eliminar `role="application"`, mantener `aria-label` descriptivo y añadir un resumen textual actualizado (`aria-describedby`) con número de unidades/puntos y un enlace a la tabla o lista equivalente.

---

#### FE-012 · Errores de formulario no asociados — Media · Riesgo · **Resuelto (1.5)**

**Ubicación:** `login.html:48`, `login.js:54-66`, `settings.html:32`, `drivers.html:130`.

**Evidencia:**

```html
<form class="login-form" id="loginForm" novalidate>
```

```js
// login.js:54-66
notify.warning("Ingresa tu usuario o correo y tu contraseña.");
…
notify.error(error.message || "No se pudo iniciar sesión.");
```

**Impacto:** todos los formularios usan `novalidate` y muestran el error solo en un toast. El campo no recibe `aria-invalid` ni `aria-describedby`, y el foco no se mueve al campo problemático. WCAG 3.3.1/3.3.3.

**Recomendación:** un `<p class="field-error" id="identifier-error" role="alert">` junto al campo, `aria-invalid="true"` y `aria-describedby`; enfocar el primer campo inválido.

**Corrección aplicada:** módulo `js/components/form-errors.js` con `setFieldError`, `clearFieldError`, `clearFormErrors` y `focusFirstError`, que inserta `<p class="field-error" role="alert">` dentro del `.form-field`, gestiona `aria-invalid`/`aria-describedby` y limpia al corregir. Se aplicó en `login.js` (2 campos), `settings.js` (8 obligatorios + rangos asociados a su tolerancia) y `drivers.js` (5 obligatorios + formato de correo). En `settings.js` se corrigió además `numberValue`, que convertía un campo vacío en 0 y ocultaba el error. Verificado en Chromium con API simulada.

---

#### FE-013 · Toasts de error y autodescarte — Media · Riesgo · **Resuelto (1.5)**

**Ubicación:** `frontend/js/core/notifications.js:30,52`.

**Evidencia:**

```js
toast.setAttribute("role", "status");
…
const timeout = setTimeout(close, options.duration || 4500);
toast.addEventListener("mouseenter", () => clearTimeout(timeout), { once: true });
```

**Impacto:** los errores usan `role="status"` (cortesía) en lugar de `role="alert"`; el contenedor ya tiene `aria-live="polite"` en el HTML, lo que puede duplicar anuncios. El mensaje desaparece a los 4,5–6 s sin posibilidad de pausarlo con teclado (solo `mouseenter`), y el usuario puede perderse el error.

**Recomendación:** `role="alert"` para errores; pausa en `focusin` además de `mouseenter`; ampliar duración de errores o no autodescartarlos; evitar el doble live region.

**Corrección aplicada:** los errores usan `role="alert"` con `aria-atomic="true"`, no se autodescartan (se elimina su barra de progreso) y el temporizador se pausa en `mouseenter` y `focusin`. Se retiró `aria-live="polite"` de los 10 `#toastRoot` para que el anuncio dependa de cada toast y no se duplique. Verificado: el error sigue visible tras 1,3 s y un toast informativo con el foco puesto también permanece.

---

#### FE-014 · `login` e `index` sin `<main>` y sin skip link — Media · Error · **Resuelto (1.2)**

**Ubicación:** `login.html:23`, `index.html:17`, todas las páginas.

**Evidencia:**

```html
<!-- login.html:23 -->
<div class="login-shell">
  <section class="login-brand" aria-label="FrostBase">…
```

**Impacto:** el contenido principal de login y splash no está dentro de un landmark `main`, por lo que «saltar al contenido» no existe. En las páginas internas no hay skip link: con el sidebar de 7 enlaces, un usuario de teclado tabula por toda la navegación en cada página.

**Recomendación:** añadir `<main>` en login/index y un skip link global (`position:absolute` fuera de pantalla hasta `:focus`) hacia `#main`.

**Corrección aplicada:** `.login-shell` y `.splash` son ahora el `<main>` de sus páginas (misma clase, sin CSS nuevo, centrado intacto a 1280 y 375 px). Las 12 páginas incorporan `<main id="main" tabindex="-1">` y un `<a class="skip-link" href="#main">` como primer elemento del `<body>`, visible al enfocar mediante `transform`. El toggle del drawer se inserta después del skip link. Verificado en Chromium: `Tab` enfoca el skip link, `Enter` mueve el foco a `main` y el drawer mantiene su comportamiento.

---

#### FE-015 · Foco visible eliminado en inputs del asistente — Media · Error · **Resuelto (1.3)**

**Ubicación:** `ai.css:322-325` y `ai.css:484-487`.

**Evidencia:**

```css
.ai-truck-picker__select:focus-visible {
  outline: none;
  border-color: var(--accent-mid);
}
```

**Impacto:** se anula el `outline` global (`base.css:232-235`) y solo cambia el color del borde, un indicador de 1–2 px y bajo contraste. WCAG 2.4.7/2.4.11.

**Recomendación:** mantener el outline (`outline: 2px solid var(--accent-mid); outline-offset: 2px`) o añadir un `box-shadow` de 3 px visible.

**Corrección aplicada:** ambas reglas declaran ahora `outline: 2px solid var(--accent-mid)` con `outline-offset: 2px` y mantienen el `border-color`. Verificado en Chromium: `:focus-visible` coincide en el selector y el textarea, con `outline` sólido de 2 px en `rgb(27, 134, 214)`; la captura del estado enfocado confirma que el anillo es visible.

---

#### FE-016 · Sin `prefers-reduced-motion` — Media · Mejora · **Resuelto (1.4)**

**Ubicación:** `base.css:161-202` (`fadeIn`, `spinner`), `components.css:1229-1301` (`toastIn/Out/Progress`, `modalIn`, `fadeOut`), transiciones en `body` y sidebar.

**Evidencia:** 14 declaraciones `animation:` y transiciones globales; no existe ninguna consulta `prefers-reduced-motion` en el proyecto.

**Impacto:** usuarios con sensibilidad vestibular no pueden desactivar animaciones (WCAG 2.3.3 es AAA, pero es una práctica estándar).

**Recomendación:**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Corrección aplicada:** el bloque vive al final de `base.css` e incluye además `scroll-behavior: auto !important`. Verificado en Chromium: con `reduce`, el spinner pasa de `0.7s infinite` a `1e-05s` y una iteración, y las transiciones de `body`/`.icon-button` de `0.16s`/`0.15s` a `1e-05s`; con `no-preference` se conservan los valores originales. Las 4 declaraciones `!important` están acotadas a este bloque.

---

#### FE-017 · Tablas dinámicas sin anuncio de estado — Baja · Mejora · **Resuelto (1.5)**

**Ubicación:** `frontend/js/components/feedback.js:68-73`.

**Evidencia:**

```js
export function renderTableState(container, html, { onRetry } = {}) {
  container.innerHTML = html;
```

**Impacto:** la carga y los errores de tabla se sustituyen sin anuncio del resultado; un usuario de lector de pantalla no sabe que el contenido cambió. `aria-busy` ya se aplicaba con `setAriaBusy`, por lo que el hueco real era la live region del resultado.

**Recomendación:** `aria-busy="true"` durante la carga y un `<p role="status">` con el resultado («12 camiones cargados», «Error al cargar»).

**Corrección aplicada:** se añadió `role="status"` a los contadores `#trucksCount`, `#devicesCount`, `#driversCount`, `#alertsCount`, `#routesCount` y `#readingsSummary`, de modo que cada actualización del resultado se anuncia. Los errores de carga se anuncian mediante el toast `role="alert"`.

---

### 5.5 Rendimiento

#### FE-028 · CSS bloqueante y fuente de iconos pesada — Media · Deuda técnica

**Ubicación:** `dashboard.html:11-18` (6 `<link rel="stylesheet">`), `assets/vendors/fontawesome/fa-solid-900.woff2` (153,5 KB).

**Evidencia:**

```html
<link rel="stylesheet" href="css/fonts.css" />
<link rel="stylesheet" href="assets/vendors/fontawesome/fa-subset.css" />
<link rel="stylesheet" href="assets/vendors/leaflet/leaflet.css" />
<link rel="stylesheet" href="css/tokens.css" />
<link rel="stylesheet" href="css/base.css" />
<link rel="stylesheet" href="css/components.css" />
<link rel="stylesheet" href="css/layout.css" />
<link rel="stylesheet" href="css/pages/dashboard.css" />
```

**Impacto:** en desarrollo se sirven 8 peticiones; en producción el build las agrupa en 1 (~40 KB minificados), pero sigue siendo render-blocking y `components.css` (38 KB) se carga también en `login`, donde se usa una fracción. La fuente de iconos solid pesa 153 KB y se descarga en todas las páginas.

**Recomendación:** CSS crítico inline para login/dashboard, `preload` del CSS de página, y valorar subset real de FontAwesome (la hoja ya es un subset, pero la fuente no) o iconos SVG inline en la navegación.

---

#### FE-030 · `theme-boot.js` bloqueante — Baja · Mejora

**Ubicación:** `login.html:16` y las otras 11 páginas.

**Evidencia:**

```html
<script src="js/core/theme-boot.js"></script>
```

**Impacto:** 11 líneas de JS en `<head>` sin `defer` (necesario para evitar el destello de tema) añaden una petición bloqueante antes del primer pintado.

**Recomendación:** inline del script con hash en la CSP, o un `<script>` mínimo inline permitido por `script-src 'sha256-…'`.

---

#### FE-031 · Logo PNG de 71 KB como logo y favicon — Baja · Mejora

**Ubicación:** `assets/logo.png`; `login.html:8,27`; `sidebar.js:43`.

**Impacto:** se descarga el mismo PNG grande para el favicon, el logo del login (72×72) y el logo del sidebar (40×40). No hay formato vectorial ni `srcset`.

**Recomendación:** SVG para el logo, `favicon-32.png` + `apple-touch-icon` para el icono, y mantener el PNG solo como fallback.

---

### 5.6 UI/UX y consistencia visual

#### FE-024 · Pesos tipográficos fuera del rango de la fuente — Media · Riesgo

**Ubicación:** `fonts.css:5`, `base.css:42-49`, `components.css:1665-1669`.

**Evidencia:**

```css
@font-face {
  font-family: "Outfit";
  font-weight: 400 700;   /* rango variable disponible: 400–700 */
}
h1, h2, h3, h4 { font-weight: 900; }
.card__title  { font-weight: 900; }
```

**Impacto:** la UI pide 800 y 900 en 13 declaraciones. El navegador sintetiza la negrita por encima de 700: el trazo engorda de forma distinta en cada motor y los titulares pierden definición. Además contradice el sistema de diseño.

**Recomendación:** usar 700 como máximo o cargar el eje `wght` completo del variable font (comprobando peso del archivo).

---

### 5.7 Compatibilidad entre navegadores

#### FE-029 · `100vh` en 9 sitios — Media · Riesgo

**Ubicación:** `base.css:18`, `components.css:1277,1619`, `layout.css:2`, `ai.css:6,235`, `driver.css:4`, `index.css:6`, `login.css:2`.

**Evidencia:**

```css
.modal { max-height: calc(100vh - 40px); }
```

**Impacto:** en Safari iOS la barra de direcciones dinámica hace que `100vh` sea mayor que el viewport visible: modales cortados y saltos al hacer scroll. El login con `min-height: 100vh` puede provocar scroll innecesario.

**Recomendación:** `100dvh` con fallback (`min-height: 100vh; min-height: 100dvh;`) y `calc(100dvh - 40px)` en modales.

---

#### FE-032 · Ruta de fuente absoluta vs. preload relativa — Baja · Riesgo

**Ubicación:** `fonts.css:7` vs `login.html:9` (y todas las páginas).

**Evidencia:**

```css
/* fonts.css:7 */
src: url("/assets/fonts/outfit-latin.woff2") format("woff2");
```

```html
<link rel="preload" href="assets/fonts/outfit-latin.woff2" as="font" type="font/woff2" crossorigin />
```

**Impacto:** hoy ambas resuelven a la misma URL porque la app se sirve en la raíz. Si se despliega bajo un subpath, el CSS pedirá `/assets/...` (fuera de la app) y el preload `assets/...` (correcto): doble descarga o fuente rota.

**Recomendación:** unificar a ruta relativa (`../fonts/outfit-latin.woff2` o reescribirla en el build).

---

### 5.8 SEO y metadatos

No se identifican problemas relevantes: la aplicación es interna y todas las páginas llevan `noindex, nofollow` de forma intencionada; los `title` son únicos y descriptivos y todas incluyen `meta description` salvo `index.html` (splash de redirección, cubierto por FE-007). No hay `canonical` ni Open Graph, coherente con el carácter privado.

### 5.9 Seguridad básica en el cliente

Sin hallazgos. No hay `target="_blank"`, no se cargan recursos externos, todo el vendorizado es local, no hay HTTP mixto y el servidor envía CSP, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` y `Permissions-Policy` (`backend/app/main.py:134-140`). Las interpolaciones de datos usan `escapeHtml` (`helpers.js`, `notifications.js`, `feedback.js`). Única observación: `modal.js:119-127` duplica `escapeHtml` (FE-035).

### 5.10 Mantenibilidad

#### FE-033 · `<head>` duplicado en 12 páginas — Media · Deuda técnica

**Ubicación:** todas las `.html` (16 líneas de metas, preload, 8 hojas, theme-boot).

**Impacto:** añadir una hoja o cambiar el preload implica editar 12 archivos a mano; ya hay divergencias (unas páginas cargan `layout.css` y otras no, `index.html` no tiene `components.css`). Es la causa de que `driver.html` se quedara sin `<h1>` y los buscadores sin etiqueta.

**Recomendación:** parcial de `<head>` en el build (11ty, Vite o un `include` casero en `scripts/build.mjs`).

---

#### FE-034 · Linters incompletos — Baja · Deuda técnica

**Ubicación:** `frontend/scripts/check-css.mjs:44` y `frontend/package.json:6-10`.

**Evidencia:**

```js
const duplicates = [...owners.entries()].filter(([, list]) => list.length > 1);
```

**Impacto:** el script solo detecta selectores repetidos **entre archivos**; los 130 duplicados internos (el problema real) pasan desapercibidos. No hay `stylelint` ni `html-validate` en `package.json` ni en CI.

**Recomendación:** configurar ambos y añadir `no-duplicate-selectors`, `declaration-block-no-duplicate-properties` y `shorthand-property-no-redundant-values`.

---

#### FE-035 · `escapeHtml` duplicado — Baja · Deuda técnica

**Ubicación:** `modal.js:119-127` vs `core/helpers.js`.

**Impacto:** dos implementaciones de saneado; un cambio de seguridad en una no se propaga a la otra.

**Recomendación:** importar el helper compartido.

---

#### FE-036 · Cobertura y umbral de la suite a11y — Baja · Riesgo

**Ubicación:** `tests/e2e/accessibility.spec.js:4-12,16-19`.

**Evidencia:**

```js
const PAGES = ["dashboard.html","trucks.html","drivers.html","routes.html","alerts.html","settings.html","ai.html"];
…
["serious", "critical"].includes(violation.impact)
```

**Impacto:** no se prueban `login`, `driver`, `index`, `truck-detail` ni `route-detail`, y los impactos `moderate` (p. ej. `region`, `heading-order`) no hacen fallar el test. Con FE-004 sin corregir, es probable que la suite estuviera en rojo (regla `label`, impacto *critical*); **no verificado** por requerir el stack levantado.

**Recomendación:** cubrir las 12 páginas y ambos temas, y bajar el umbral a `moderate`.

---

## 6. Puntos fuertes (conservar)

1. **Sistema de tokens real**: 73 custom properties, tema oscuro completo, solo 3 sin uso.
2. **Cero estilos en línea** y solo **3 `!important`** en utilidades de ocultación, más 4 acotados al bloque de movimiento reducido.
3. **Build sólido**: CSS agrupado y minificado por página, JS bundleado, hashes y caché `immutable`; Docker lo ejecuta en producción.
4. **Seguridad de cliente bien encaminada**: CSP y cabeceras en servidor, sin CDNs, sin `target="_blank"`, `escapeHtml` en las interpolaciones.
5. **Accesibilidad de base**: `focus-visible` global, `.sr-only`, `aria-current`, `role="dialog"` + `aria-modal` + focus trap funcional (`modal.js:16-63`), imágenes con `width`/`height`.
6. **Responsive sensato en lo esencial**: `overflow-x: auto` en tablas, grids fluidos con `minmax(0,1fr)`, `clamp()` en titulares, sidebar colapsable.
7. **Rendimiento de fuentes correcto**: un solo woff2, `font-display: swap` y `preload`.
8. **Tests de accesibilidad y CSP ya presentes**, lo que permite convertir las mejoras en regresiones detectables.

---

## 7. Limitaciones de la auditoría

- **No verificado en navegador real**: no se comprobó renderizado, desbordamientos ni CLS. Requiere levantar el stack (`docker compose up`) y revisar breakpoints. Los ratios de contraste sí están calculados numéricamente.
- **No verificado**: si la suite Playwright pasa hoy. No se ejecutó el stack ni Lighthouse; se sospecha fallo en `routes.html` por el input sin etiqueta (FE-004, ya corregido).
- `stylelint` se ejecutó con una configuración temporal en `%TEMP%`. Reportó 171 avisos: 130 `no-duplicate-selectors` y el resto estilo (longitud de hex, nombres de `@keyframes`, prefijo `-webkit-`).
- `html-validate` reportó 242 problemas, de los cuales 198 son `void-style`/`doctype-style` (convención de autocierre, no errores HTML5). Los 44 restantes son los hallazgos reales.
- No se auditó `frontend/build` (generado), `assets/vendors` ni el backend, salvo CSP y cabeceras.
- El contexto inicial del proyecto venía con campos de plantilla sin rellenar; los supuestos aplicados están declarados al inicio.
