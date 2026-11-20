from app.core.config import Settings


def test_obsolete_settings_are_removed():
    for field in (
        "device_offline_seconds",
        "weather_city",
        "weather_latitude",
        "weather_longitude",
    ):
        assert field not in Settings.model_fields
