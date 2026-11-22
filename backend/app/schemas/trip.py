"""Schemas de viajes y entregas del conductor (G6)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.trip import Trip, TripOrder


class TripOrderOut(BaseModel):
    id: int
    trip_id: int
    order_index: int
    name: str
    address: str | None = None
    latitude: float
    longitude: float
    state: str
    started_at: datetime | None = None
    delivered_at: datetime | None = None
    failure_reason: str | None = None

    @classmethod
    def from_order(cls, order: TripOrder) -> "TripOrderOut":
        return cls(
            id=order.id,
            trip_id=order.trip_id,
            order_index=order.order_index,
            name=order.name,
            address=order.address,
            latitude=order.latitude,
            longitude=order.longitude,
            state=order.state,
            started_at=order.started_at,
            delivered_at=order.delivered_at,
            failure_reason=order.failure_reason,
        )


class TripOut(BaseModel):
    id: int
    driver_id: int
    truck_id: int
    route_id: int | None = None
    state: str
    started_at: datetime
    ended_at: datetime | None = None
    orders: list[TripOrderOut] = []
    orders_delivered: int = 0
    orders_failed: int = 0
    orders_pending: int = 0
    route_name: str | None = None
    truck_plate: str | None = None

    @classmethod
    def from_trip(cls, trip: Trip) -> "TripOut":
        orders = [TripOrderOut.from_order(o) for o in trip.orders]
        return cls(
            id=trip.id,
            driver_id=trip.driver_id,
            truck_id=trip.truck_id,
            route_id=trip.route_id,
            state=trip.state,
            started_at=trip.started_at,
            ended_at=trip.ended_at,
            orders=orders,
            orders_delivered=len([o for o in orders if o.state == "delivered"]),
            orders_failed=len([o for o in orders if o.state == "failed"]),
            orders_pending=len(
                [o for o in orders if o.state in ("pending", "in_delivery")]
            ),
            route_name=trip.route.name if trip.route else None,
            truck_plate=trip.truck.plate if trip.truck else None,
        )


class TripStartIn(BaseModel):
    route_id: int


class TripEndIn(BaseModel):
    confirm_pending: bool = False
    failure_reason: str | None = Field(default=None, max_length=500)


class OrderFailIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CanStartTripOut(BaseModel):
    can_start: bool
    blocking_reason: str | None = None
    route_id: int | None = None
    current_trip_id: int | None = None
