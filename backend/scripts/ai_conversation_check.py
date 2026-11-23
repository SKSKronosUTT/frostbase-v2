"""Batería de verificación conversacional del asistente (A4).

Hace preguntas al asistente a través del backend y contrasta las cifras con
`agent-read`. No forma parte de la suite automática (consume cuota del LLM).

Uso (con el stack arriba):
    set ADMIN_PASSWORD=...
    python -m scripts.ai_conversation_check --limit 5 --delay 10

Criterio: ≥ 90 % de respuestas correctas.
"""

from __future__ import annotations

import argparse
import os
import re
import time
from collections.abc import Callable

import httpx

READ_HEADERS: dict[str, str] = {}


def _login(client: httpx.Client, base_url: str) -> dict[str, str]:
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("Defina ADMIN_PASSWORD")
    response = client.post(
        f"{base_url}/api/v1/auth/login",
        json={"identifier": "admin", "password": password},
    )
    response.raise_for_status()
    token = client.cookies.get("frostbase_csrf") or ""
    return {"X-CSRF-Token": token}


def _read(client: httpx.Client, base_url: str, path: str) -> dict:
    response = client.get(f"{base_url}/api/v1/agent-read{path}", headers=READ_HEADERS)
    response.raise_for_status()
    return response.json()


def _contains_number(text: str, value: int) -> bool:
    return re.search(rf"\b{value}\b", text) is not None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batería del asistente FrostBase")
    parser.add_argument("--base-url", default="http://127.0.0.1:8050")
    parser.add_argument("--limit", type=int, default=5, help="Preguntas a ejecutar")
    parser.add_argument(
        "--delay", type=float, default=10.0, help="Segundos entre preguntas"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("AI_AGENT_READ_TOKEN", "")
    if not token:
        raise SystemExit("Defina AI_AGENT_READ_TOKEN para contrastar las cifras")
    READ_HEADERS["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=150) as client:
        csrf = _login(client, args.base_url)
        summary = _read(client, args.base_url, "/fleet-summary")
        trips = _read(client, args.base_url, "/trips/active")
        critical = _read(client, args.base_url, "/alerts?limit=5")

        questions: list[tuple[str, Callable[[str], bool]]] = [
            (
                "¿Cuántas alertas activas hay ahora mismo?",
                lambda text: _contains_number(text, summary["alerts_active"]),
            ),
            (
                "¿Cuántos viajes están en curso?",
                lambda text: _contains_number(text, summary["trips_active"]),
            ),
            (
                "¿Cuántas rutas hay programadas para hoy?",
                lambda text: _contains_number(text, summary["routes_today"]),
            ),
            (
                "¿Cuántas entregas están pendientes en los viajes activos?",
                lambda text: _contains_number(text, summary["pending_orders"]),
            ),
            (
                "¿Qué placas aparecen en las alertas activas?",
                lambda text: (
                    "sin alertas" in text.lower()
                    if not critical["items"]
                    else any(
                        item.get("truck_plate")
                        and item["truck_plate"].lower() in text.lower()
                        for item in critical["items"]
                    )
                ),
            ),
            (
                "¿Qué camiones están en viaje y cómo van sus entregas?",
                lambda text: (
                    not trips["items"]
                    or any(
                        item["truck_plate"].lower() in text.lower()
                        for item in trips["items"]
                    )
                ),
            ),
        ]
        selected = questions[: max(1, min(args.limit, len(questions)))]
        passed = 0
        for index, (question, check) in enumerate(selected, start=1):
            response = client.post(
                f"{args.base_url}/api/v1/ai/chat",
                headers=csrf,
                json={"message": question},
            )
            if response.status_code != 200:
                print(f"[{index}] ERROR {response.status_code}: {question}")
                continue
            reply = response.json().get("reply", "")
            ok = bool(reply) and check(reply)
            passed += int(ok)
            print(f"[{'OK' if ok else 'FAIL'}] {question}")
            print(f"    {reply[:300]}")
            time.sleep(args.delay)

        rate = 100 * passed / len(selected)
        print(f"\nResultado: {passed}/{len(selected)} ({rate:.0f} %)")
        return 0 if rate >= 90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
