"""Endpoints de solo lectura para el agente (A2).

Autenticados con un token propio (``Authorization: Bearer``), no con JWT de
administrador. Solo GET: el agente nunca puede escribir en FrostBase.
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.api.deps import AgentReadToken, DbSession
from app.core.ratelimit import RateLimit
from app.schemas.agent_read import (
    AgentAlertsOut,
    AgentAlertsTodayOut,
    AgentFleetSummaryOut,
    AgentRoutesOut,
    AgentThresholdsOut,
    AgentTripsOut,
    AgentTruckStatusOut,
)
from app.services import agent_read
from app.services.ai_agent import audit

router = APIRouter(prefix="/agent-read", tags=["Agente (solo lectura)"])

_limiter = RateLimit("agent-read", limit=60, window_seconds=60)


def _check(request: Request, response: Response) -> None:
    _limiter.check(request, response)
    # Salud del pull: solo ruta, sin token ni contenido de la respuesta.
    audit.record_event(
        admin_id=None,
        action="read",
        status="ok",
        detail=request.url.path,
    )


@router.get("/fleet-summary", response_model=AgentFleetSummaryOut)
def fleet_summary(
    request: Request,
    response: Response,
    _: AgentReadToken,
    db: DbSession,
) -> AgentFleetSummaryOut:
    _check(request, response)
    return agent_read.fleet_summary(db)


@router.get("/alerts/today", response_model=AgentAlertsTodayOut)
def alerts_today(
    request: Request,
    response: Response,
    _: AgentReadToken,
    db: DbSession,
    limit: int = Query(default=10, ge=1, le=20),
) -> AgentAlertsTodayOut:
    """Alertas creadas/resueltas desde medianoche local (America/Tijuana)."""
    _check(request, response)
    return agent_read.alerts_today(db, limit=limit)


@router.get("/alerts", response_model=AgentAlertsOut)
def alerts(
    request: Request,
    response: Response,
    _: AgentReadToken,
    db: DbSession,
    limit: int = Query(default=10, ge=1, le=20),
) -> AgentAlertsOut:
    _check(request, response)
    return agent_read.alerts(db, limit=limit)


@router.get("/trucks/{truck_id}/status", response_model=AgentTruckStatusOut)
def truck_status(
    truck_id: int,
    request: Request,
    response: Response,
    _: AgentReadToken,
    db: DbSession,
) -> AgentTruckStatusOut:
    _check(request, response)
    result = agent_read.truck_status(db, truck_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camión no encontrado",
        )
    return result


@router.get("/trips/active", response_model=AgentTripsOut)
def active_trips(
    request: Request,
    response: Response,
    _: AgentReadToken,
    db: DbSession,
    limit: int = Query(default=5, ge=1, le=10),
) -> AgentTripsOut:
    _check(request, response)
    return agent_read.active_trips(db, limit=limit)


@router.get("/routes/today", response_model=AgentRoutesOut)
def routes_today(
    request: Request,
    response: Response,
    _: AgentReadToken,
    db: DbSession,
    limit: int = Query(default=6, ge=1, le=10),
) -> AgentRoutesOut:
    _check(request, response)
    return agent_read.routes_today(db, limit=limit)


@router.get("/thresholds", response_model=AgentThresholdsOut)
def thresholds(
    request: Request,
    response: Response,
    _: AgentReadToken,
    db: DbSession,
) -> AgentThresholdsOut:
    _check(request, response)
    return agent_read.thresholds(db)
