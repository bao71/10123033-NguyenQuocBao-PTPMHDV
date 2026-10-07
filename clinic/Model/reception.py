from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from Model.appointments import AppointmentItem


class ReceptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^[0-9A-Fa-f]{16}$")


class ReceptionSummary(BaseModel):
    total: int
    booked: int
    confirmed: int
    checked_in: int
    in_progress: int
    completed: int
    cancelled: int
    no_show: int


class ReceptionListResponse(BaseModel):
    work_date: date
    summary: ReceptionSummary
    items: list[AppointmentItem]
    page: int
    page_size: int
    total: int
