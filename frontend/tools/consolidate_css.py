"""Consolida `bauhaus.css` dentro de tokens/base/components/layout/pages (T4.5).

Uso puntual desde la raíz del repositorio:
    python frontend/tools/consolidate_css.py
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "css"

SECTION_TARGETS = {
    "Tipografía y lienzo": "base.css",
    "Sidebar": "layout.css",
    "Encabezados de página": "layout.css",
    "Tarjetas": "components.css",
    "Botones": "components.css",
    "Botones de icono": "components.css",
    "Badges y estados": "components.css",
    "Formularios": "components.css",
    "Tablas": "components.css",
    "Pestañas": "components.css",
    "KPIs con bloqueo de color": "components.css",
    "Carrusel de temperaturas": "pages/dashboard.css",
    "Paneles de estado / clima": "components.css",
    "Mapa": "components.css",
    "Empty states / tiles / notices": "components.css",
    "Modales y toasts": "components.css",
    "Toggle": "components.css",
    "Página de login (composición Bauhaus)": "pages/login.css",
}

PAGE_SELECTORS = [
    (re.compile(r"^\.settings-section"), "pages/settings.css"),
    (re.compile(r"^\.range-preview"), "pages/settings.css"),
    (re.compile(r"^\.points-section"), "pages/routes.css"),
    (re.compile(r"^\.point-row__order"), "pages/routes.css"),
    (re.compile(r"^\.route-point__num"), "pages/routes.css"),
    (re.compile(r"^\.route-list-item"), "pages/routes.css"),
    (re.compile(r"^\.route-assign"), "pages/routes.css"),
    (re.compile(r"^\.detail-hero__icon"), "pages/truck-detail.css"),
    (re.compile(r"^\.reading-tile"), "pages/truck-detail.css"),
    (re.compile(r"^\.history-"), "pages/truck-detail.css"),
    (re.compile(r"^\.alert-detail-hero"), "pages/alerts.css"),
    (re.compile(r"^\.alerts-filters"), "pages/alerts.css"),
]


def split_rules(text: str) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    index = 0
    while True:
        start = text.find("{", index)
        if start == -1:
            break
        selector = text[index:start].strip()
        depth = 1
        position = start + 1
        while position < len(text) and depth:
            if text[position] == "{":
                depth += 1
            elif text[position] == "}":
                depth -= 1
            position += 1
        body = text[start : position]
        rules.append((selector, body))
        index = position
    return rules


def main() -> None:
    source = CSS / "bauhaus.css"
    text = source.read_text(encoding="utf-8")
    text = re.sub(r"/\* =+.*?=+ \*/", "", text, flags=re.S)

    parts = re.split(r"/\* ---------- (.*?) ---------- \*/", text)
    # parts[0] es vacío; luego alterna título, contenido
    chunks: dict[str, list[str]] = {}
    for index in range(1, len(parts), 2):
        title = parts[index].strip()
        content = parts[index + 1]
        if title == "Páginas específicas":
            for selector, body in split_rules(content):
                first = selector.split(",")[0].strip()
                target = None
                for pattern, path in PAGE_SELECTORS:
                    if pattern.match(first):
                        target = path
                        break
                if target is None:
                    target = "components.css"
                chunks.setdefault(target, []).append(f"{selector} {body}")
            continue
        if title == "Responsive":
            chunks.setdefault("layout.css", []).append(content.strip())
            continue
        target = SECTION_TARGETS.get(title)
        if target is None:
            raise SystemExit(f"Sección sin destino: {title}")
        chunks.setdefault(target, []).append(content.strip())

    marker = "\n\n/* ===== Consolidado desde bauhaus.css (T4.5) ===== */\n"
    for target, blocks in chunks.items():
        path = CSS / target
        original = path.read_text(encoding="utf-8").rstrip()
        addition = marker + "\n\n".join(blocks) + "\n"
        path.write_text(original + addition, encoding="utf-8")
        print(f"{target}: +{len(blocks)} bloque(s)")

    source.unlink()
    print("bauhaus.css eliminado")


if __name__ == "__main__":
    main()
