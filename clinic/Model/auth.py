from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, min_length=8, max_length=20, pattern=r"^\+?[0-9 .-]+$")
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, pattern=r"^(male|female|other|unknown)$")

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()

    @field_validator("date_of_birth")
    @classmethod
    def birth_date_must_be_past(cls, value: date | None) -> date | None:
        if value is not None and value >= date.today():
            raise ValueError("Ngày sinh phải nhỏ hơn ngày hiện tại")
        return value


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=40, max_length=512)


class LogoutRequest(RefreshRequest):
    all_sessions: bool = False


class UserResponse(BaseModel):
    user_id: UUID
    username: str
    email: EmailStr | None
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
    patient_id: UUID | None = None
    patient_code: str | None = None
    full_name: str | None = None
    permissions: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
