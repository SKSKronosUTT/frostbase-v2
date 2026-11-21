"""Endpoints del conductor (G2: perfil; el portal completo llega en G5).

El ID del conductor siempre viene del token: nunca se acepta por parámetro.
"""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentDriver, DbSession
from app.models.driver import DriverTruckAssignment
from app.models.truck import Truck
from app.schemas.driver import DriverMeOut, DriverTruckBrief

router = APIRouter(prefix="/driver", tags=["Conductor"])


@router.get("/me", response_model=DriverMeOut)
def me(driver: CurrentDriver, db: DbSession) -> DriverMeOut:
    assignment = db.scalar(
        select(DriverTruckAssignment).where(
            DriverTruckAssignment.driver_id == driver.id,
            DriverTruckAssignment.unassigned_at.is_(None),
        )
    )
    truck = db.get(Truck, assignment.truck_id) if assignment is not None else None
    out = DriverMeOut.model_validate(driver)
    out.truck = DriverTruckBrief(id=truck.id, plate=truck.plate) if truck else None
    return out
