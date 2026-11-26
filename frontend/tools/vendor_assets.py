"""Genera los assets vendorizados del frontend (Leaflet, Font Awesome y Outfit).

Uso:
    python frontend/tools/vendor_assets.py

Requiere `fonttools` y `brotli` (dependencias solo de desarrollo).
Descarga las fuentes desde los CDN oficiales la primera vez y genera:
    frontend/assets/vendors/fontawesome/fa-subset.css
    frontend/assets/vendors/fontawesome/fa-solid-subset.woff2
    frontend/assets/vendors/fontawesome/fa-regular-subset.woff2
    frontend/assets/fonts/outfit-latin.woff2
    frontend/css/fonts.css
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
VENDORS = FRONTEND / "assets" / "vendors" / "fontawesome"
FONTS = FRONTEND / "assets" / "fonts"
TMP = Path(__file__).resolve().parent / ".cache"

FA_VERSION = "6.6.0"
SOLID_URL = (
    f"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{FA_VERSION}"
    "/webfonts/fa-solid-900.woff2"
)
REGULAR_URL = (
    f"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{FA_VERSION}"
    "/webfonts/fa-regular-400.woff2"
)
METADATA_URL = (
    "https://raw.githubusercontent.com/FortAwesome/Font-Awesome/"
    f"{FA_VERSION}/metadata/icons.json"
)
OUTFIT_CSS_URL = (
    "https://fonts.googleapis.com/css2?family=Outfit:wght@400..900&display=swap"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def used_icons() -> set[str]:
    pattern = re.compile(r"\bfa-[a-z0-9-]+\b")
    found: set[str] = set()
    for path in FRONTEND.rglob("*"):
        if path.suffix not in {".html", ".js"} or "vendors" in path.parts:
            continue
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    reserved = {"fa-solid", "fa-regular", "fa-brands", "fa-light", "fa-thin"}
    return {
        name for name in found if not name.startswith("fa-") or name not in reserved
    }


def build_icon_map(metadata: dict) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for name, data in metadata.items():
        styles = data.get("styles", [])
        unicode = data.get("unicode")
        if not unicode:
            continue
        entry = {
            "unicode": unicode,
            "styles": set(styles),
        }
        mapping[f"fa-{name}"] = entry
        for alias in data.get("aliases", {}).get("names", []):
            mapping[f"fa-{alias}"] = entry
    return mapping


def subset_font(source: Path, destination: Path, unicodes: set[str]) -> None:
    if not unicodes:
        return
    codepoints = ",".join(f"U+{code.upper()}" for code in sorted(unicodes))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "fontTools.subset",
            str(source),
            f"--unicodes={codepoints}",
            f"--output-file={destination}",
            "--flavor=woff2",
            "--layout-features=*",
            "--no-hinting",
            "--desubroutinize",
        ],
        check=True,
    )


def parse_outfit() -> None:
    css = (TMP / "outfit.css").read_text(encoding="utf-8")
    matches = re.findall(
        r"/\* latin \*/\s*@font-face\s*\{(.*?)\}", css, flags=re.DOTALL
    )
    if not matches:
        raise SystemExit("No se encontró el bloque latin de Outfit")
    block = matches[0]
    url = re.search(r"url\((https://[^)]+)\)", block).group(1)
    download(url, FONTS / "outfit-latin.woff2")
    (FRONTEND / "css" / "fonts.css").write_text(
        "/* Generado por frontend/tools/vendor_assets.py */\n"
        "@font-face {\n"
        '  font-family: "Outfit";\n'
        "  font-style: normal;\n"
        "  font-weight: 400 900;\n"
        "  font-display: swap;\n"
        '  src: url("../assets/fonts/outfit-latin.woff2") format("woff2");\n'
        "}\n",
        encoding="utf-8",
    )


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    FONTS.mkdir(parents=True, exist_ok=True)
    VENDORS.mkdir(parents=True, exist_ok=True)

    download(METADATA_URL, TMP / "icons.json")
    download(SOLID_URL, TMP / "fa-solid-900.woff2")
    download(REGULAR_URL, TMP / "fa-regular-400.woff2")
    download(OUTFIT_CSS_URL, TMP / "outfit.css")

    metadata = json.loads((TMP / "icons.json").read_text(encoding="utf-8"))
    icons = build_icon_map(metadata)
    wanted = used_icons()

    solid: set[str] = set()
    regular: set[str] = set()
    rules: list[str] = []
    missing: list[str] = []
    for name in sorted(wanted):
        entry = icons.get(name)
        if entry is None:
            missing.append(name)
            continue
        unicode = entry["unicode"]
        styles = entry["styles"]
        selectors: list[str] = []
        if "solid" in styles:
            solid.add(unicode)
            selectors.append(f".fa-solid.{name}")
        if "regular" in styles:
            regular.add(unicode)
            selectors.append(f".fa-regular.{name}")
        if selectors:
            joined = ", ".join(f"{selector}::before" for selector in selectors)
            rules.append(f'{joined} {{ content: "\\{unicode}"; }}')

    subset_font(TMP / "fa-solid-900.woff2", VENDORS / "fa-solid.woff2", solid)
    subset_font(TMP / "fa-regular-400.woff2", VENDORS / "fa-regular.woff2", regular)

    header = [
        "/* Generado por frontend/tools/vendor_assets.py. No editar a mano. */",
        "@font-face {",
        '  font-family: "Font Awesome 6 Free";',
        "  font-style: normal;",
        "  font-weight: 900;",
        "  font-display: block;",
        '  src: url("fa-solid.woff2") format("woff2");',
        "}",
        "@font-face {",
        '  font-family: "Font Awesome 6 Free";',
        "  font-style: normal;",
        "  font-weight: 400;",
        "  font-display: block;",
        '  src: url("fa-regular.woff2") format("woff2");',
        "}",
        ".fa-solid, .fa-regular, .fa {",
        "  -moz-osx-font-smoothing: grayscale;",
        "  -webkit-font-smoothing: antialiased;",
        "  display: inline-block;",
        "  font-style: normal;",
        "  font-variant: normal;",
        "  line-height: 1;",
        "  text-rendering: auto;",
        "}",
        '.fa-solid { font-family: "Font Awesome 6 Free"; font-weight: 900; }',
        '.fa-regular { font-family: "Font Awesome 6 Free"; font-weight: 400; }',
    ]
    (VENDORS / "fa-subset.css").write_text(
        "\n".join(header + rules) + "\n", encoding="utf-8"
    )

    parse_outfit()

    print(
        f"Iconos usados: {len(wanted)} · sólidos: {len(solid)} · regulares: {len(regular)}"
    )
    if missing:
        print("No encontrados en Font Awesome:", ", ".join(missing))


if __name__ == "__main__":
    main()
