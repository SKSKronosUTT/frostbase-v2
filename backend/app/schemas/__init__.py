from app.schemas.alert import AlertOut
from app.schemas.auth import (
    AdminOut,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    ThemeUpdate,
)
from app.schemas.common import MessageOut, Page
from app.schemas.dashboard import (
    DashboardAlert,
    DashboardSummary,
    DashboardTruck,
    WeatherOut,
)
from app.schemas.device import DeviceCreate, DeviceCreatedOut, DeviceOut, DeviceUpdate
from app.schemas.iot import IoTConfigResponse, IoTReadingResponse, ReadingIngest
from app.schemas.reading import ReadingOut
from app.schemas.route import (
    AssignedTruckOut,
    DeliveryPointIn,
    DeliveryPointOut,
    RouteBrief,
    RouteBriefWithGeometry,
    RouteCreate,
    RouteOut,
    RouteUpdate,
)
from app.schemas.setting import SettingsOut, SettingsUpdate
from app.schemas.truck import TruckCreate, TruckDetailOut, TruckOut, TruckUpdate

__all__ = [
    "AdminOut",
    "AlertOut",
    "AssignedTruckOut",
    "DashboardAlert",
    "DashboardSummary",
    "DashboardTruck",
    "DeliveryPointIn",
    "DeliveryPointOut",
    "DeviceCreate",
    "DeviceCreatedOut",
    "DeviceOut",
    "DeviceUpdate",
    "IoTConfigResponse",
    "IoTReadingResponse",
    "LoginRequest",
    "LoginResponse",
    "MessageOut",
    "Page",
    "PasswordChangeRequest",
    "ReadingIngest",
    "ReadingOut",
    "RouteBrief",
    "RouteBriefWithGeometry",
    "RouteCreate",
    "RouteOut",
    "RouteUpdate",
    "SettingsOut",
    "SettingsUpdate",
    "ThemeUpdate",
    "TruckCreate",
    "TruckDetailOut",
    "TruckOut",
    "TruckUpdate",
    "WeatherOut",
]
