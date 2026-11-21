"""Genera docs/api/openapi.json desde la aplicación FastAPI.

Uso (desde backend/):
    python -m scripts.export_openapi
    python -m scripts.export_openapi --check   # falla si el archivo cambió

Se ejecuta en CI para detectar cambios de contrato involuntarios.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "api" / "openapi.json"


def dump() -> str:
    load_dotenv(ROOT / ".env")
    from app.main import app

    return (
        json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta el contrato OpenAPI")
    parser.add_argument(
        "--check",
        action="store_true",
        help="No escribe; falla si el contrato versionado está desactualizado",
    )
    args = parser.parse_args()

    content = dump()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(
                "docs/api/openapi.json está desactualizado. "
                "Ejecute: python -m scripts.export_openapi"
            )
            return 1
        print("Contrato OpenAPI sin cambios")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Contrato OpenAPI escrito en {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
