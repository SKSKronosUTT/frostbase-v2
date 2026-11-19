# Integración de dispositivos ESP32-S3

FrostBase expone una API REST simple para que un ESP32-S3 (o cualquier cliente HTTP) envíe lecturas de temperatura, humedad y GPS. La autenticación es independiente de la sesión del administrador.

## Resumen

| Elemento | Valor |
|---|---|
| Endpoint de lecturas | `POST /api/v1/iot/readings` |
| Endpoint de configuración | `GET /api/v1/iot/config` |
| Autenticación | `X-Device-Key: <clave>` (config: además `X-Device-Id`) |
| Formato | JSON UTF-8 |
| Frecuencia recomendada | cada 10 segundos |
| Transporte | HTTP/1.1; HTTPS en producción |

## 1. Registrar el dispositivo

Desde la UI (detalle del camión) o con la API administrativa:

```bash
curl -s -X POST http://localhost:8050/api/v1/devices \
  -b "frostbase_token=<cookie>" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"ESP32-FROST-003","truck_id":1}'
```

La respuesta incluye `device_key`. **Solo se muestra una vez**. Las claves nuevas se
guardan como HMAC-SHA256 con `DEVICE_KEY_PEPPER` (verificación O(1)); los
dispositivos antiguos conservan Argon2 y usan un caché de aciertos de 300 s. Si se
pierde la clave, rote:

```bash
curl -s -X POST http://localhost:8050/api/v1/devices/3/rotate-key \
  -b "frostbase_token=<cookie>"
```

La clave anterior deja de funcionar inmediatamente. El endpoint de rotación está
limitado a 10 solicitudes/hora por administrador. Para migrar todo el parque a
HMAC: `python -m scripts.rotate_all_device_keys --dry-run` y luego `--yes` (con la
aplicación detenida o reiniciándola después).

El dispositivo debe tener un camión asignado; de lo contrario las lecturas se rechazan con `409`.

## 2. Obtener la configuración

```http
GET /api/v1/iot/config
X-Device-Id: ESP32-FROST-001
X-Device-Key: <clave>
```

```json
{
  "device_id": "ESP32-FROST-001",
  "truck_id": 1,
  "truck_plate": "ABC-123-A",
  "route": {
    "name": "Villa Fontana - Playas de Tijuana",
    "geometry": [[32.5064, -116.9727], [32.5069, -116.9737]]
  },
  "temperature_min": -5.0,
  "temperature_max": 1.0,
  "humidity_min": 75.0,
  "humidity_max": 85.0
}
```

- La geometría es una lista de pares `[latitud, longitud]`.
- `route` puede ser `null` si el camión no tiene ruta.
- Consulte la configuración al arrancar y periódicamente (por ejemplo, cada 5 minutos) para recoger cambios de umbrales.

## 3. Enviar una lectura

```http
POST /api/v1/iot/readings
X-Device-Key: <clave>
Content-Type: application/json
```

```json
{
  "device_id": "ESP32-FROST-001",
  "temperature": -2.4,
  "humidity": 79.5,
  "latitude": 32.5149,
  "longitude": -117.0382,
  "timestamp": "2026-11-15T22:30:00Z"
}
```

| Campo | Tipo | Requerido | Validación |
|---|---|---|---|
| `device_id` | string | Sí | 3–100 caracteres, debe existir |
| `temperature` | float | Sí | −80…80 °C |
| `humidity` | float | Sí | 0…100 % |
| `latitude` | float | No | −90…90 |
| `longitude` | float | No | −180…180 |
| `timestamp` | ISO 8601 | No | Si falta se usa la hora del servidor. Ventana: −7 días a +5 minutos; naive = UTC |

Respuesta `200`:

```json
{
  "success": true,
  "message": "Lectura registrada correctamente",
  "truck_id": 1,
  "alerts": [],
  "duplicate": false,
  "reading_id": 12345
}
```

Si la lectura genera una alerta, `alerts` incluye las alertas activas creadas o
reutilizadas. La ingesta es idempotente por `(device_id, reading_timestamp)`:
reenviar el mismo payload devuelve `duplicate: true`, el mismo `reading_id` y
`alerts: []`. **Conserve el timestamp original al reintentar**; si lo regenera,
se creará una lectura nueva.

### Códigos HTTP

| Código | Causa | Acción sugerida |
|---|---|---|
| `200` | Lectura registrada o duplicada | Continuar; revise `duplicate` |
| `401` | Falta `X-Device-Key`, no coincide o el dispositivo no existe | Revisar clave; no reintentar en bucle rápido |
| `409` | Dispositivo sin camión asignado | Asignar camión desde la UI/API |
| `422` | JSON, valores físicos o timestamp fuera de ventana | Corregir payload; no reintentar igual |
| `429` | Rate limit (30/min por dispositivo, 120/min por IP) | Esperar `Retry-After` y aplicar backoff |
| `5xx` | Error temporal del servidor | Reintentar con backoff exponencial |

### Rate limiting y backoff

Las respuestas `429` incluyen:

| Cabecera | Significado |
|---|---|
| `Retry-After` | Segundos que debe esperar antes de reintentar |
| `X-RateLimit-Limit` | Límite de la ventana |
| `X-RateLimit-Remaining` | Peticiones restantes |
| `X-RateLimit-Reset` | Segundos hasta que se libere la ventana |

Recomendación para el firmware:

1. Ante `429`, espere `Retry-After` (o 60 s si no está presente) + jitter.
2. Ante `5xx` o error de red, use backoff exponencial: 5, 10, 20, 40… hasta 60 s.
3. Ante `401`/`422`, **no** reintente en bucle: corrija la clave o el payload.
4. Envíe como máximo una lectura cada 10 s por dispositivo. El límite normal es
   30/min, así que un simulador o ESP32 a 10 s nunca debería recibir `429`.

## 4. Ejemplo de firmware (Arduino, ESP32-S3)

Dependencias: core `esp32` (incluye `WiFi.h`, `HTTPClient.h`, `ArduinoJson`). Instale **ArduinoJson** desde el Library Manager.

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

const char* WIFI_SSID = "MI_RED";
const char* WIFI_PASS = "MI_CLAVE";

const char* API_BASE = "https://frostbase.example.com/api/v1";
const char* DEVICE_ID = "ESP32-FROST-001";
const char* DEVICE_KEY = "CLAVE_DEL_DISPOSITIVO";

const unsigned long INTERVAL_MS = 10000;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

String isoTimestamp() {
  time_t now = time(nullptr);
  struct tm utc;
  gmtime_r(&now, &utc);
  char buffer[32];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &utc);
  return String(buffer);
}

void sendReading(float temperature, float humidity, double latitude, double longitude) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(String(API_BASE) + "/iot/readings");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  http.setTimeout(8000);

  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["latitude"] = latitude;
  doc["longitude"] = longitude;
  doc["timestamp"] = isoTimestamp();

  String payload;
  serializeJson(doc, payload);

  int status = http.POST(payload);
  if (status > 0) {
    Serial.printf("HTTP %d: %s\n", status, http.getString().c_str());
  } else {
    Serial.printf("Error HTTP: %s\n", http.errorToString(status).c_str());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  connectWiFi();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
}

void loop() {
  // Sustituya por lecturas reales de sus sensores y GPS
  float temperature = -2.0 + random(-30, 31) / 100.0;
  float humidity = 80.0 + random(-100, 101) / 100.0;
  double latitude = 32.5149;
  double longitude = -117.0382;

  sendReading(temperature, humidity, latitude, longitude);
  delay(INTERVAL_MS);
}
```

## 5. Recomendaciones de producción

- **HTTPS obligatorio.** Use un certificado válido; en el ESP32 configure `WiFiClientSecure` con la CA raíz o `setInsecure()` solo en pruebas.
- **No reutilice claves** entre dispositivos. Rote la clave si el equipo se compromete. Las claves nuevas usan HMAC con `DEVICE_KEY_PEPPER`; rotar el pepper invalida todas las claves HMAC y exige rotar también las de los dispositivos.
- **Backoff exponencial** ante `5xx`, `429` o fallos de red (por ejemplo, 5, 10, 20… hasta 60 s). Respete `Retry-After`. Nunca bloquee el bucle principal.
- **Buffering local:** si no hay red, guarde lecturas en memoria/flash y envíelas al reconectar (con su `timestamp` original).
- **Timestamp en UTC.** Sincronice por NTP; el servidor también registra `received_at`.
- **GPS opcional:** si no hay fix, omita `latitude`/`longitude` en lugar de enviar ceros.
- **Consumo:** active el modem sleep de WiFi y use deep sleep si el intervalo es largo.
- **Validación:** el backend valida rangos físicos y rechaza coordenadas inválidas con `422`.

## 6. Simulador de referencia

`iot-simulator/simulator.py` implementa el mismo contrato en Python, incluyendo recorrido sobre la geometría de la ruta, anomalías probabilísticas y reconexión tolerante a fallos. Úselo para comparar comportamiento antes de flashear el ESP32.

```bash
cd iot-simulator
cp .env.example .env   # configure DEVICE_ID y DEVICE_KEY
python simulator.py
```
