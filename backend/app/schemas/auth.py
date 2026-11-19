from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MIN_PASSWORD_LENGTH = 12


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    theme: str
    must_change_password: bool = False
    created_at: datetime
    last_login: datetime | None = None


class ThemeUpdate(BaseModel):
    theme: Literal["light", "dark"]


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=255)

    @field_validator("new_password")
    @classmethod
    def _not_default_password(cls, value: str) -> str:
        if value == "ChangeMe123!":
            raise ValueError("La nueva contraseña no puede ser la de por defecto")
        return value

    @model_validator(mode="after")
    def _must_differ(self) -> "PasswordChangeRequest":
        if self.current_password == self.new_password:
            raise ValueError("La nueva contraseña debe ser distinta de la actual")
        return self


class LoginResponse(BaseModel):
    admin: AdminOut
