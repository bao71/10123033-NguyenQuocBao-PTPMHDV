from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from API.dependencies import CurrentUser, DatabaseConnection, request_metadata
from BLL.appointment_service import AppointmentService
from Model.appointments import (
    AppointmentCancelRequest,
    AppointmentCreateRequest,
    AppointmentItem,
    AppointmentListResponse,
    AppointmentStatus,
    AppointmentUpdateRequest,
    DoctorListResponse,
    ScheduleCancelRequest,
    ScheduleCreateRequest,
    ScheduleItem,
    ScheduleListResponse,
    SlotListResponse,
)

router = APIRouter(tags=["Appointments"])


@router.get("/appointments", response_model=AppointmentListResponse)
def list_appointments(
    connection: DatabaseConnection,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=100)] = None,
    doctor_id: UUID | None = None,
    patient_id: UUID | None = None,
    status: AppointmentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: Literal["appointment_at", "created_at", "status"] = "appointment_at",
    sort_order: Literal["asc", "desc"] = "asc",
) -> AppointmentListResponse:
    return AppointmentService().list(
        connection,
        actor,
        page=page,
        page_size=page_size,
        search=search,
        doctor_id=doctor_id,
        patient_id=patient_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/appointments/{appointment_id}", response_model=AppointmentItem)
def get_appointment(appointment_id: UUID, connection: DatabaseConnection, actor: CurrentUser):
    return AppointmentService().get(connection, appointment_id, actor)


@router.post("/appointments", response_model=AppointmentItem, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return AppointmentService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="create",
    )


@router.put("/appointments/{appointment_id}", response_model=AppointmentItem)
def update_appointment(
    appointment_id: UUID,
    payload: AppointmentUpdateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return AppointmentService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="update",
        appointment_id=appointment_id,
    )


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentItem)
def cancel_appointment(
    appointment_id: UUID,
    payload: AppointmentCancelRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return AppointmentService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="cancel",
        appointment_id=appointment_id,
    )


@router.get("/doctors", response_model=DoctorListResponse, tags=["Doctor schedules"])
def list_doctors(
    connection: DatabaseConnection,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=100)] = None,
):
    return AppointmentService().doctors(
        connection,
        actor,
        page=page,
        page_size=page_size,
        search=search,
    )


@router.get(
    "/doctors/{doctor_id}/slots", response_model=SlotListResponse, tags=["Doctor schedules"]
)
def available_slots(
    doctor_id: UUID,
    work_date: date,
    connection: DatabaseConnection,
    actor: CurrentUser,
    patient_id: UUID | None = None,
    exclude_appointment_id: UUID | None = None,
):
    """work_date is the calendar date in Vietnam (UTC+7). Timestamps include UTC offsets."""
    return AppointmentService().slots(
        connection,
        actor,
        doctor_id,
        work_date,
        patient_id,
        exclude_appointment_id,
    )


@router.get("/doctor-schedules", response_model=ScheduleListResponse, tags=["Doctor schedules"])
def list_schedules(
    connection: DatabaseConnection,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    doctor_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: Literal["active", "cancelled"] | None = None,
):
    return AppointmentService().schedules(
        connection,
        actor,
        page=page,
        page_size=page_size,
        doctor_id=doctor_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )


@router.post(
    "/doctor-schedules",
    response_model=ScheduleItem,
    status_code=status.HTTP_201_CREATED,
    tags=["Doctor schedules"],
)
def create_schedule(
    payload: ScheduleCreateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return AppointmentService().write_schedule(
        connection,
        actor,
        request_metadata(request),
        payload=payload,
    )


@router.post(
    "/doctor-schedules/{schedule_id}/cancel", response_model=ScheduleItem, tags=["Doctor schedules"]
)
def cancel_schedule(
    schedule_id: UUID,
    payload: ScheduleCancelRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return AppointmentService().write_schedule(
        connection,
        actor,
        request_metadata(request),
        schedule_id=schedule_id,
        version=payload.version,
    )
