import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")
MIN_PASSWORD_LENGTH = 12


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    middle_name: str | None = None
    email: str
    phone: str
    must_change_password: bool = False
    created_at: datetime
    last_login: datetime | None = None


class DriverTruckBrief(BaseModel):
    id: int
    plate: str


class DriverMeOut(DriverOut):
    truck: DriverTruckBrief | None = None


class DriverRouteBrief(BaseModel):
    id: int
    name: str
    status: str


class DriverAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    middle_name: str | None = None
    email: str
    phone: str
    birthdate: date
    is_active: bool
    must_change_password: bool
    truck: DriverTruckBrief | None = None
    created_at: datetime
    last_login: datetime | None = None


class DriverCreatedOut(DriverAdminOut):
    """La contraseña temporal solo aparece en la respuesta de alta/reset."""

    temporary_password: str | None = None


class DriverDetailOut(DriverAdminOut):
    routes: list[DriverRouteBrief] = []


class DriverDeactivationOut(BaseModel):
    id: int
    affected_routes: list[DriverRouteBrief] = []


class DriverTripOut(BaseModel):
    id: int
    state: str
    started_at: datetime
    ended_at: datetime | None = None
    truck_id: int


class DriverCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(min_length=10, max_length=20)
    birthdate: date
    password: str | None = Field(default=None, min_length=12, max_length=255)
    truck_id: int | None = None

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("formato de correo inválido")
        return normalized

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("el teléfono debe tener entre 10 y 15 dígitos")
        return normalized

    @field_validator("first_name", "last_name", "middle_name")
    @classmethod
    def _strip_names(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("no puede estar vacío")
        return normalized


class DriverUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    phone: str | None = Field(default=None, min_length=10, max_length=20)
    birthdate: date | None = None

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("formato de correo inválido")
        return normalized

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("el teléfono debe tener entre 10 y 15 dígitos")
        return normalized

    @field_validator("first_name", "last_name", "middle_name")
    @classmethod
    def _strip_names(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("no puede estar vacío")
        return normalized


class DriverTruckIn(BaseModel):
    truck_id: int


class DriverOptionOut(BaseModel):
    id: int
    label: str
