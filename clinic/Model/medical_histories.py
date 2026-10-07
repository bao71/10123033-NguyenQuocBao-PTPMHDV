from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

HistoryType = Literal["allergy", "condition", "surgery", "family", "medication", "other"]


class MedicalHistoryFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: HistoryType
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    onset_date: date | None = None
    is_active: bool = True

    @field_validator("onset_date")
    @classmethod
    def onset_cannot_be_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Ngày bắt đầu không được ở tương lai")
        return value


class MedicalHistoryCreateRequest(MedicalHistoryFields):
    pass


class MedicalHistoryUpdateRequest(MedicalHistoryFields):
    version: str = Field(pattern=r"^[0-9A-Fa-f]{16}$")


class MedicalHistoryItem(MedicalHistoryFields):
    history_id: UUID
    patient_id: UUID
    created_by: UUID
    version_no: int
    created_at: datetime
    updated_at: datetime
    version: str


class MedicalHistoryListResponse(BaseModel):
    items: list[MedicalHistoryItem]
    page: int
    page_size: int
    total: int
