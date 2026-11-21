"""CRUD administrativo de conductores (G3).

Reglas de negocio (decisiones G0/G3):

- El correo es el identificador de acceso y es único globalmente
  (``login_identities`` lo garantiza entre admins y conductores).
- La contraseña se guarda solo como hash Argon2. Si el administrador no la
  define se genera una temporal que se devuelve **una sola vez**; siempre se
  exige cambio en el primer inicio de sesión.
- La baja es lógica: el correo sigue reservado (se sugiere restaurar la
  cuenta) y las sesiones mueren de inmediato (``token_version += 1``).
- El camión se asigna con historial: cerrar la asignación anterior y abrir la
  nueva en la misma transacción; un camión solo puede tener un conductor
  activo.
"""

import logging
import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.driver import Driver, DriverTruckAssignment
from app.models.route import Route
from app.models.trip import Trip
from app.models.truck import Truck
from app.repositories import driver as driver_repo
from app.schemas.driver import DriverCreate, DriverUpdate
from app.services import auth_service
from app.utils.time import utcnow

logger = logging.getLogger("frostbase.drivers")

TEMP_PASSWORD_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class DriverNotFoundError(Exception):
    pass


class DriverConflictError(Exception):
    """Conflicto de estado: correo tomado, camión ocupado, viaje en curso…"""


class DriverValidationError(Exception):
    pass


def _generate_temporary_password() -> str:
    return "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(16))


def _validate_password(password: str, email: str) -> None:
    if len(password) < 12:
        raise DriverValidationError("La contraseña debe tener al menos 12 caracteres")
    if password == "ChangeMe123!":
        raise DriverValidationError(
            "La contraseña no puede ser la de por defecto del proyecto"
        )
    local_part = email.split("@", 1)[0].lower()
    if local_part and local_part in password.lower():
        raise DriverValidationError(
            "La contraseña no puede contener el correo del conductor"
        )


def _validate_adult(birthdate: date) -> None:
    today = date.today()
    eighteen = today.replace(year=today.year - 18)
    if birthdate > eighteen:
        raise DriverValidationError("El conductor debe ser mayor de 18 años")


def _ensure_email_free(db: Session, email: str) -> None:
    identity = driver_repo.get_identity_by_email(db, email)
    if identity is not None:
        raise DriverConflictError("Ese correo ya está registrado")
    if driver_repo.get_by_email(db, email) is not None:
        raise DriverConflictError("Ese correo ya está registrado")


def _ensure_no_active_trip(db: Session, driver_id: int) -> None:
    active = db.scalar(
        select(Trip).where(Trip.driver_id == driver_id, Trip.state == "in_progress")
    )
    if active is not None:
        raise DriverConflictError(
            "El conductor tiene un viaje en curso; finalízalo antes de continuar"
        )


def _serialize_truck(truck: Truck | None) -> dict | None:
    if truck is None:
        return None
    return {"id": truck.id, "plate": truck.plate}


def create_driver(
    db: Session, payload: DriverCreate, *, admin_id: int
) -> tuple[Driver, str | None]:
    email = payload.email
    _ensure_email_free(db, email)
    _validate_adult(payload.birthdate)

    temporary_password: str | None = None
    if payload.password:
        _validate_password(payload.password, email)
        password_hash = hash_password(payload.password)
    else:
        temporary_password = _generate_temporary_password()
        password_hash = hash_password(temporary_password)

    driver = Driver(
        first_name=payload.first_name,
        last_name=payload.last_name,
        middle_name=payload.middle_name,
        email=email,
        phone=payload.phone,
        birthdate=payload.birthdate,
        password_hash=password_hash,
        must_change_password=True,
        created_by=admin_id,
    )
    db.add(driver)
    db.flush()
    auth_service.ensure_login_identity(
        db, email=email, account_type="driver", account_id=driver.id
    )

    if payload.truck_id is not None:
        assign_truck(db, driver, payload.truck_id, admin_id=admin_id)

    logger.info(
        "driver_created id=%s email=%s admin_id=%s",
        driver.id,
        email,
        admin_id,
    )
    return driver, temporary_password


def update_driver(db: Session, driver: Driver, payload: DriverUpdate) -> Driver:
    changes: dict[str, object] = {}
    if payload.first_name is not None:
        changes["first_name"] = payload.first_name
    if payload.last_name is not None:
        changes["last_name"] = payload.last_name
    if payload.middle_name is not None:
        changes["middle_name"] = payload.middle_name
    if payload.phone is not None:
        changes["phone"] = payload.phone
    if payload.birthdate is not None:
        _validate_adult(payload.birthdate)
        changes["birthdate"] = payload.birthdate

    if payload.email is not None and payload.email != driver.email:
        _ensure_email_free(db, payload.email)
        changes["email"] = payload.email
        # El correo cambió: se reserva el nuevo y se liberan las sesiones.
        auth_service.ensure_login_identity(
            db, email=payload.email, account_type="driver", account_id=driver.id
        )
        driver.token_version += 1

    for field, value in changes.items():
        setattr(driver, field, value)
    db.add(driver)
    db.flush()
    logger.info("driver_updated id=%s fields=%s", driver.id, ",".join(changes))
    return driver


def deactivate_driver(db: Session, driver: Driver) -> list[Route]:
    _ensure_no_active_trip(db, driver.id)

    assignment = driver_repo.active_assignment(db, driver.id)
    if assignment is not None:
        assignment.unassigned_at = utcnow()
        db.add(assignment)

    driver.is_active = False
    driver.token_version += 1
    db.add(driver)
    db.flush()

    affected = list(
        db.scalars(
            select(Route).where(
                Route.assigned_driver_id == driver.id, Route.status == "activa"
            )
        )
    )
    logger.info("driver_deactivated id=%s affected_routes=%s", driver.id, len(affected))
    return affected


def restore_driver(db: Session, driver: Driver) -> Driver:
    driver.is_active = True
    db.add(driver)
    db.flush()
    logger.info("driver_restored id=%s", driver.id)
    return driver


def reset_password(db: Session, driver: Driver) -> str:
    temporary_password = _generate_temporary_password()
    driver.password_hash = hash_password(temporary_password)
    driver.must_change_password = True
    driver.token_version += 1
    db.add(driver)
    db.flush()
    logger.info("driver_password_reset id=%s", driver.id)
    return temporary_password


def assign_truck(
    db: Session, driver: Driver, truck_id: int, *, admin_id: int
) -> DriverTruckAssignment:
    if not driver.is_active:
        raise DriverConflictError("El conductor está inactivo")
    _ensure_no_active_trip(db, driver.id)

    truck = driver_repo.truck_by_id(db, truck_id)
    if truck is None or truck.is_deleted:
        raise DriverValidationError("El camión seleccionado no existe")
    if truck.status == "mantenimiento":
        raise DriverValidationError(
            "El camión está en mantenimiento y no puede asignarse"
        )

    current = driver_repo.active_assignment_for_truck(db, truck_id)
    if current is not None and current.driver_id != driver.id:
        other = driver_repo.get_by_id(db, current.driver_id)
        owner = other.first_name if other else "otro conductor"
        raise DriverConflictError(f"El camión ya está asignado a {owner}")

    existing = driver_repo.active_assignment(db, driver.id)
    if existing is not None:
        if existing.truck_id == truck_id:
            return existing
        existing.unassigned_at = utcnow()
        db.add(existing)

    assignment = DriverTruckAssignment(
        driver_id=driver.id, truck_id=truck_id, assigned_by=admin_id
    )
    db.add(assignment)
    db.flush()
    logger.info(
        "truck_assigned driver_id=%s truck_id=%s admin_id=%s",
        driver.id,
        truck_id,
        admin_id,
    )
    return assignment


def remove_truck(db: Session, driver: Driver) -> None:
    _ensure_no_active_trip(db, driver.id)
    assignment = driver_repo.active_assignment(db, driver.id)
    if assignment is None:
        return
    assignment.unassigned_at = utcnow()
    db.add(assignment)
    db.flush()
    logger.info("truck_removed driver_id=%s", driver.id)


def detail_payload(db: Session, driver: Driver) -> dict:
    assignment = driver_repo.active_assignment(db, driver.id)
    truck = (
        driver_repo.truck_by_id(db, assignment.truck_id)
        if assignment is not None
        else None
    )
    routes = list(
        db.scalars(
            select(Route)
            .where(Route.assigned_driver_id == driver.id)
            .order_by(Route.name)
        )
    )
    payload = {
        "id": driver.id,
        "first_name": driver.first_name,
        "last_name": driver.last_name,
        "middle_name": driver.middle_name,
        "email": driver.email,
        "phone": driver.phone,
        "birthdate": driver.birthdate,
        "is_active": driver.is_active,
        "must_change_password": driver.must_change_password,
        "truck": _serialize_truck(truck),
        "created_at": driver.created_at,
        "last_login": driver.last_login,
        "routes": [
            {"id": route.id, "name": route.name, "status": route.status}
            for route in routes
        ],
    }
    return payload


def admin_payload(db: Session, driver: Driver) -> dict:
    assignment = driver_repo.active_assignment(db, driver.id)
    truck = (
        driver_repo.truck_by_id(db, assignment.truck_id)
        if assignment is not None
        else None
    )
    return {
        "id": driver.id,
        "first_name": driver.first_name,
        "last_name": driver.last_name,
        "middle_name": driver.middle_name,
        "email": driver.email,
        "phone": driver.phone,
        "birthdate": driver.birthdate,
        "is_active": driver.is_active,
        "must_change_password": driver.must_change_password,
        "truck": _serialize_truck(truck),
        "created_at": driver.created_at,
        "last_login": driver.last_login,
    }
