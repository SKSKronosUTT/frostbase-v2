"""Asignación efectiva camión ↔ ruta, derivada del conductor (G4.1).

Regla única de dominio (decisión G0/G4.1): **el camión de una ruta es el
camión activo de su dueño** y, a la inversa, **la ruta de un camión es la ruta
de hoy (o la única) del conductor activo asignado a ese camión**.

``trucks.route_id`` queda como vínculo legado de solo lectura: nadie lo escribe
ya y los lectores (dashboard, flota, ``/iot/config``) usan estos derivados. El
reporte de conciliación enumera los vínculos legados que difieren del derivado
para que el administrador los revise antes de que la columna desaparezca en
G6.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.driver import Driver, DriverTruckAssignment
from app.models.route import Route
from app.models.truck import Truck
from app.repositories import driver as driver_repo

CASE_OWNER_WITHOUT_TRUCK = "owner_without_truck"
CASE_OWNER_TRUCK_DIFFERS = "owner_truck_differs"
CASE_NO_OWNER = "no_owner"


def today_weekday() -> int:
    """Día de semana actual en la zona de negocio (0=domingo … 6=sábado)."""
    return datetime.now(settings.tz).isoweekday() % 7


def _owner_if_active(db: Session, route: Route) -> Driver | None:
    if route.assigned_driver_id is None:
        return None
    driver = driver_repo.get_by_id(db, route.assigned_driver_id)
    if driver is None or not driver.is_active:
        return None
    return driver


def effective_truck(db: Session, route: Route) -> Truck | None:
    """Camión de la ruta: el camión activo de su dueño (legado ignorado)."""
    driver = _owner_if_active(db, route)
    if driver is None:
        return None
    assignment = driver_repo.active_assignment(db, driver.id)
    if assignment is None:
        return None
    return driver_repo.truck_by_id(db, assignment.truck_id)


def routes_for_driver(db: Session, driver_id: int) -> list[Route]:
    return list(
        db.scalars(
            select(Route)
            .options(selectinload(Route.delivery_days))
            .where(
                Route.assigned_driver_id == driver_id,
                Route.status == "activa",
            )
            .order_by(Route.name)
        )
    )


def _resolve_route(routes: list[Route], weekday: int) -> Route | None:
    """Ruta de hoy; si no hay, la única ruta activa del conductor."""
    for route in routes:
        if any(day.weekday == weekday for day in route.delivery_days):
            return route
    if len(routes) == 1:
        return routes[0]
    return None


def effective_route_for_truck(db: Session, truck: Truck | None) -> Route | None:
    """Ruta de un camión: la de hoy (o la única) de su conductor activo."""
    if truck is None:
        return None
    assignment = driver_repo.active_assignment_for_truck(db, truck.id)
    if assignment is None:
        return None
    driver = driver_repo.get_by_id(db, assignment.driver_id)
    if driver is None or not driver.is_active:
        return None
    return _resolve_route(routes_for_driver(db, driver.id), today_weekday())


def effective_routes_for_trucks(
    db: Session, truck_ids: list[int]
) -> dict[int, Route | None]:
    """Versión en lote de ``effective_route_for_truck`` (dashboard/flota)."""
    result: dict[int, Route | None] = {truck_id: None for truck_id in truck_ids}
    if not truck_ids:
        return result

    assignments = db.scalars(
        select(DriverTruckAssignment).where(
            DriverTruckAssignment.truck_id.in_(truck_ids),
            DriverTruckAssignment.unassigned_at.is_(None),
        )
    ).all()
    truck_to_driver = {
        assignment.truck_id: assignment.driver_id for assignment in assignments
    }
    driver_ids = list(set(truck_to_driver.values()))
    if not driver_ids:
        return result

    active_driver_ids = set(
        db.scalars(
            select(Driver.id).where(
                Driver.id.in_(driver_ids), Driver.is_active.is_(True)
            )
        )
    )
    routes = list(
        db.scalars(
            select(Route)
            .options(selectinload(Route.delivery_days))
            .where(
                Route.assigned_driver_id.in_(active_driver_ids),
                Route.status == "activa",
            )
        )
    )
    weekday = today_weekday()
    by_driver: dict[int, list[Route]] = {}
    for route in routes:
        owner_id = route.assigned_driver_id or 0
        by_driver.setdefault(owner_id, []).append(route)

    for truck_id, driver_id in truck_to_driver.items():
        if driver_id not in active_driver_ids:
            continue
        result[truck_id] = _resolve_route(by_driver.get(driver_id, []), weekday)
    return result


def _assignment_map_for_drivers(
    db: Session, driver_ids: list[int]
) -> dict[int, DriverTruckAssignment]:
    rows = db.scalars(
        select(DriverTruckAssignment).where(
            DriverTruckAssignment.driver_id.in_(driver_ids),
            DriverTruckAssignment.unassigned_at.is_(None),
        )
    ).all()
    return {row.driver_id: row for row in rows}


def legacy_mismatches(db: Session) -> list[dict]:
    """Rutas cuyo vínculo legado difiere del camión derivado del dueño.

    Clasificación y acción sugerida:

    - ``owner_without_truck``: el dueño no tiene camión pero la ruta tiene
      vínculo legado. Acción sugerida: convertir ese camión en la asignación
      del conductor (``convertible=True`` solo si el camión está libre).
    - ``owner_truck_differs``: el dueño tiene otro camión; la ruta ya muestra
      el derivado, el legado sobra (se libera solo al borrar la columna).
    - ``no_owner``: ruta sin dueño con vínculo legado; asígnele un conductor
      y el camión saldrá de él.
    """
    routes = list(
        db.scalars(
            select(Route)
            .options(selectinload(Route.delivery_days))
            .order_by(Route.name)
        )
    )
    owner_ids = [
        route.assigned_driver_id for route in routes if route.assigned_driver_id
    ]
    drivers = {
        driver.id: driver
        for driver in db.scalars(select(Driver).where(Driver.id.in_(owner_ids or [0])))
    }
    assignments = _assignment_map_for_drivers(db, owner_ids or [0])

    report: list[dict] = []
    for route in routes:
        legacy_truck = route.truck
        driver = drivers.get(route.assigned_driver_id or 0)
        if driver is not None and not driver.is_active:
            driver = None

        assignment = assignments.get(driver.id) if driver else None
        derived_truck_id = assignment.truck_id if assignment else None

        if legacy_truck is None:
            # Sin legado no hay conciliación pendiente, muestre o no camión.
            continue
        if derived_truck_id == legacy_truck.id:
            continue  # el legado coincide con el derivado: sin acción

        owner = {"id": driver.id, "full_name": driver.full_name} if driver else None
        legacy = {"id": legacy_truck.id, "plate": legacy_truck.plate}
        derived = None
        if derived_truck_id is not None:
            derived_truck = driver_repo.truck_by_id(db, derived_truck_id)
            if derived_truck is not None:
                derived = {
                    "id": derived_truck.id,
                    "plate": derived_truck.plate,
                }

        if driver is None:
            case = CASE_NO_OWNER
            suggestion = (
                "Asigne un conductor a la ruta; el camión saldrá de él. "
                "El vínculo legado deja de usarse."
            )
            convertible = False
            target_driver_id = None
        elif assignment is None:
            case = CASE_OWNER_WITHOUT_TRUCK
            occupied = driver_repo.active_assignment_for_truck(db, legacy_truck.id)
            convertible = occupied is None
            suggestion = (
                "Convierta el camión de la ruta en el camión del conductor."
                if convertible
                else f"El camión {legacy_truck.plate} pertenece a otro conductor; "
                "revise el relevo antes de asignarlo."
            )
            target_driver_id = driver.id
        else:
            case = CASE_OWNER_TRUCK_DIFFERS
            suggestion = (
                "La ruta ya muestra el camión del conductor; el vínculo "
                "legado sobra y se retirará con la columna en G6."
            )
            convertible = False
            target_driver_id = None

        report.append(
            {
                "route_id": route.id,
                "route_name": route.name,
                "case": case,
                "owner": owner,
                "legacy_truck": legacy,
                "effective_truck": derived,
                "suggestion": suggestion,
                "convertible": convertible,
                "target_driver_id": target_driver_id,
            }
        )
    return report
