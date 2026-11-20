from datetime import timedelta

from app.core.database import SessionLocal
from app.models.device import Device
from app.services import alert_service, settings_service
from app.utils.time import utcnow


def test_disconnect_watcher_creates_and_resolves_alert(create_truck, create_device):
    truck_id = create_truck(plate="WATCH-001")
    device_pk, _, _ = create_device(truck_id, device_id="ESP32-WATCH-001")

    old_seen = utcnow() - timedelta(hours=1)
    with SessionLocal() as db:
        device = db.get(Device, device_pk)
        device.last_seen = old_seen
        db.commit()
        setting = settings_service.get_settings(db)
        created = alert_service.check_disconnected_devices(db, setting)
        db.commit()
    assert created == 1

    with SessionLocal() as db:
        active = alert_service.alerts_repo.find_active(
            db, device_pk, alert_service.DISCONNECT_TYPE
        )
        assert active is not None
        assert active.started_at == old_seen
        assert active.status == "activa"

    with SessionLocal() as db:
        device = db.get(Device, device_pk)
        device.last_seen = utcnow()
        db.commit()
        setting = settings_service.get_settings(db)
        alert_service.check_disconnected_devices(db, setting)
        db.commit()

    with SessionLocal() as db:
        assert (
            alert_service.alerts_repo.find_active(
                db, device_pk, alert_service.DISCONNECT_TYPE
            )
            is None
        )
