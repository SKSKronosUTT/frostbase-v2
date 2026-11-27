# Guía de estilos y desarrollo frontend — FrostBase

**Última actualización:** 2026-11-26
**Alcance:** `frontend/*.html`, `frontend/css/**`, `frontend/js/**`, `frontend/partials/**` y `frontend/scripts/**`.
**Referencias:** [`docs/auditoria-frontend.md`](auditoria-frontend.md), [`docs/plan-mejora.md`](plan-mejora.md) y [`frontend/README.md`](../frontend/README.md).

Esta guía explica cómo construir una página o un componente nuevo sin tener que leer todo el CSS existente. Si algo no encaja en lo que hay aquí, primero revisa si el patrón ya existe en `components.css`; si no, documenta la excepción en el PR.

---

## 1. Principios

1. **Sin framework ni preprocesador.** HTML, CSS y JavaScript ES modules nativo. El build usa esbuild.
2. **El diseño vive en tokens.** Colores, tipografía, espaciado, sombras y transiciones salen de `css/tokens.css`. No se escriben colores hexadecimales fuera de ese archivo.
3. **Accesibilidad por defecto.** Landmarks, foco visible, teclado, etiquetas, contraste y `prefers-reduced-motion` no son un extra.
4. **Rendimiento medible.** Una sola hoja CSS por página, tema sin parpadeo, LCP < 2,5 s y CLS < 0,1 como objetivos.
5. **Estética Bauhaus.** Bordes rectos, sombras duras, mayúsculas en titulares y azul frío como acento. No introduzcas radios suaves, degradados ni sombras difusas sin hablarlo.

---

## 2. Estructura del proyecto

```text
frontend/
├─ partials/
│  ├─ head.html              # único <head> (metas, iconos, preload, hojas)
│  └─ sidebar.html           # navegación lateral compartida
├─ pages.config.json         # título, descripción y hojas por página
├─ *.html                    # 12 plantillas de página
├─ css/
│  ├─ tokens.css             # variables de diseño
│  ├─ fonts.css              # @font-face de Outfit
│  ├─ base.css               # reset, tipografía base y utilidades
│  ├─ components.css         # componentes compartidos y estados
│  ├─ layout.css             # shell, sidebar, cabecera, breakpoints globales
│  └─ pages/*.css            # estilos específicos de cada página
├─ js/
│  ├─ core/                  # api, auth, tema, helpers, notificaciones, shell
│  ├─ components/            # modal, feedback, formularios, mapa, paginación
│  └─ pages/                 # un módulo por página
├─ assets/                   # logo, iconos y fuentes
├─ tools/                    # vendorización de Leaflet/FontAwesome/Outfit
└─ scripts/                  # build y checks
```

Las páginas de `frontend/*.html` son **plantillas**: el `<head>` y el sidebar viven en `partials/` y el build los resuelve. El backend sirve `frontend/build`; el servidor no renderiza las plantillas.

---

## 3. Build y parciales

`npm run build`:

1. Lee `pages.config.json` (orden de páginas, `title`, `description`, `styles`).
2. Resuelve `<!-- @include head -->` y `<!-- @include sidebar -->`.
3. Marca el enlace activo del sidebar con `is-active` y `aria-current="page"`.
4. Fusiona **todo el CSS de la página** (vendor + app) en una sola hoja, reescribe las URL relativas de fuentes e imágenes y la hashea.
5. Minifica y hashea el bundle JS de la página.
6. Inlinea el script de tema (`theme-boot`) y escribe `build/csp.json` con su hash SHA-256.
7. Genera `build/` y `manifest.json`.

No añadas `<link rel="stylesheet">` directamente a una página: declara las hojas en `pages.config.json`. El orden importa: primero `fonts.css`, después los vendor (`fontawesome`, `leaflet`), `tokens.css`, `base.css`, `components.css`, `layout.css` y al final `css/pages/<pagina>.css`.

`npm run build` es obligatorio antes de abrir la app en local. `make dev` y la imagen Docker lo ejecutan solos.

---

## 4. Tokens

### 4.1 Color

Los colores semánticos están en `tokens.css` y cambian automáticamente con `[data-theme="dark"]`.

| Token                                                  | Uso                           |
| ------------------------------------------------------ | ----------------------------- |
| `--bg`, `--bg-soft`                                    | Fondo de página y variantes   |
| `--surface`, `--surface-soft`, `--surface-muted`       | Tarjetas y paneles            |
| `--text`, `--text-muted`, `--text-soft`                | Texto principal y secundarios |
| `--ink`, `--border-ink`, `--border`, `--border-strong` | Bordes, contornos y sombras   |
| `--accent-deep`, `--accent-mid`, `--accent-frost`      | Marca y acentos               |
| `--success`, `--warning`, `--danger`, `--offline`      | Estados                       |
| `--sidebar*`                                           | Navegación lateral            |

Reglas:

- Usa el token semántico, no el color físico (`--danger`, no `#c9404c`).
- Para fondos suaves de estado usa `--success-soft`, `--danger-soft`, etc.
- No añadas un color nuevo sin tokens claro/oscuro y sin comprobar contraste AA.
- Las excepciones de tema se escriben como `[data-theme="dark"] .bloque { … }`, nunca duplicando toda la regla.

### 4.2 Tipografía

La familia es **Outfit** (variable, `wght` 100–900) con fallback del sistema. El rango completo está declarado en `fonts.css`; los titulares usan 900 real, no negrita sintética.

| Token         | Valor | Uso típico                      |
| ------------- | ----- | ------------------------------- |
| `--text-xs`   | 11 px | Etiquetas, `eyebrow`, metadatos |
| `--text-sm`   | 12 px | Hints, badges, tablas compactas |
| `--text-md`   | 13 px | Texto de tablas y ayudas        |
| `--text-base` | 14 px | Texto base del `body`           |
| `--text-lg`   | 16 px | `h3`, subtítulos                |
| `--text-xl`   | 20 px | `h2`                            |
| `--text-2xl`  | 26 px | `h1` base                       |
| `--text-3xl`  | 32 px | Cifras destacadas               |

- El `h1` de una página interna usa `.page-header__title h1` (`clamp(30px, 4vw, 46px)`).
- Los `h1`–`h4` son mayúsculas, peso 900 y `letter-spacing: -0.02em`; no los redefinas por página.
- No uses `font-size` en px fuera de los tokens. Para un tamaño nuevo, añade un token y justifica el paso.
- Los pesos disponibles son 400, 500, 600, 700, 800 y 900. No pidas 850 ni 950.

### 4.3 Espaciado

Escala de 12 pasos (base 2/4 px): `--space-1` 2 px, `--space-2` 4, `--space-3` 6, `--space-4` 8, `--space-5` 10, `--space-6` 12, `--space-7` 14, `--space-8` 16, `--space-9` 20, `--space-10` 24, `--space-11` 32, `--space-12` 40.

- `padding`, `margin`, `gap` y posiciones usan tokens.
- Los valores estructurales (anchos de sidebar, bordes de 2–4 px, alturas de mapa) pueden quedar en px.
- No inventes `13px` o `18px` para espaciado: usa el paso más cercano o añade un token si el patrón se repite.

### 4.4 Forma, sombra y movimiento

- `--radius-*` son 0 px (estilo Bauhaus); solo `--radius-pill` es 999 px para píldoras.
- Sombras: `--shadow-sm/md/lg` (duras, sin desenfoque).
- `--transition: 160ms ease-out`. Respeta `prefers-reduced-motion`.
- `--viewport-height`: **no uses `100vh`**. Usa este token (`100vh` con mejora a `100dvh`), también dentro de `calc()`.

---

## 5. CSS: organización y convenciones

### 5.1 Nombres

Se usa **BEM parcial**:

```css
.bloque {
}
.bloque__elemento {
}
.bloque--modificador {
}
.estado.is-activo {
}
.utilidad {
}
```

- Bloques en minúsculas y kebab-case: `.kpi-card`.
- Elementos con `__`: `.kpi-card__label`.
- Modificadores con `--`: `.btn--primary`, `.badge--danger`.
- Estados con `is-`: `.is-active`, `.is-offline`, `.is-visible`.
- No anides selectores más de dos niveles ni uses IDs para estilos.
- No uses `!important` salvo en `.hidden`/`[hidden]` y en el bloque de movimiento reducido.

### 5.2 Dónde va cada estilo

| Archivo              | Contenido                                                            |
| -------------------- | -------------------------------------------------------------------- |
| `tokens.css`         | Variables nuevas                                                     |
| `base.css`           | Reset, `body`, titulares, enlaces, utilidades, foco y reduced motion |
| `components.css`     | Componentes reutilizables y sus estados                              |
| `layout.css`         | Shell, sidebar, cabecera, `.main` y media queries globales           |
| `pages/<pagina>.css` | Solo lo específico de esa página                                     |

Si un componente se usa en dos páginas, muévelo a `components.css`.

### 5.3 Breakpoints

Los únicos cortes permitidos son **480, 768, 1024 y 1280 px**. La estrategia actual es `max-width` (desktop-first); la inversión completa a `min-width` es el paso pendiente **2.3b**. Mientras tanto:

- No añadas breakpoints nuevos.
- Reutiliza uno de los cuatro valores.
- Comprueba 320, 390, 480, 768, 1024, 1280 y 1440 px.
- En móvil, el sidebar es un drawer; no dupliques su lógica.

### 5.4 Interacción y foco

Todo control debe tener estados claros:

```css
.mi-control { … }
.mi-control:hover { … }
.mi-control:focus-visible { … }
.mi-control:active { … }
.mi-control:disabled { opacity: 0.55; cursor: not-allowed; }
.mi-control[aria-invalid="true"] { border-color: var(--danger); }
```

El foco global (`:focus-visible`) ya dibuja un contorno azul de 2 px con offset 3 px. No lo elimines; si un componente necesita otro, mantén el contraste y el offset.

---

## 6. Componentes base

### 6.1 Botones

```html
<button class="btn btn--primary" type="button">Guardar</button>
<button class="btn btn--ghost btn--sm" type="button">Cancelar</button>
<button class="btn btn--danger" type="button">Eliminar</button>
<button class="icon-button" type="button" aria-label="Editar camión">
  <i class="fa-solid fa-pen" aria-hidden="true"></i>
</button>
```

- Modificadores: `--primary`, `--ghost`, `--danger`, `--sm`, `--block`, `--spaced-top`.
- `type="button"` siempre que no envíe un formulario.
- Un botón solo-icono **necesita** `aria-label`; el icono lleva `aria-hidden="true"`.
- Para carga usa `setButtonLoading(button, true, "Guardando.")` de `core/helpers.js`.

### 6.2 Tarjetas

```html
<article class="card">
  <header class="card__header">
    <div>
      <h2 class="card__title">Título</h2>
      <p class="card__subtitle">Contexto breve</p>
    </div>
  </header>
  <div class="card__body">…</div>
</article>
```

Usa `article` para contenido autocontenido y `section` para agrupar contenido con título. No uses `div` si existe un elemento semántico.

### 6.3 Formularios

```html
<form class="form-grid" id="miForm" novalidate>
  <div class="form-field">
    <label for="campo">Etiqueta</label>
    <input class="input" id="campo" name="campo" required />
    <p class="hint">Texto de ayuda opcional.</p>
  </div>
  <div class="form-field form-field--full">
    <label for="notas">Notas</label>
    <textarea class="textarea" id="notas"></textarea>
  </div>
</form>
```

- `.form-grid` = 2 columnas; `.form-grid--3` = 3; `.form-field--full` ocupa todo el ancho.
- Usa `label for` siempre. No uses el placeholder como etiqueta.
- Para errores, importa de `components/form-errors.js`:

```js
import {
  clearFormErrors,
  focusFirstError,
  setFieldError,
} from "../components/form-errors.js";

setFieldError(input, "Ingresa un valor válido.");
focusFirstError(form);
// al corregir el campo, el helper limpia aria-invalid y el mensaje
```

`setFieldError` añade `aria-invalid="true"`, `aria-describedby` y un `role="alert"`. No dupliques esa lógica a mano.

### 6.4 Tablas

```html
<div
  class="table-wrap"
  role="region"
  aria-label="Listado de camiones"
  tabindex="0"
>
  <table class="table">
    <thead>
      <tr>
        <th scope="col">Placas</th>
        <th scope="col">Estado</th>
      </tr>
    </thead>
    <tbody id="miTablaBody">
      <tr>
        <td>ABC-123</td>
        <td>En ruta</td>
      </tr>
    </tbody>
  </table>
</div>
```

- **Todo `<th>` necesita `scope="col"` o `scope="row"`.** `html-validate` falla si falta.
- El `.table-wrap` es una región con nombre y `tabindex="0"`: si la tabla desborda, se recorre con flechas.
- Para tablas compactas usa `.table--compact`.
- Para estados de carga/error usa `renderTableState`, `tableSkeleton`, `emptyRow`, `tableError` y `setAriaBusy` de `components/feedback.js`.

### 6.5 Badges y estados

```html
<span class="badge badge--success">En ruta</span>
<span class="badge badge--warning">Mantenimiento</span>
<span class="badge badge--danger">Fuera de rango</span>
<span class="status-dot is-online"></span>
```

No comuniques un estado **solo** con color: añade texto o un icono con etiqueta.

### 6.6 Tabs

```html
<div class="tabs" role="tablist" aria-label="Secciones de flota">
  <button
    class="tab is-active"
    role="tab"
    id="tab-camiones"
    aria-selected="true"
    aria-controls="panel-camiones"
    data-tab="camiones"
  >
    Camiones
  </button>
  <button
    class="tab"
    role="tab"
    id="tab-dispositivos"
    aria-selected="false"
    aria-controls="panel-dispositivos"
    tabindex="-1"
    data-tab="dispositivos"
  >
    Dispositivos IoT
  </button>
</div>
<div id="panel-camiones" role="tabpanel" aria-labelledby="tab-camiones">…</div>
<div
  id="panel-dispositivos"
  role="tabpanel"
  aria-labelledby="tab-dispositivos"
  hidden
>
  …
</div>
```

El patrón de teclado ya está implementado en `pages/trucks.js`: flechas, Home/End, `aria-selected` y roving `tabindex`.

### 6.7 Modales

```html
<div class="modal-overlay hidden" id="miModal">
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="miModalTitle"
  >
    <header class="modal__header">
      <h2 id="miModalTitle">Título</h2>
      <button
        class="icon-button modal__close"
        type="button"
        aria-label="Cerrar"
      >
        <i class="fa-solid fa-xmark" aria-hidden="true"></i>
      </button>
    </header>
    <div class="modal__body">…</div>
    <footer class="modal__footer">…</footer>
  </div>
</div>
```

Activa el foco y Escape con `activateModal(overlay, { onClose, initialFocus })` de `components/modal.js`; no implementes otro focus trap. Para confirmaciones usa `confirmDialog`.

### 6.8 Avisos y toasts

```js
import { notify } from "../core/notifications.js";

notify.success("Cambios guardados.");
notify.error("No se pudo guardar.");
```

Los errores usan `role="alert"` y no se autodescartan; el resto usa `role="status"`. No crees toasts con `innerHTML` sin `escapeHtml`.

### 6.9 Sidebar y navegación

- El marcado está en `partials/sidebar.html`.
- Cada enlace lleva `data-nav="<clave>"`; el build marca `is-active` y `aria-current="page"` según el nombre de la página.
- Para una página de detalle, añade el alias en `SIDEBAR_ALIASES` de `scripts/build.mjs` (`truck-detail → trucks`, `route-detail → routes`).
- El drawer móvil, `inert`, el foco atrapado y Escape viven en `components/sidebar.js`; no los dupliques.

### 6.10 Mapas

- Usa `createMap(id, { center, zoom, lazy })` de `components/map.js`.
- El contenedor debe ser `role="region"` con `aria-label` y `aria-describedby` a un resumen textual actualizado.
- `lazy: true` difiere las teselas hasta que el mapa es visible (dashboard); úsalo solo en mapas bajo el pliegue.
- Añade un resumen con el número de unidades/puntos o la ubicación. No dejes el mapa como única fuente de información.

---

## 7. Accesibilidad

Checklist mínimo para cualquier página o componente:

- [ ] Un solo `<main id="main" tabindex="-1">` y un `<h1>` por página.
- [ ] Skip link como primer elemento: `<a class="skip-link" href="#main">Saltar al contenido</a>`.
- [ ] Landmarks: `<nav aria-label="Navegación principal">`, secciones con `aria-label` si no tienen título visible.
- [ ] Jerarquía de encabezados sin saltos (`h1 → h2 → h3`).
- [ ] Formularios con `label for`, `aria-invalid`/`aria-describedby` en error y foco en el primer error.
- [ ] Botones solo-icono con `aria-label`; iconos decorativos con `aria-hidden="true"`.
- [ ] Tablas con `th scope` y contenedor `.table-wrap` enfocable.
- [ ] Modales con `role="dialog"`, `aria-modal`, `aria-labelledby`, foco atrapado y Escape.
- [ ] Mensajes dinámicos en `role="status"` o `role="alert"`.
- [ ] Foco visible; no elimines `:focus-visible`.
- [ ] Contraste AA con tokens (revisa ambos temas).
- [ ] `prefers-reduced-motion` respetado.
- [ ] Mapas con `role="region"`, nombre y resumen textual.

La suite `tests/e2e/accessibility.spec.js` audita las 12 páginas en ambos temas con umbral `moderate` y prueba skip link, drawer, tabs y errores de login.

---

## 8. Rendimiento

- El build deja **una hoja CSS por página**; no añadas hojas sueltas al HTML.
- El tema va inline con hash CSP (`build/csp.json`); no vuelvas a cargar `theme-boot.js` como script externo.
- Las imágenes llevan `width`/`height`. Usa `logo-160.png` (no el PNG maestro de 1123 px) y los iconos `favicon-32`/`apple-touch-icon`.
- Los mapas bajo el pliegue usan `lazy: true`.
- No añadas dependencias de runtime sin justificar peso y licencia; los vendors se generan con `tools/vendor_assets.py`.
- Objetivos: LCP < 2,5 s en 4G simulada, CLS < 0,1 y CSP sin violaciones. Mide con Lighthouse y la suite E2E.
- Para animaciones nuevas, usa `--transition` y comprueba `prefers-reduced-motion`.

---

## 9. Crear una página nueva

Ejemplo: una página interna `reports.html`.

### 9.1 Plantilla

```html
<!DOCTYPE html>
<html lang="es" data-theme="light">
  <head>
    <!-- @include head -->
  </head>
  <body data-page="reports">
    <a class="skip-link" href="#main">Saltar al contenido</a>
    <div class="app-shell">
      <div class="sidebar" id="sidebar">
        <!-- @include sidebar -->
      </div>
      <main id="main" tabindex="-1" class="main">
        <header class="page-header">
          <div class="page-header__title">
            <span class="eyebrow">Operación</span>
            <h1>Reportes</h1>
            <p class="page-header__subtitle">Descripción breve de la página.</p>
          </div>
        </header>

        <section class="card" aria-label="Contenido de reportes">
          <header class="card__header">
            <h2 class="card__title">Título de la sección</h2>
          </header>
          <div class="card__body">…</div>
        </section>
      </main>
    </div>
    <script type="module" src="js/pages/reports.js"></script>
  </body>
</html>
```

Las páginas públicas (login, splash) no llevan sidebar ni `app-shell`; el portal del conductor usa `driver-shell`.

### 9.2 Configuración

Añade la entrada en `pages.config.json`:

```json
"reports.html": {
  "title": "Reportes | FrostBase",
  "description": "Reportes operativos de la flota FrostBase.",
  "styles": [
    "css/fonts.css",
    "assets/vendors/fontawesome/fa-subset.css",
    "css/tokens.css",
    "css/base.css",
    "css/components.css",
    "css/layout.css",
    "css/pages/reports.css"
  ]
}
```

Si la página usa mapas, añade `assets/vendors/leaflet/leaflet.css` antes de `tokens.css`.

### 9.3 CSS y JS

- Crea `css/pages/reports.css` solo con lo específico.
- Crea `js/pages/reports.js`:

```js
import { initProtectedPage } from "../core/app.js";

async function init() {
  await initProtectedPage();
  // carga de datos, eventos y render
}

init();
```

Para páginas públicas no llames a `initProtectedPage`; para el portal del conductor usa el patrón de `pages/driver.js`.

### 9.4 Navegación

Añade el enlace en `partials/sidebar.html`:

```html
<a class="nav-link" data-nav="reports" href="reports.html">
  <i class="fa-solid fa-chart-column" aria-hidden="true"></i>
  <span>Reportes</span>
</a>
```

El icono debe existir en el subset de FontAwesome. Si no, ejecuta `python tools/vendor_assets.py` con las dependencias de desarrollo.

### 9.5 Verificación

```bash
cd frontend
npm run build
npm run lint
npm run verify
npx playwright test
```

Comprueba además:

- navegación sin JS (el sidebar está en el HTML);
- ambos temas;
- 320–1440 px y el drawer móvil;
- foco con Tab, skip link y formularios;
- `html-validate` sin errores y `csp.spec.js` sin violaciones.

---

## 10. Crear un componente

1. Elige un bloque con nombre kebab-case (`status-chip`).
2. Añade el CSS a `components.css` con `__elemento` y `--modificador`; usa tokens.
3. Define estados `:hover`, `:focus-visible`, `:active`, `:disabled` y `[aria-invalid]` si aplica.
4. Comprueba el tema oscuro; si hace falta un ajuste, usa `[data-theme="dark"] .status-chip` y un token, no un color nuevo.
5. Incluye el marcado accesible (rol, etiqueta, texto alternativo, `aria-live` si cambia).
6. Añade el componente a esta guía si es reutilizable.
7. Verifica en las 12 páginas o al menos en las que lo usan, en ambos temas y anchos.

Ejemplo mínimo:

```css
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  border: 2px solid var(--border-ink);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  font-weight: 700;
  text-transform: uppercase;
}

.status-chip--warning {
  background: var(--warning-soft);
  color: var(--warning-text);
}

[data-theme="dark"] .status-chip--warning {
  color: var(--warning);
}

.status-chip__dot {
  width: 8px;
  height: 8px;
  background: currentColor;
  border-radius: var(--radius-pill);
}
```

---

## 11. Checklist de PR

- [ ] La página/componente funciona en claro y oscuro.
- [ ] Sin colores hexadecimales fuera de `tokens.css`; sin `font-size` en px.
- [ ] Sin breakpoints nuevos (480/768/1024/1280).
- [ ] Sin `!important` nuevo (salvo utilidades justificadas).
- [ ] `npm run lint` y `npm run verify` en verde.
- [ ] `npx playwright test` en verde (o justificación si no aplica).
- [ ] `html-validate` sin errores: `<th scope>`, IDs únicos, doctype.
- [ ] CSP sin violaciones; sin scripts inline nuevos (el tema ya está resuelto con hash).
- [ ] Accesibilidad: foco, teclado, etiquetas, `aria-live`, contraste.
- [ ] Rendimiento: sin hojas extra, imágenes con tamaño, mapas bajo el pliegue con `lazy`.
- [ ] `pages.config.json` y `partials/sidebar.html` actualizados si es página nueva.
- [ ] Documentación actualizada (esta guía, README o plan) si cambia un patrón.

---

## 12. Comandos útiles

```bash
cd frontend
npm ci
npm run build        # genera build/ y csp.json
npm run lint         # ESLint, Prettier, Stylelint, duplicados y escape HTML
npm run lint:html    # html-validate sobre build/*.html (requiere build)
npm run verify       # lint + build + html-validate
npx playwright test  # suite E2E completa
```

Desde la raíz:

```bash
make lint
make build
make e2e
```

o en Windows:

```powershell
.\tasks.ps1 lint
.\tasks.ps1 build
.\tasks.ps1 e2e
```

---

## 13. Anti-patrones

- Copiar el `<head>` o el sidebar a una página nueva: usa los parciales.
- Añadir una hoja CSS con `<link>` en el HTML: declárala en `pages.config.json`.
- Usar `100vh`: usa `var(--viewport-height)`.
- Escribir `innerHTML` con datos de la API sin `escapeHtml`; `npm run check:html` lo detecta.
- Crear un modal o drawer con lógica de foco propia: reutiliza `modal.js`/`sidebar.js`.
- Poner un `<div>` clicable en lugar de `<button>`.
- Ocultar contenido con `display:none` cuando debe ser accesible: usa `.sr-only`.
- Añadir un icono nuevo sin regenerar el subset de FontAwesome.
- Introducir un color o una sombra “a mano” que no exista en tokens.

---

## 14. Referencias

- [`frontend/README.md`](../frontend/README.md): arranque y comandos del frontend.
- [`docs/auditoria-frontend.md`](auditoria-frontend.md): hallazgos y correcciones.
- [`docs/plan-mejora.md`](plan-mejora.md): estado de las fases y pendientes.
- `frontend/css/tokens.css`: fuente de verdad de los tokens.
- `frontend/partials/` y `frontend/pages.config.json`: shell de página.
- `frontend/tests/e2e/accessibility.spec.js`: ejemplos de pruebas de foco y axe.
