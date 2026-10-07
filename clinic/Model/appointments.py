from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

AppointmentStatus = Literal[
    "booked", "confirmed", "checked_in", "in_progress", "completed", "cancelled", "no_show"
]


class BookingFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    doctor_id: UUID
    schedule_id: UUID
    appointment_at: AwareDatetime
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("appointment_at")
    @classmethod
    def minute_precision(cls, value: datetime) -> datetime:
        if value.second or value.microsecond:
            raise ValueError("Giờ hẹn phải có độ chính xác đến phút")
        return value


class AppointmentCreateRequest(BookingFields):
    patient_id: UUID | None = None


class AppointmentUpdateRequest(BookingFields):
    version: str = Field(pattern=r"^[0-9A-Fa-f]{16}$")


class AppointmentCancelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    version: str = Field(pattern=r"^[0-9A-Fa-f]{16}$")
    cancellation_reason: str = Field(min_length=2, max_length=1000)


class AppointmentItem(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    patient_code: str
    patient_name: str
    doctor_id: UUID
    doctor_code: str
    doctor_name: str
    specialty: str
    schedule_id: UUID | None
    appointment_at: datetime
    ends_at: datetime
    duration_minutes: int
    reason: str | None
    status: AppointmentStatus
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    version: str


class AppointmentListResponse(BaseModel):
    items: list[AppointmentItem]
    page: int
    page_size: int
    total: int


class DoctorItem(BaseModel):
    doctor_id: UUID
    doctor_code: str
    doctor_name: str
    specialty: str


class DoctorListResponse(BaseModel):
    items: list[DoctorItem]
    page: int
    page_size: int
    total: int


class ScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doctor_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    slot_minutes: int = Field(default=30, ge=5, le=240)

    @model_validator(mode="after")
    def valid_interval(self) -> "ScheduleCreateRequest":
        if self.end_at <= self.start_at:
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu")
        if any(value.second or value.microsecond for value in (self.start_at, self.end_at)):
            raise ValueError("Giờ ca làm phải có độ chính xác đến phút")
        minutes = int((self.end_at - self.start_at).total_seconds() / 60)
        if minutes < self.slot_minutes or minutes % self.slot_minutes:
            raise ValueError("Ca làm phải chia hết thành các lượt khám")
        return self


class ScheduleCancelRequest(BaseModel):
    version: str = Field(pattern=r"^[0-9A-Fa-f]{16}$")


class ScheduleItem(BaseModel):
    schedule_id: UUID
    doctor_id: UUID
    doctor_code: str
    doctor_name: str
    specialty: str
    start_at: datetime
    end_at: datetime
    slot_minutes: int
    status: Literal["active", "cancelled"]
    version: str


class ScheduleListResponse(BaseModel):
    items: list[ScheduleItem]
    page: int
    page_size: int
    total: int


class SlotItem(BaseModel):
    schedule_id: UUID
    appointment_at: datetime
    ends_at: datetime
    duration_minutes: int
    available: bool


class SlotListResponse(BaseModel):
    doctor_id: UUID
    work_date: date
    items: list[SlotItem]
