from datetime import timedelta

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.reading import Reading
from app.utils.time import utcnow
from scripts.retention import run_retention


def test_retention_dry_run_and_apply(create_truck, create_device):
    truck_id = create_truck(plate="RET-001")
    device_pk, _, _ = create_device(truck_id, device_id="ESP32-RET-001")

    now = utcnow()
    old = now - timedelta(days=120)
    with SessionLocal() as db:
        db.add(
            Reading(
                device_id=device_pk,
                truck_id=truck_id,
                temperature=2.0,
                humidity=70.0,
                received_at=old,
                reading_timestamp=old,
            )
        )
        db.add(
            Reading(
                device_id=device_pk,
                truck_id=truck_id,
                temperature=3.0,
                humidity=71.0,
                received_at=now,
                reading_timestamp=now,
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                device_id=device_pk,
                alert_type="temperatura",
                message="vieja",
                started_at=old,
                resolved_at=old,
                status="resuelta",
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                device_id=device_pk,
                alert_type="humedad",
                message="reciente",
                started_at=now,
                resolved_at=now,
                status="resuelta",
            )
        )
        db.commit()

        preview = run_retention(db, readings_days=90, alerts_days=90, dry_run=True)
        assert preview.readings == 1
        assert preview.alerts == 1

        applied = run_retention(db, readings_days=90, alerts_days=90)
        assert applied.readings == 1
        assert applied.alerts == 1

    with SessionLocal() as db:
        remaining = db.query(Reading).filter(Reading.device_id == device_pk).all()
        assert len(remaining) == 1
        alerts = db.query(Alert).filter(Alert.device_id == device_pk).all()
        assert len(alerts) == 1
