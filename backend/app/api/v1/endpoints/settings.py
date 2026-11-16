from fastapi import APIRouter

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.setting import SettingsOut, SettingsUpdate
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["Configuración"])


@router.get("", response_model=SettingsOut)
def get_settings(db: DbSession, _: CurrentAdmin) -> SettingsOut:
    return settings_service.get_settings_out(db)


@router.put("", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate, db: DbSession, _: CurrentAdmin
) -> SettingsOut:
    return settings_service.update_settings(db, payload)
