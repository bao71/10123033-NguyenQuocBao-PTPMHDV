from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from API.dependencies import CurrentUser, DatabaseConnection, request_metadata
from BLL.patient_service import PatientService
from Model.patients import (
    PatientCreateRequest,
    PatientItem,
    PatientListResponse,
    PatientUpdateRequest,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=PatientListResponse)
def list_patients(
    connection: DatabaseConnection,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=100)] = None,
    gender: Literal["male", "female", "other", "unknown"] | None = None,
    has_account: bool | None = None,
    sort_by: Literal["patient_code", "full_name", "date_of_birth", "created_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> PatientListResponse:
    return PatientService().list_patients(
        connection,
        actor,
        page=page,
        page_size=page_size,
        search=search,
        gender=gender,
        has_account=has_account,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{patient_id}", response_model=PatientItem)
def get_patient(
    patient_id: UUID, connection: DatabaseConnection, actor: CurrentUser
) -> PatientItem:
    return PatientItem.model_validate(PatientService().get_patient(connection, patient_id, actor))


@router.post("", response_model=PatientItem, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
) -> PatientItem:
    return PatientItem.model_validate(
        PatientService().create_patient(connection, payload, actor, request_metadata(request))
    )


@router.put("/{patient_id}", response_model=PatientItem)
def update_patient(
    patient_id: UUID,
    payload: PatientUpdateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
) -> PatientItem:
    return PatientItem.model_validate(
        PatientService().update_patient(
            connection, patient_id, payload, actor, request_metadata(request)
        )
    )


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: UUID,
    version: Annotated[str, Query(pattern=r"^[0-9A-Fa-f]{16}$")],
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
) -> Response:
    PatientService().delete_patient(
        connection, patient_id, version, actor, request_metadata(request)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
