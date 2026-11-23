"""Contrato de los endpoints de solo lectura para el agente (A2)."""

from pydantic import BaseModel


class AgentFleetSummaryOut(BaseModel):
    generated_at: str
    timezone: str
    window_start: str
    trucks_total: int
    trucks_by_status: dict[str, int]
    alerts_active: int
    alerts_by_type: dict[str, int]
    alerts_created_today: int
    alerts_created_today_by_type: dict[str, int]
    alerts_resolved_today: int
    trips_active: int
    pending_orders: int
    routes_today: int


class AgentAlertOut(BaseModel):
    alert_type: str
    truck_plate: str | None = None
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    started_at: str
    age_minutes: int
    acknowledged: bool = False


class AgentAlertsOut(BaseModel):
    generated_at: str
    timezone: str
    items: list[AgentAlertOut]


class AgentTodayAlertOut(BaseModel):
    alert_type: str
    truck_plate: str | None = None
    status: str
    started_at: str
    resolved_at: str | None = None
    acknowledged: bool = False


class AgentAlertsTodayOut(BaseModel):
    generated_at: str
    timezone: str
    window_start: str
    created_total: int
    resolved_total: int
    active_total: int
    created_by_type: dict[str, int]
    resolved_by_type: dict[str, int]
    active_by_type: dict[str, int]
    items: list[AgentTodayAlertOut]


class AgentTruckStatusOut(BaseModel):
    generated_at: str
    timezone: str
    truck_id: int
    plate: str
    status: str
    temperature: float | None = None
    humidity: float | None = None
    age_minutes: int | None = None
    door_open: bool | None = None
    temperature_min: float
    temperature_max: float
    humidity_min: float
    humidity_max: float
    active_alerts: list[str] = []


class AgentTripOut(BaseModel):
    driver_alias: str
    truck_plate: str
    started_at: str
    orders_total: int
    orders_delivered: int
    orders_failed: int
    orders_pending: int


class AgentTripsOut(BaseModel):
    generated_at: str
    timezone: str
    items: list[AgentTripOut]


class AgentRouteOut(BaseModel):
    name: str
    driver_alias: str
    points: int
    pending_orders: int


class AgentRoutesOut(BaseModel):
    generated_at: str
    timezone: str
    items: list[AgentRouteOut]


class AgentThresholdOverrideOut(BaseModel):
    plate: str
    temperature_min: float
    temperature_max: float
    humidity_min: float
    humidity_max: float


class AgentThresholdsOut(BaseModel):
    generated_at: str
    timezone: str
    temperature_min: float
    temperature_max: float
    humidity_min: float
    humidity_max: float
    overrides: list[AgentThresholdOverrideOut]
