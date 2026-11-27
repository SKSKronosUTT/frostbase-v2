# Frontend — FrostBase

Panel web multipágina en HTML, CSS y JavaScript nativo. Sin framework ni preprocesador; el build usa **esbuild**. La app consume la API de `backend/` y se sirve como estáticos desde `frontend/build`.

La guía completa de tokens, componentes, accesibilidad y recetas está en [`docs/guia-estilos.md`](../docs/guia-estilos.md).

## Requisitos

- Node.js 20+
- npm

## Arranque

```bash
cd frontend
npm ci
npm run build
```

El backend sirve `frontend/build`. `make dev` y `docker/Dockerfile` ejecutan el build automáticamente. **Las páginas de `frontend/*.html` son plantillas** (`partials/head.html` y `partials/sidebar.html`); abrirlas directamente no carga CSS ni navegación.

## Estructura

```text
partials/head.html        <head> único
partials/sidebar.html     navegación lateral
pages.config.json         título, descripción y hojas por página
*.html                    plantillas de página
css/tokens.css            variables de diseño
css/base.css              reset, tipografía, utilidades
css/components.css        componentes compartidos
css/layout.css            shell, sidebar, cabecera
css/pages/*.css           estilos específicos
js/core/                  api, auth, tema, helpers, notificaciones
js/components/            modal, feedback, formularios, mapa, paginación
js/pages/                 módulo de cada página
scripts/build.mjs         build (incluye parciales y bundles)
scripts/check-*.mjs       checks de CSS y de HTML escapado
tests/e2e/                Playwright (flujos y accesibilidad)
```

## Comandos

| Comando               | Qué hace                                                                              |
| --------------------- | ------------------------------------------------------------------------------------- |
| `npm run build`       | Genera `build/` con páginas resueltas, CSS/JS hasheados, `manifest.json` y `csp.json` |
| `npm run lint`        | ESLint, Prettier, Stylelint, duplicados de CSS y escape de HTML                       |
| `npm run lint:html`   | `html-validate` sobre `build/*.html` (requiere build)                                 |
| `npm run verify`      | `lint` + build + `html-validate`                                                      |
| `npx playwright test` | Suite E2E completa (requiere el stack en `http://127.0.0.1:8050`)                     |

En la raíz también están `make lint`, `make build` y `make e2e` (o `.\tasks.ps1 lint|build|e2e`).

## Pages y parciales

1. Crea `mi-pagina.html` con `<!-- @include head -->`, el shell y `<!-- @include sidebar -->` si es interna.
2. Añade su entrada a `pages.config.json` con `title`, `description` y `styles`.
3. Añade `css/pages/mi-pagina.css` y `js/pages/mi-pagina.js`.
4. Añade el enlace en `partials/sidebar.html` con `data-nav="mi-pagina"`.
5. Si es una página de detalle, añade el alias en `SIDEBAR_ALIASES` de `scripts/build.mjs`.
6. Ejecuta `npm run verify` y `npx playwright test`.

El paso a paso con ejemplos está en la [guía de estilos](../docs/guia-estilos.md#9-crear-una-página-nueva).

## Convenciones

- **Tokens:** colores, tipografía, espaciado, sombras y `--viewport-height` salen de `css/tokens.css`. No escribas hex fuera de tokens ni `100vh`.
- **CSS:** BEM parcial (`bloque__elemento--modificador`), estados `is-*`, sin IDs para estilos y sin `!important` salvo utilidades.
- **Breakpoints:** solo 480, 768, 1024 y 1280 px, todos `min-width` (base móvil). No uses `max-width`.
- **Accesibilidad:** landmarks, un `h1`, etiquetas de formulario, `th scope`, foco visible, modales con focus trap y mensajes `role="status"`/`alert`.
- **HTML dinámico:** usa `escapeHtml` de `core/helpers.js`; `npm run check:html` falla si interpolas datos sin sanear.
- **Rendimiento:** el build deja una sola hoja CSS por página; no añadas `<link>` en el HTML. El tema va inline con hash CSP.

## Pruebas

- `tests/e2e/accessibility.spec.js`: 12 páginas × 2 temas con axe (`moderate+`) y pruebas de skip link, drawer, tabs y errores de login.
- El resto de `tests/e2e/`: login, flota, rutas, alertas, configuración, IA y CSP.
- La suite completa se ejecuta en `nightly.yml`; el job `frontend-lint` de CI ejecuta linters y build.

## Build de producción

`npm run build`:

- resuelve los parciales y marca el enlace activo;
- fusiona vendor + app CSS en una hoja por página y reescribe las URL relativas;
- minifica y hashea CSS/JS;
- inlinea `theme-boot` y escribe `csp.json` para que el backend añada el hash a `script-src`;
- copia fuentes, vendors e iconos.

No edites `frontend/build/`: es un artefacto generado y está en `.gitignore`.
