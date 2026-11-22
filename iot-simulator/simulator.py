"""Simulador de dispositivo ESP32-S3 para FrostBase.

Simula un único dispositivo asociado a un camión existente, enviando lecturas
de temperatura, humedad y GPS a la API real de FrostBase cada 10 segundos, y
eventos del Reed Switch de la puerta cuando DOOR_OPEN_PROBABILITY > 0.

Uso:
    pip install -r requirements.txt
    cp .env.example .env   # configure DEVICE_ID y DEVICE_KEY
    python simulator.py
"""
from __future__ import annotations

import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependencia opcional en tiempo de ejecución
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).with_name(".env"))

API_URL = os.getenv("FROSTBASE_API_URL", "http://localhost:8050/api/v1").rstrip("/")
DEVICE_ID = os.getenv("DEVICE_ID", "ESP32-FROST-001")
DEVICE_KEY = os.getenv("DEVICE_KEY", "")
INTERVAL_SECONDS = float(os.getenv("INTERVAL_SECONDS", "10"))
ANOMALY_PROBABILITY = float(os.getenv("ANOMALY_PROBABILITY", "0.01"))
DOOR_OPEN_PROBABILITY = float(os.getenv("DOOR_OPEN_PROBABILITY", "0.0"))
DOOR_OPEN_CYCLES = int(os.getenv("DOOR_OPEN_CYCLES", "3"))
FIXED_LATITUDE = float(os.getenv("FIXED_LATITUDE", "32.5149"))
FIXED_LONGITUDE = float(os.getenv("FIXED_LONGITUDE", "-117.0382"))
SPEED_KMH = float(os.getenv("SPEED_KMH", "30"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "8"))
CONFIG_REFRESH_CYCLES = int(os.getenv("CONFIG_REFRESH_CYCLES", "30"))

HEADERS = {"X-Device-Key": DEVICE_KEY}
running = True


def log(message: str) -> None:
    print(message, flush=True)


def log_key_help() -> None:
    log("[ERROR] 401 Unauthorized: la DEVICE_KEY no coincide con este DEVICE_ID.")
    log("        DEVICE_KEY NO es la placa del camión (por ejemplo, ABC-123-A).")
    log("        Es la cadena larga (~43 caracteres) que imprime el seed al crear")
    log("        el dispositivo, o la que se genera al rotar su clave.")
    log("        Si no la tiene, genere una nueva desde el panel (Flota →")
    log("        dispositivo → Rotar clave) o ejecute:")
    log(
        "          docker compose exec app python -m scripts.rotate_device_key "
        f"--device-id {DEVICE_ID}"
    )
    log("        Copie el valor en iot-simulator/.env y reinicie este simulador.")


def sleep_running(seconds: float) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while running and time.monotonic() < deadline:
        time.sleep(min(0.5, deadline - time.monotonic()))


def handle_stop(_signum, _frame) -> None:
    global running
    running = False


def fetch_config() -> dict | None:
    """Obtiene la configuración del dispositivo, reintentando indefinidamente."""
    attempt = 0
    while running:
        attempt += 1
        try:
            response = requests.get(
                f"{API_URL}/iot/config",
                headers={**HEADERS, "X-Device-Id": DEVICE_ID},
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 401:
                log_key_help()
                sleep_running(10)
                continue
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                log(
                    "[WARN] Rate limit 429 al obtener la configuración. "
                    f"Esperando {retry_after}s…"
                )
                try:
                    sleep_running(min(float(retry_after), 60))
                except ValueError:
                    sleep_running(60)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            wait = min(30, 5 * attempt)
            log(f"[WARN] No se pudo obtener la configuración ({exc}). Reintentando en {wait}s…")
            time.sleep(wait)
    return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


class RouteWalker:
    """Recorre la geometría de la ruta avanzando una distancia fija por lectura."""

    def __init__(self, geometry: list | None) -> None:
        self.points: list[tuple[float, float]] = []
        if geometry:
            for point in geometry:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    try:
                        self.points.append((float(point[0]), float(point[1])))
                    except (TypeError, ValueError):
                        continue
        if len(self.points) < 2:
            self.points = []
            return
        self.cumulative = [0.0]
        for (lat1, lon1), (lat2, lon2) in zip(self.points, self.points[1:]):
            self.cumulative.append(
                self.cumulative[-1] + haversine_m(lat1, lon1, lat2, lon2)
            )
        self.total = self.cumulative[-1]
        self.distance = 0.0

    @property
    def available(self) -> bool:
        return bool(self.points) and self.total > 0

    def _position_at(self, distance: float) -> tuple[float, float]:
        for index in range(1, len(self.cumulative)):
            if self.cumulative[index] >= distance:
                start, end = self.points[index - 1], self.points[index]
                segment = self.cumulative[index] - self.cumulative[index - 1]
                ratio = 0.0 if segment == 0 else (
                    distance - self.cumulative[index - 1]
                ) / segment
                return (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
        return self.points[-1]

    def next_position(self) -> tuple[float, float] | None:
        if not self.available:
            return None
        position = self._position_at(self.distance)
        self.distance += (SPEED_KMH * 1000 / 3600) * INTERVAL_SECONDS
        if self.distance >= self.total:
            self.distance = 0.0
        return position


class ReadingGenerator:
    def __init__(self, config: dict) -> None:
        self.configure(config)

    def configure(self, config: dict) -> None:
        self.temp_min = float(config.get("temperature_min", -5))
        self.temp_max = float(config.get("temperature_max", 0))
        self.hum_min = float(config.get("humidity_min", 70))
        self.hum_max = float(config.get("humidity_max", 90))
        self.temp_center = (self.temp_min + self.temp_max) / 2
        self.hum_center = (self.hum_min + self.hum_max) / 2
        # G4.1: la ruta puede ser None (sin conductor, sin ruta de hoy o sin
        # camión); el camión se queda en la posición fija del .env.
        route = config.get("route") or {}
        self.walker = RouteWalker(route.get("geometry"))

    def _normal_temperature(self) -> float:
        span = max(0.2, (self.temp_max - self.temp_min) * 0.25)
        value = self.temp_center + random.uniform(-span, span)
        return round(min(self.temp_max - 0.1, max(self.temp_min + 0.1, value)), 1)

    def _normal_humidity(self) -> float:
        span = max(0.5, (self.hum_max - self.hum_min) * 0.25)
        value = self.hum_center + random.uniform(-span, span)
        return round(min(self.hum_max - 0.1, max(self.hum_min + 0.1, value)), 1)

    def generate(self) -> tuple[float, float, float, float, str | None]:
        temperature = self._normal_temperature()
        humidity = self._normal_humidity()
        anomaly: str | None = None

        if random.random() < ANOMALY_PROBABILITY:
            if random.random() < 0.5:
                if random.random() < 0.5:
                    temperature = round(
                        self.temp_max + random.uniform(1.5, 6.0), 1
                    )
                else:
                    temperature = round(
                        self.temp_min - random.uniform(1.5, 6.0), 1
                    )
                anomaly = "TEMPERATURA FUERA DE RANGO"
            else:
                if random.random() < 0.5:
                    humidity = round(min(100.0, self.hum_max + random.uniform(2.0, 10.0)), 1)
                else:
                    humidity = round(max(0.0, self.hum_min - random.uniform(2.0, 10.0)), 1)
                anomaly = "HUMEDAD FUERA DE RANGO"

        position = self.walker.next_position()
        if position:
            latitude, longitude = position
        else:
            latitude, longitude = FIXED_LATITUDE, FIXED_LONGITUDE
        return temperature, humidity, latitude, longitude, anomaly


def send_reading(temperature: float, humidity: float, latitude: float, longitude: float) -> dict | None:
    payload = {
        "device_id": DEVICE_ID,
        "temperature": temperature,
        "humidity": humidity,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        response = requests.post(
            f"{API_URL}/iot/readings",
            json=payload,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 401:
            log_key_help()
            return None
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            log(
                "[WARN] Rate limit 429 al enviar la lectura. "
                f"Esperando {retry_after}s…"
            )
            try:
                sleep_running(min(float(retry_after), 60))
            except ValueError:
                sleep_running(60)
            return None
        if response.status_code >= 400:
            log(f"[ERROR] API respondió {response.status_code}: {response.text[:200]}")
            return None
        return response.json()
    except requests.RequestException as exc:
        log(f"[ERROR] No se pudo enviar la lectura: {exc}")
        return None


def send_door_event(is_open: bool) -> dict | None:
    """Envía un evento del Reed Switch (G7): cambia el estado de la puerta."""
    payload = {
        "device_id": DEVICE_ID,
        "is_open": is_open,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        response = requests.post(
            f"{API_URL}/iot/door",
            json=payload,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 401:
            log_key_help()
            return None
        if response.status_code >= 400:
            log(f"[ERROR] API respondió {response.status_code}: {response.text[:200]}")
            return None
        return response.json()
    except requests.RequestException as exc:
        log(f"[ERROR] No se pudo enviar el evento de puerta: {exc}")
        return None


def print_reading(
    config: dict,
    temperature: float,
    humidity: float,
    latitude: float,
    longitude: float,
    anomaly: str | None,
    result: dict | None,
) -> None:
    route = config.get("route") or {}
    log("")
    log("[FROSTBASE SIMULATOR]")
    log(f"Device: {DEVICE_ID}")
    log(f"Truck: {config.get('truck_plate') or 'sin asignar'}")
    log(f"Route: {route.get('name') or 'sin ruta (posición fija)'}")
    log(f"Temperature: {temperature:.1f} °C")
    log(f"Humidity: {humidity:.1f} %")
    log(f"GPS: {latitude:.6f}, {longitude:.6f}")
    log(f"Status: {anomaly or 'NORMAL'}")
    if result and result.get("duplicate"):
        log("Duplicate: sí (mismo timestamp; no se creó otra lectura)")
    if result and result.get("alerts"):
        for alert in result["alerts"]:
            if alert.get("status") == "activa":
                log(f"Alert: {alert.get('message') or alert.get('alert_type')}")
    log(f"Sending next reading in {int(INTERVAL_SECONDS)} seconds...")


def main() -> int:
    global running
    if not DEVICE_KEY:
        log("[ERROR] Falta DEVICE_KEY. Copie .env.example a .env y configure la clave del dispositivo.")
        return 1

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    log(f"[FROSTBASE SIMULATOR] Conectando a {API_URL} …")
    config = fetch_config()
    if config is None:
        return 0

    generator = ReadingGenerator(config)
    cycle = 0
    door_cycles_left = 0

    while running:
        if cycle > 0 and cycle % CONFIG_REFRESH_CYCLES == 0:
            refreshed = fetch_config()
            if refreshed:
                config = refreshed
                generator.configure(config)
                log("[INFO] Configuración del dispositivo actualizada.")

        # G7: puerta con Reed Switch — abre al azar y cierra tras N ciclos.
        if door_cycles_left > 0:
            door_cycles_left -= 1
            if door_cycles_left == 0:
                send_door_event(False)
                log("[DOOR] Puerta cerrada.")
        elif DOOR_OPEN_PROBABILITY > 0 and random.random() < DOOR_OPEN_PROBABILITY:
            send_door_event(True)
            door_cycles_left = max(1, DOOR_OPEN_CYCLES)
            log("[DOOR] Puerta abierta (evento enviado al backend).")

        temperature, humidity, latitude, longitude, anomaly = generator.generate()
        if anomaly:
            log(f"[ANOMALY] Lectura anómala generada: {anomaly}")
        result = send_reading(temperature, humidity, latitude, longitude)
        print_reading(
            config, temperature, humidity, latitude, longitude, anomaly, result
        )
        cycle += 1

        deadline = time.monotonic() + INTERVAL_SECONDS
        while running and time.monotonic() < deadline:
            time.sleep(min(0.5, deadline - time.monotonic()))

    log("\n[FROSTBASE SIMULATOR] Detenido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
