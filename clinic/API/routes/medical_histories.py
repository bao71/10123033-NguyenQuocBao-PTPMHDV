from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from API.dependencies import CurrentUser, DatabaseConnection, request_metadata
from BLL.medical_history_service import MedicalHistoryService
from Model.medical_histories import (
    HistoryType,
    MedicalHistoryCreateRequest,
    MedicalHistoryItem,
    MedicalHistoryListResponse,
    MedicalHistoryUpdateRequest,
)

router = APIRouter(prefix="/patients/{patient_id}/medical-histories", tags=["Medical histories"])


@router.get("", response_model=MedicalHistoryListResponse)
def list_medical_histories(
    patient_id: UUID,
    connection: DatabaseConnection,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    type: HistoryType | None = None,
    is_active: bool | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    sort_by: Literal["created_at", "onset_date", "name"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> MedicalHistoryListResponse:
    return MedicalHistoryService().list_for_patient(
        connection, patient_id, actor, page=page, page_size=page_size,
        type=type, is_active=is_active, search=search,
        sort_by=sort_by, sort_order=sort_order,
    )


@router.get("/{history_id}", response_model=MedicalHistoryItem)
def get_medical_history(
    patient_id: UUID, history_id: UUID, connection: DatabaseConnection, actor: CurrentUser
) -> MedicalHistoryItem:
    return MedicalHistoryItem.model_validate(
        MedicalHistoryService().get(connection, patient_id, history_id, actor)
    )


@router.post("", response_model=MedicalHistoryItem, status_code=status.HTTP_201_CREATED)
def create_medical_history(
    patient_id: UUID,
    payload: MedicalHistoryCreateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
) -> MedicalHistoryItem:
    return MedicalHistoryItem.model_validate(
        MedicalHistoryService().create(
            connection, patient_id, payload, actor, request_metadata(request)
        )
    )


@router.put("/{history_id}", response_model=MedicalHistoryItem)
def update_medical_history(
    patient_id: UUID,
    history_id: UUID,
    payload: MedicalHistoryUpdateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
) -> MedicalHistoryItem:
    return MedicalHistoryItem.model_validate(
        MedicalHistoryService().update(
            connection, patient_id, history_id, payload, actor, request_metadata(request)
        )
    )


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medical_history(
    patient_id: UUID,
    history_id: UUID,
    version: Annotated[str, Query(pattern=r"^[0-9A-Fa-f]{16}$")],
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
) -> Response:
    MedicalHistoryService().delete(
        connection, patient_id, history_id, version, actor, request_metadata(request)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
