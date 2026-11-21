"""Actualiza las cabeceras de los HTML para usar assets locales (T4.1).

Ejecutar una vez desde la raíz del repositorio:
    python frontend/tools/update_heads.py
"""

from __future__ import annotations

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1]
LEAFLET_PAGES = {"dashboard.html", "routes.html", "route-detail.html", "truck-detail.html"}
DESCRIPTIONS = {
    "dashboard.html": "Panel de control de la flota refrigerada FrostBase: temperatura, ubicación y alertas.",
    "trucks.html": "Gestión de camiones y dispositivos IoT de la flota FrostBase.",
    "truck-detail.html": "Detalle de un camión: lecturas, dispositivo, ruta y alertas.",
    "routes.html": "Gestión de rutas de reparto de FrostBase.",
    "route-detail.html": "Detalle de una ruta: puntos de entrega y geometría.",
    "alerts.html": "Historial de alertas de temperatura, humedad y desconexión.",
    "settings.html": "Configuración de umbrales y preferencias de FrostBase.",
}

THEME_SCRIPT = re.compile(
    r"\s*<script>\s*\(function \(\) \{.*?</script>", re.DOTALL
)


def update(name: str) -> bool:
    path = FRONTEND / name
    html = path.read_text(encoding="utf-8")
    original = html

    html = re.sub(
        r'\s*<link rel="preconnect" href="https://fonts\.googleapis\.com" />', "", html
    )
    html = re.sub(
        r'\s*<link rel="preconnect" href="https://fonts\.gstatic\.com" crossorigin />',
        "",
        html,
    )
    html = re.sub(
        r'\s*<link href="https://fonts\.googleapis\.com/css2\?family=Inter[^"]*" rel="stylesheet" />',
        "",
        html,
    )
    html = html.replace(
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css" />',
        '<link rel="stylesheet" href="assets/vendors/fontawesome/fa-subset.css" />',
    )
    html = html.replace(
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />',
        '<link rel="stylesheet" href="assets/vendors/leaflet/leaflet.css" />',
    )
    html = html.replace(
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>',
        '<script src="assets/vendors/leaflet/leaflet.js"></script>',
    )

    if '<link rel="stylesheet" href="css/fonts.css" />' not in html:
        anchor = '<link rel="icon" href="assets/logo.png" />'
        preload = (
            anchor
            + '\n  <link rel="preload" href="assets/fonts/outfit-latin.woff2"'
            + ' as="font" type="font/woff2" crossorigin />'
            + '\n  <link rel="stylesheet" href="css/fonts.css" />'
        )
        html = html.replace(anchor, preload, 1)

    if '<meta name="robots"' not in html and name != "login.html":
        html = html.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />'
            '\n  <meta name="robots" content="noindex, nofollow" />',
            1,
        )

    if name in DESCRIPTIONS and 'name="description"' not in html:
        html = html.replace(
            '<meta name="robots" content="noindex, nofollow" />',
            '<meta name="robots" content="noindex, nofollow" />'
            f'\n  <meta name="description" content="{DESCRIPTIONS[name]}" />',
            1,
        )

    html = THEME_SCRIPT.sub(
        '\n  <script src="js/core/theme-boot.js"></script>', html, count=1
    )

    if name == "index.html":
        html = re.sub(r"\s*<style>.*?</style>", "", html, flags=re.DOTALL)
        if 'href="css/pages/index.css"' not in html:
            html = html.replace(
                '<link rel="stylesheet" href="css/global.css" />',
                '<link rel="stylesheet" href="css/global.css" />'
                '\n  <link rel="stylesheet" href="css/pages/index.css" />',
                1,
            )

    html = html.replace(
        '<img src="assets/logo.png" alt="Logotipo FrostBase"\n               onerror="this.style.display=\'none\'; this.parentElement.classList.add(\'login-brand__logo--placeholder\');" />',
        '<img src="assets/logo.png" alt="Logotipo FrostBase" width="72" height="72" />',
    )

    if name in LEAFLET_PAGES:
        html = re.sub(
            r'<div class="map([^"]*)" id="([^"]+)"></div>',
            r'<div class="map\1" id="\2" role="application"'
            r' aria-label="Mapa de ubicación de la flota"></div>',
            html,
        )

    if html != original:
        path.write_text(html, encoding="utf-8")
        return True
    return False


def main() -> None:
    for path in sorted(FRONTEND.glob("*.html")):
        changed = update(path.name)
        print(f"{path.name}: {'actualizado' if changed else 'sin cambios'}")


if __name__ == "__main__":
    main()
