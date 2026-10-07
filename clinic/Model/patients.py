from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PatientFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=200)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, pattern=r"^(male|female|other|unknown)$")
    phone: str | None = Field(default=None, min_length=8, max_length=20, pattern=r"^\+?[0-9 .-]+$")
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    insurance_number: str | None = Field(default=None, max_length=50)

    @field_validator("date_of_birth")
    @classmethod
    def birth_date_must_be_past(cls, value: date | None) -> date | None:
        if value is not None and value >= date.today():
            raise ValueError("Ngày sinh phải nhỏ hơn ngày hiện tại")
        return value


class PatientCreateRequest(PatientFields):
    pass


class PatientUpdateRequest(PatientFields):
    version: str = Field(pattern=r"^[0-9A-Fa-f]{16}$")


class PatientItem(PatientFields):
    patient_id: UUID
    patient_code: str
    has_account: bool
    created_at: datetime
    updated_at: datetime
    version: str


class PatientListResponse(BaseModel):
    items: list[PatientItem]
    page: int
    page_size: int
    total: int
