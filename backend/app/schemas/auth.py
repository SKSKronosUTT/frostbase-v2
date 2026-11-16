from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    theme: str
    created_at: datetime
    last_login: datetime | None = None


class ThemeUpdate(BaseModel):
    theme: Literal["light", "dark"]


class LoginResponse(BaseModel):
    admin: AdminOut
