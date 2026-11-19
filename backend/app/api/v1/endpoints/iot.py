from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.api.deps import TxSession, authenticate_device_or_401
from app.core.ratelimit import RateLimit
from app.schemas.iot import IoTConfigResponse, IoTReadingResponse, ReadingIngest
from app.services import reading_service, settings_service
from app.services.serializers import serialize_alert

router = APIRouter(prefix="/iot", tags=["IoT"])

_reading_device_limiter = RateLimit("iot:readings:device", limit=30, window_seconds=60)
_reading_ip_limiter = RateLimit("iot:readings:ip", limit=120, window_seconds=60)
_config_device_limiter = RateLimit("iot:config:device", limit=60, window_seconds=60)
_config_ip_limiter = RateLimit("iot:config:ip", limit=120, window_seconds=60)


@router.post("/readings", response_model=IoTReadingResponse)
def receive_reading(
    payload: ReadingIngest,
    request: Request,
    response: Response,
    db: TxSession,
    x_device_key: Annotated[str | None, Header(alias="X-Device-Key")] = None,
) -> IoTReadingResponse:
    # El límite se aplica antes de cualquier verificación de clave (KDF/HMAC).
    _reading_device_limiter.check(request, response, extra=payload.device_id.strip())
    _reading_ip_limiter.check(request, response)
    device = authenticate_device_or_401(
        db, device_id=payload.device_id, device_key=x_device_key
    )
    setting = settings_service.get_settings(db)
    try:
        reading, alerts, duplicate = reading_service.ingest_reading(
            db, device=device, payload=payload, setting=setting
        )
    except reading_service.DeviceNotAssignedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return IoTReadingResponse(
        success=True,
        message=(
            "Lectura duplicada; se conserva la existente"
            if duplicate
            else "Lectura registrada correctamente"
        ),
        truck_id=reading.truck_id,
        alerts=[serialize_alert(alert) for alert in alerts],
        duplicate=duplicate,
        reading_id=reading.id,
    )


@router.get("/config", response_model=IoTConfigResponse)
def device_config(
    request: Request,
    response: Response,
    db: TxSession,
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
    x_device_key: Annotated[str | None, Header(alias="X-Device-Key")] = None,
) -> IoTConfigResponse:
    if not x_device_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado X-Device-Id",
        )
    if len(x_device_id) > 100:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dispositivo o clave inválidos",
        )
    _config_device_limiter.check(request, response, extra=x_device_id.strip())
    _config_ip_limiter.check(request, response)
    device = authenticate_device_or_401(
        db, device_id=x_device_id, device_key=x_device_key
    )
    setting = settings_service.get_settings(db)
    route = device.truck.route if device.truck else None
    return IoTConfigResponse(
        device_id=device.device_id,
        truck_id=device.truck_id,
        truck_plate=device.truck.plate if device.truck else None,
        route=(
            {"name": route.name, "geometry": route.geometry} if route else None
        ),
        temperature_min=setting.temperature_min,
        temperature_max=setting.temperature_max,
        humidity_min=setting.humidity_min,
        humidity_max=setting.humidity_max,
    )
