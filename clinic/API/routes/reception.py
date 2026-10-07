from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from API.dependencies import CurrentUser, DatabaseConnection, request_metadata
from BLL.reception_service import ReceptionService
from Model.appointments import AppointmentItem, AppointmentStatus
from Model.reception import ReceptionListResponse, ReceptionRequest

router = APIRouter(tags=["Reception"])


@router.get("/reception", response_model=ReceptionListResponse)
def list_reception(
    connection: DatabaseConnection,
    actor: CurrentUser,
    work_date: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=100)] = None,
    doctor_id: UUID | None = None,
    status: AppointmentStatus | None = None,
    sort_order: Literal["asc", "desc"] = "asc",
):
    """Reception desk by Vietnam calendar date. Summary precedes the status/page filter."""
    return ReceptionService().list(
        connection,
        actor,
        work_date=work_date,
        page=page,
        page_size=page_size,
        search=search,
        doctor_id=doctor_id,
        status=status,
        sort_order=sort_order,
    )


@router.post("/appointments/{appointment_id}/confirm", response_model=AppointmentItem)
def confirm_appointment(
    appointment_id: UUID,
    payload: ReceptionRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return ReceptionService().receive(
        connection,
        actor,
        request_metadata(request),
        appointment_id,
        payload,
        action="confirm",
    )


@router.post("/appointments/{appointment_id}/check-in", response_model=AppointmentItem)
def check_in_appointment(
    appointment_id: UUID,
    payload: ReceptionRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return ReceptionService().receive(
        connection,
        actor,
        request_metadata(request),
        appointment_id,
        payload,
        action="check_in",
    )


@router.post("/appointments/{appointment_id}/no-show", response_model=AppointmentItem)
def mark_no_show(
    appointment_id: UUID,
    payload: ReceptionRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return ReceptionService().receive(
        connection,
        actor,
        request_metadata(request),
        appointment_id,
        payload,
        action="no_show",
    )
