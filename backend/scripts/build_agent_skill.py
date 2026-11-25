"""Genera un paquete instalable de la skill Lua ``frostbase`` (B5 fase 2).

El ZIP contiene la skill y un ``private/config.txt`` con la URL del backend y
el token RO. Ese ZIP es un secreto: no lo suba al repositorio ni lo comparta.

Uso:
    python -m scripts.build_agent_skill
    python -m scripts.build_agent_skill --output C:\\ruta\\frostbase-skill.zip
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

from scripts.runtime import PROJECT_ROOT, configure_stdio, load_project_env

load_project_env()

from app.core.config import settings  # noqa: E402

SKILL_NAME = "frostbase"
SOURCE = PROJECT_ROOT / "esp-claw" / "skills" / SKILL_NAME
DEFAULT_OUTPUT = PROJECT_ROOT / "dist" / f"{SKILL_NAME}-skill.zip"


def build_package(
    source: Path,
    output: Path,
    *,
    base_url: str,
    token: str,
) -> Path:
    """Copia la skill, escribe la configuración privada y crea el ZIP."""
    if not source.is_dir():
        raise FileNotFoundError(f"No existe la skill: {source}")
    if not base_url.strip():
        raise ValueError("AI_BACKEND_URL está vacío")
    if not token.strip():
        raise ValueError("AI_AGENT_READ_TOKEN está vacío")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        staged = Path(temp) / SKILL_NAME
        shutil.copytree(source, staged)
        private = staged / "private"
        private.mkdir(parents=True, exist_ok=True)
        (private / "config.txt").write_text(
            f"base={base_url.rstrip('/')}\ntoken={token}\n",
            encoding="utf-8",
        )
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staged.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(Path(temp)))
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera el ZIP de la skill Lua frostbase"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Ruta del ZIP (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    args = parse_args()
    try:
        package = build_package(
            SOURCE,
            args.output,
            base_url=settings.ai_backend_url,
            token=settings.ai_agent_read_token,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 2

    print(f"\nPaquete generado: {package}")
    print(
        "Descomprímalo y suba su contenido a /skills/frostbase del ESP-Claw; "
        "use el prompt generado con: .\\tasks.ps1 ai-prompt -Skill"
    )
    print(
        "\nEl ZIP contiene el token RO en private/config.txt: trátelo como un "
        "secreto y no lo suba al repositorio."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
