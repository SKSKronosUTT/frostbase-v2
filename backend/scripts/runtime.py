"""Utilidades para scripts ejecutados desde el host o desde el contenedor.

En desarrollo los scripts se lanzan desde ``backend/`` con el *host* como cwd;
las variables viven en el ``.env`` de la raíz del repositorio. En el contenedor
llegan por ``compose`` y no hay ``.env``, por lo que la carga es opcional y
nunca pisa variables ya definidas.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env() -> Path | None:
    """Carga ``<repo>/.env`` si existe sin sobrescribir el entorno actual."""
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)
        return ENV_FILE
    return None


def configure_stdio() -> None:
    """Evita ``UnicodeEncodeError`` con acentos/flechas en Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
