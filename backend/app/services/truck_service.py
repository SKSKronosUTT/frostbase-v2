from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.truck import Truck
from app.repositories import alerts as alerts_repo
from app.repositories import devices as devices_repo
from app.repositories import readings as readings_repo
from app.repositories import routes as routes_repo
from app.repositories import trucks as trucks_repo
from app.schemas.common import Page
from app.schemas.truck import TruckCreate, TruckDetailOut, TruckOut, TruckUpdate
from app.services import alert_service, settings_service
from app.services.serializers import serialize_truck


class TruckConflictError(Exception):
    pass


class TruckNotFoundError(Exception):
    pass


class TruckValidationError(Exception):
    pass


def _get_or_fail(db: Session, truck_id: int) -> Truck:
    truck = trucks_repo.get(db, truck_id)
    if truck is None:
        raise TruckNotFoundError("Camión no encontrado")
    return truck


def _assign_route(db: Session, truck: Truck, route_id: int | None) -> None:
    if route_id is None:
        truck.route_id = None
        db.add(truck)
        return
    route = routes_repo.get(db, route_id)
    if route is None:
        raise TruckValidationError("La ruta seleccionada no existe")
    for other in trucks_repo.trucks_using_route(db, route_id, except_id=truck.id):
        other.route_id = None
        db.add(other)
    truck.route_id = route.id
    db.add(truck)


def _assign_device(db: Session, truck: Truck, device_pk: int | None) -> None:
    current = devices_repo.get_by_truck(db, truck.id)
    if device_pk is None:
        if current is not None:
            current.truck_id = None
            db.add(current)
        return

    device = devices_repo.get(db, device_pk)
    if device is None:
        raise TruckValidationError("El dispositivo seleccionado no existe")
    if current is not None and current.id != device.id:
        current.truck_id = None
        db.add(current)
    if device.truck_id is not None and device.truck_id != truck.id:
        previous = trucks_repo.get(db, device.truck_id)
        if previous is not None:
            previous_id = previous.id
            device.truck_id = None
            db.flush()
            conflict = devices_repo.get_by_truck(db, previous_id)
            if conflict is not None and conflict.id != device.id:
                conflict.truck_id = None
                db.add(conflict)
    device.truck_id = truck.id
    db.add(device)


def list_trucks(
    db: Session,
    *,
    search: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> Page[TruckOut]:
    setting = settings_service.get_settings(db)
    trucks, total = trucks_repo.list_paginated(
        db, search=search, status=status, page=page, page_size=page_size
    )
    latest = readings_repo.get_latest_for_trucks(db, [truck.id for truck in trucks])
    active_counts = alerts_repo.active_counts_by_truck(db)
    items = [
        serialize_truck(
            truck,
            latest_reading=latest.get(truck.id),
            setting=setting,
            active_alerts=active_counts.get(truck.id, 0),
        )
        for truck in trucks
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


def get_truck_detail(db: Session, truck_id: int) -> TruckDetailOut:
    truck = _get_or_fail(db, truck_id)
    setting = settings_service.get_settings(db)
    latest = readings_repo.get_latest_for_truck(db, truck.id)
    active = len(
        [alert for alert in alerts_repo.list_active(db) if alert.truck_id == truck.id]
    )
    return serialize_truck(
        truck,
        latest_reading=latest,
        setting=setting,
        active_alerts=active,
        detail=True,
    )


def create_truck(db: Session, payload: TruckCreate) -> TruckOut:
    plate = payload.normalized_plate()
    if trucks_repo.get_by_plate(db, plate) is not None:
        raise TruckConflictError("Ya existe un camión con esas placas")

    truck = Truck(
        brand=payload.brand.strip(),
        model=payload.model.strip(),
        year=payload.year,
        plate=plate,
        description=payload.description,
        status=payload.status,
    )
    db.add(truck)
    db.flush()

    if payload.route_id is not None:
        _assign_route(db, truck, payload.route_id)
    if payload.device_id is not None:
        _assign_device(db, truck, payload.device_id)

    db.commit()
    db.refresh(truck)
    truck = _get_or_fail(db, truck.id)
    setting = settings_service.get_settings(db)
    latest = readings_repo.get_latest_for_truck(db, truck.id)
    return serialize_truck(truck, latest_reading=latest, setting=setting)


def update_truck(db: Session, truck_id: int, payload: TruckUpdate) -> TruckOut:
    truck = _get_or_fail(db, truck_id)
    fields = payload.model_fields_set

    if "plate" in fields and payload.plate is not None:
        plate = payload.plate.strip().upper()
        existing = trucks_repo.get_by_plate(db, plate)
        if existing is not None and existing.id != truck.id:
            raise TruckConflictError("Ya existe un camión con esas placas")
        truck.plate = plate
    if "brand" in fields and payload.brand is not None:
        truck.brand = payload.brand.strip()
    if "model" in fields and payload.model is not None:
        truck.model = payload.model.strip()
    if "year" in fields and payload.year is not None:
        truck.year = payload.year
    if "description" in fields:
        truck.description = payload.description
    if "status" in fields and payload.status is not None:
        truck.status = payload.status
    if "route_id" in fields:
        _assign_route(db, truck, payload.route_id)
    if "device_id" in fields:
        _assign_device(db, truck, payload.device_id)

    db.add(truck)
    db.commit()
    truck = _get_or_fail(db, truck.id)
    setting = settings_service.get_settings(db)
    latest = readings_repo.get_latest_for_truck(db, truck.id)
    active_counts = alerts_repo.active_counts_by_truck(db)
    return serialize_truck(
        truck,
        latest_reading=latest,
        setting=setting,
        active_alerts=active_counts.get(truck.id, 0),
    )


def delete_truck(db: Session, truck_id: int) -> None:
    truck = _get_or_fail(db, truck_id)
    device = devices_repo.get_by_truck(db, truck.id)
    if device is not None:
        device.truck_id = None
        db.add(device)
    truck.route_id = None
    truck.is_deleted = True
    db.add(truck)
    db.commit()
    alert_service.resolve_truck_alerts(db, truck.id, "Camión eliminado del sistema")


def assign_route_to_truck(db: Session, route_id: int, truck_id: int) -> TruckOut:
    truck = _get_or_fail(db, truck_id)
    _assign_route(db, truck, route_id)
    db.add(truck)
    db.commit()
    truck = _get_or_fail(db, truck.id)
    setting = settings_service.get_settings(db)
    latest = readings_repo.get_latest_for_truck(db, truck.id)
    return serialize_truck(truck, latest_reading=latest, setting=setting)
