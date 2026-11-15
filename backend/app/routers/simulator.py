from fastapi import APIRouter, Depends

from ..db import get_conn
from ..responses import ok
from ..schemas import SimulateIn
from ..services.simulation import check_simulated_trips, generate_orders, generate_trips

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/orders")
def simulate_orders(payload: SimulateIn, conn=Depends(get_conn)):
    return ok(generate_orders(conn, payload.date))


@router.post("/trips")
def simulate_trips(payload: SimulateIn, conn=Depends(get_conn)):
    return ok(generate_trips(conn, payload.date))


@router.post("/check")
def check_trips(conn=Depends(get_conn)):
    return ok(check_simulated_trips(conn))


@router.post("/generate/{start_date}/{end_date}")
def simulate_range(start_date: str, end_date: str, conn=Depends(get_conn)):
    from datetime import date, timedelta

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    results = []
    cursor = start
    while cursor <= end:
        try:
            orders = generate_orders(conn, cursor)
            trips = generate_trips(conn, cursor)
            results.append({"date": cursor.isoformat(), "orders": len(orders), "trips": len(trips)})
        except Exception as error:
            results.append({"date": cursor.isoformat(), "error": str(error)})
        cursor += timedelta(days=1)
    return ok(results)
