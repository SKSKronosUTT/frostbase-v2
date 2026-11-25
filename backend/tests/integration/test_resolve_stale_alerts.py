"""Limpieza de alertas de prueba (B0): simulación, filtros e idempotencia."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.device import Device
from app.utils.time import utcnow
from scripts.resolve_stale_alerts import DEFAULT_DEVICE_PREFIXES, run_cleanup


def _add_alert(db, *, truck_id, device_pk, alert_type, started_at):
    db.add(
        Alert(
            truck_id=truck_id,
            device_id=device_pk,
            alert_type=alert_type,
            status="activa",
            started_at=started_at,
        )
    )


def _seed(create_truck, create_device):
    now = utcnow()
    load_truck = create_truck(plate="CLEAN-LOAD")
    load_device, _, _ = create_device(load_truck, device_id="LOAD-CLEAN-1")
    e2e_truck = create_truck(plate="CLEAN-E2E")
    e2e_device, _, _ = create_device(e2e_truck, device_id="E2E-CLEAN-1")
    door_truck = create_truck(plate="CLEAN-DOOR")
    door_device, _, _ = create_device(door_truck, device_id="ESP32-DOOR-CLEAN")
    demo_truck = create_truck(plate="CLEAN-DEMO")
    demo_device, _, _ = create_device(demo_truck, device_id="ESP32-DEMO-CLEAN")
    real_truck = create_truck(plate="CLEAN-REAL")
    real_device, _, _ = create_device(real_truck, device_id="REAL-CLEAN")

    with SessionLocal() as db:
        _add_alert(
            db,
            truck_id=load_truck,
            device_pk=load_device,
            alert_type="temperatura",
            started_at=now - timedelta(days=3),
        )
        _add_alert(
            db,
            truck_id=load_truck,
            device_pk=load_device,
            alert_type="humedad",
            started_at=now - timedelta(minutes=5),
        )
        _add_alert(
            db,
            truck_id=e2e_truck,
            device_pk=e2e_device,
            alert_type="desconexion",
            started_at=now - timedelta(days=3),
        )
        _add_alert(
            db,
            truck_id=door_truck,
            device_pk=door_device,
            alert_type="puerta",
            started_at=now - timedelta(days=2),
        )
        _add_alert(
            db,
            truck_id=demo_truck,
            device_pk=demo_device,
            alert_type="temperatura",
            started_at=now - timedelta(days=3),
        )
        _add_alert(
            db,
            truck_id=real_truck,
            device_pk=real_device,
            alert_type="temperatura",
            started_at=now - timedelta(days=3),
        )
        db.execute(
            update(Device)
            .where(
                Device.id.in_(
                    [
                        load_device,
                        e2e_device,
                        door_device,
                        demo_device,
                        real_device,
                    ]
                )
            )
            .values(last_seen=now)
        )
        db.commit()


def test_cleanup_preview_age_filter_apply_and_idempotency(create_truck, create_device):
    _seed(create_truck, create_device)
    with SessionLocal() as db:
        preview = run_cleanup(db, dry_run=True, sample_limit=10)
        assert preview.total == 4
        assert preview.by_prefix == {
            "LOAD-": 2,
            "E2E-": 1,
            "ESP32-DOOR-": 1,
        }
        assert preview.by_type == {
            "temperatura": 1,
            "humedad": 1,
            "desconexion": 1,
            "puerta": 1,
        }
        assert preview.applied == 0
        assert preview.devices_to_silence == 3
        assert len(preview.samples) == 4

        recent = run_cleanup(db, older_than_days=2, dry_run=True)
        assert recent.total == 3
        assert recent.by_prefix["LOAD-"] == 1

        applied = run_cleanup(db, dry_run=False)
        assert applied.applied == 4
        assert applied.devices_silenced == 3

        statuses = {row.truck.plate: row.status for row in db.scalars(select(Alert))}
        assert statuses["CLEAN-LOAD"] == "resuelta"
        assert statuses["CLEAN-E2E"] == "resuelta"
        assert statuses["CLEAN-DOOR"] == "resuelta"
        assert statuses["CLEAN-DEMO"] == "activa"
        assert statuses["CLEAN-REAL"] == "activa"

        last_seen = {row.device_id: row.last_seen for row in db.scalars(select(Device))}
        assert last_seen["LOAD-CLEAN-1"] is None
        assert last_seen["E2E-CLEAN-1"] is None
        assert last_seen["ESP32-DOOR-CLEAN"] is None
        assert last_seen["ESP32-DEMO-CLEAN"] is not None
        assert last_seen["REAL-CLEAN"] is not None

        again = run_cleanup(db, dry_run=False)
        assert again.total == 0
        assert again.applied == 0
        assert again.devices_silenced == 0


def test_cleanup_can_keep_devices(create_truck, create_device):
    _seed(create_truck, create_device)
    with SessionLocal() as db:
        result = run_cleanup(db, dry_run=False, silence_devices=False)
        assert result.applied == 4
        assert result.devices_silenced == 0
        last_seen = {row.device_id: row.last_seen for row in db.scalars(select(Device))}
        assert last_seen["LOAD-CLEAN-1"] is not None
        assert last_seen["E2E-CLEAN-1"] is not None


def test_cleanup_requires_prefixes(create_truck, create_device):
    _seed(create_truck, create_device)
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            run_cleanup(db, device_prefixes=(), dry_run=True)


def test_default_prefixes_preserve_demo():
    assert "LOAD-" in DEFAULT_DEVICE_PREFIXES
    assert "E2E-" in DEFAULT_DEVICE_PREFIXES
    assert "ESP32-DEMO-" not in DEFAULT_DEVICE_PREFIXES
