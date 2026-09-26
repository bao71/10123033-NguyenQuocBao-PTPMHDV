from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserListItem(BaseModel):
    user_id: UUID
    username: str
    email: str | None
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserListItem]
    page: int
    page_size: int
    total: int


class StaffCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    phone: str | None = Field(default=None, min_length=8, max_length=20, pattern=r"^\+?[0-9 .-]+$")
    role: str = Field(pattern=r"^(Receptionist|Doctor|Pharmacist)$")
    doctor_code: str | None = Field(default=None, min_length=2, max_length=30)
    specialty: str | None = Field(default=None, min_length=2, max_length=200)
    license_number: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_doctor_profile(self) -> "StaffCreateRequest":
        if self.role == "Doctor" and (not self.doctor_code or not self.specialty):
            raise ValueError("Bác sĩ cần mã bác sĩ và chuyên khoa.")
        if self.role != "Doctor" and any(
            (self.doctor_code, self.specialty, self.license_number)
        ):
            raise ValueError("Hồ sơ bác sĩ chỉ dùng cho vai trò Bác sĩ.")
        self.username = self.username.lower()
        return self


class UserStatusRequest(BaseModel):
    is_active: bool


class RoleItem(BaseModel):
    code: str
    name: str
    description: str | None
    permissions: list[str]


class RoleListResponse(BaseModel):
    roles: list[RoleItem]
    available_permissions: list[str]


class RolePermissionsRequest(BaseModel):
    permissions: list[str] = Field(max_length=100)
