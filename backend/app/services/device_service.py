from sqlalchemy.orm import Session

from app.core.security import (
    generate_device_secret,
    hash_device_secret,
)
from app.models.device import Device
from app.repositories import devices as devices_repo
from app.repositories import trucks as trucks_repo
from app.schemas.common import Page
from app.schemas.device import DeviceCreate, DeviceCreatedOut, DeviceOut, DeviceUpdate
from app.services import settings_service
from app.services.serializers import serialize_device
from app.utils.time import utcnow


class DeviceConflictError(Exception):
    pass


class DeviceNotFoundError(Exception):
    pass


class DeviceValidationError(Exception):
    pass


def _to_out(db: Session, device: Device) -> DeviceOut:
    setting = settings_service.get_settings(db)
    return serialize_device(device, setting.offline_timeout_seconds)


def _created_out(db: Session, device: Device, secret: str) -> DeviceCreatedOut:
    setting = settings_service.get_settings(db)
    base = serialize_device(device, setting.offline_timeout_seconds)
    return DeviceCreatedOut(**base.model_dump(), device_key=secret)


def _validate_truck(db: Session, truck_id: int):
    truck = trucks_repo.get(db, truck_id)
    if truck is None:
        raise DeviceValidationError("El camión seleccionado no existe")
    return truck


def _detach_truck_devices(db: Session, truck_id: int, except_device_id: int | None = None):
    current = devices_repo.get_by_truck(db, truck_id)
    if current is not None and current.id != except_device_id:
        current.truck_id = None
        db.add(current)


def list_devices(
    db: Session, *, search: str | None, page: int, page_size: int
) -> Page[DeviceOut]:
    setting = settings_service.get_settings(db)
    devices, total = devices_repo.list_all(
        db, search=search, page=page, page_size=page_size
    )
    items = [serialize_device(device, setting.offline_timeout_seconds) for device in devices]
    return Page(items=items, total=total, page=page, page_size=page_size)


def list_all_devices(db: Session) -> list[DeviceOut]:
    setting = settings_service.get_settings(db)
    return [
        serialize_device(device, setting.offline_timeout_seconds)
        for device in devices_repo.list_all_without_pagination(db)
    ]


def list_unassigned_devices(db: Session) -> list[DeviceOut]:
    setting = settings_service.get_settings(db)
    devices, _ = devices_repo.list_all(
        db, page=1, page_size=500, unassigned_only=True
    )
    return [serialize_device(device, setting.offline_timeout_seconds) for device in devices]


def get_device(db: Session, device_pk: int) -> DeviceOut:
    device = devices_repo.get(db, device_pk)
    if device is None:
        raise DeviceNotFoundError("Dispositivo no encontrado")
    return _to_out(db, device)


def create_device(db: Session, payload: DeviceCreate) -> DeviceCreatedOut:
    identifier = payload.device_id.strip()
    if devices_repo.get_by_identifier(db, identifier) is not None:
        raise DeviceConflictError("Ya existe un dispositivo con ese identificador")
    if payload.truck_id is not None:
        _validate_truck(db, payload.truck_id)
        _detach_truck_devices(db, payload.truck_id)

    secret = generate_device_secret()
    device = devices_repo.create(
        db,
        device_id=identifier,
        truck_id=payload.truck_id,
        key_hash=hash_device_secret(secret),
    )
    device = devices_repo.get(db, device.id) or device
    return _created_out(db, device, secret)


def update_device(db: Session, device_pk: int, payload: DeviceUpdate) -> DeviceOut:
    device = devices_repo.get(db, device_pk)
    if device is None:
        raise DeviceNotFoundError("Dispositivo no encontrado")
    if "truck_id" in payload.model_fields_set:
        if payload.truck_id is not None:
            _validate_truck(db, payload.truck_id)
            _detach_truck_devices(db, payload.truck_id, except_device_id=device.id)
        device.truck_id = payload.truck_id
        db.add(device)
        db.commit()
        device = devices_repo.get(db, device.id) or device
    return _to_out(db, device)


def rotate_key(db: Session, device_pk: int) -> DeviceCreatedOut:
    device = devices_repo.get(db, device_pk)
    if device is None:
        raise DeviceNotFoundError("Dispositivo no encontrado")
    secret = generate_device_secret()
    device.key_hash = hash_device_secret(secret)
    db.add(device)
    db.commit()
    device = devices_repo.get(db, device.id) or device
    return _created_out(db, device, secret)


def authenticate_device(db: Session, device_id: str, secret: str) -> Device | None:
    from app.core.security import verify_device_secret

    device = devices_repo.get_by_identifier(db, device_id)
    if device is None:
        return None
    if not verify_device_secret(secret, device.key_hash):
        return None
    return device


def touch_device(db: Session, device: Device) -> Device:
    device.last_seen = utcnow()
    db.add(device)
    db.commit()
    db.refresh(device)
    return device
