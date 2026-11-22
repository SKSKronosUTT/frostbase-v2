from sqlalchemy.orm import Session

from app.core.cache import cache_delete
from app.models.setting import Setting
from app.repositories import settings as settings_repo
from app.schemas.setting import SettingsOut, SettingsUpdate
from app.utils.time import ensure_utc


def serialize_settings(setting: Setting) -> SettingsOut:
    return SettingsOut(
        temperature_ideal=setting.temperature_ideal,
        temperature_tolerance=setting.temperature_tolerance,
        humidity_ideal=setting.humidity_ideal,
        humidity_tolerance=setting.humidity_tolerance,
        temperature_min=setting.temperature_min,
        temperature_max=setting.temperature_max,
        humidity_min=setting.humidity_min,
        humidity_max=setting.humidity_max,
        offline_timeout_seconds=setting.offline_timeout_seconds,
        door_open_grace_seconds=setting.door_open_grace_seconds,
        weather_city=setting.weather_city,
        weather_latitude=setting.weather_latitude,
        weather_longitude=setting.weather_longitude,
        updated_at=ensure_utc(setting.updated_at),
    )


def get_settings(db: Session) -> Setting:
    return settings_repo.get_or_create(db)


def ensure_settings(db: Session) -> Setting:
    return settings_repo.ensure_default(db)


def get_settings_out(db: Session) -> SettingsOut:
    return serialize_settings(get_settings(db))


def update_settings(db: Session, payload: SettingsUpdate) -> SettingsOut:
    setting = get_settings(db)
    setting.temperature_ideal = payload.temperature_ideal
    setting.temperature_tolerance = payload.temperature_tolerance
    setting.humidity_ideal = payload.humidity_ideal
    setting.humidity_tolerance = payload.humidity_tolerance
    setting.offline_timeout_seconds = payload.offline_timeout_seconds
    if payload.door_open_grace_seconds is not None:
        setting.door_open_grace_seconds = payload.door_open_grace_seconds
    setting.weather_city = payload.weather_city
    setting.weather_latitude = payload.weather_latitude
    setting.weather_longitude = payload.weather_longitude
    settings_repo.save(db, setting)
    cache_delete("dashboard:summary")
    return serialize_settings(setting)
