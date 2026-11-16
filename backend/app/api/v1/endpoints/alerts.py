from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentAdmin, DbSession
from app.repositories import alerts as alerts_repo
from app.schemas.alert import AlertOut
from app.schemas.common import Page
from app.services.serializers import serialize_alert

router = APIRouter(prefix="/alerts", tags=["Alertas"])

AlertStatusFilter = Literal["activa", "resuelta"]
AlertTypeFilter = Literal["temperatura", "humedad", "desconexion"]


@router.get("", response_model=Page[AlertOut])
def list_alerts(
    db: DbSession,
    _: CurrentAdmin,
    truck_id: int | None = Query(default=None),
    alert_type: AlertTypeFilter | None = Query(default=None),
    status_filter: AlertStatusFilter | None = Query(default=None, alias="status"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> Page[AlertOut]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha inicial no puede ser posterior a la final",
        )
    alerts, total = alerts_repo.list_paginated(
        db,
        truck_id=truck_id,
        alert_type=alert_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[serialize_alert(alert) for alert in alerts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: DbSession, _: CurrentAdmin) -> AlertOut:
    alert = alerts_repo.get(db, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada"
        )
    return serialize_alert(alert)
