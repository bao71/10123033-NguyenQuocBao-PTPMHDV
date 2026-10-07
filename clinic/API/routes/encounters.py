from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from API.dependencies import CurrentUser, DatabaseConnection, request_metadata
from BLL.encounter_service import EncounterService
from Model.encounters import (
    ClinicalOrderCreateRequest,
    ClinicalOrderUpdateRequest,
    ClinicalOrderVersionRequest,
    ClinicalResultCreateRequest,
    ClinicalResultUpdateRequest,
    ClinicalResultVersionRequest,
    EncounterDetail,
    EncounterListResponse,
    EncounterStartRequest,
    EncounterStatus,
    EncounterUpdateRequest,
    EncounterVersionListResponse,
    EncounterVersionRequest,
)

router = APIRouter(prefix="/encounters", tags=["Encounters"])


@router.get("", response_model=EncounterListResponse)
def list_encounters(
    connection: DatabaseConnection,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=100)] = None,
    patient_id: UUID | None = None,
    appointment_id: UUID | None = None,
    status: EncounterStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: Literal["started_at", "updated_at", "status"] = "started_at",
    sort_order: Literal["asc", "desc"] = "desc",
):
    """Doctors see assigned encounters; patients see only their completed encounters."""
    return EncounterService().list(
        connection,
        actor,
        page=page,
        page_size=page_size,
        search=search,
        patient_id=patient_id,
        appointment_id=appointment_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{encounter_id}", response_model=EncounterDetail)
def get_encounter(encounter_id: UUID, connection: DatabaseConnection, actor: CurrentUser):
    return EncounterService().get(connection, encounter_id, actor)


@router.post("", response_model=EncounterDetail, status_code=status.HTTP_201_CREATED)
def start_encounter(
    payload: EncounterStartRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection, actor, request_metadata(request), payload, action="start"
    )


@router.put("/{encounter_id}", response_model=EncounterDetail)
def save_encounter(
    encounter_id: UUID,
    payload: EncounterUpdateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="save",
        encounter_id=encounter_id,
    )


@router.post("/{encounter_id}/complete", response_model=EncounterDetail)
def complete_encounter(
    encounter_id: UUID,
    payload: EncounterVersionRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="complete",
        encounter_id=encounter_id,
    )


@router.get("/{encounter_id}/versions", response_model=EncounterVersionListResponse)
def encounter_versions(
    encounter_id: UUID,
    connection: DatabaseConnection,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
):
    return EncounterService().versions(
        connection, encounter_id, actor, page=page, page_size=page_size
    )


@router.post(
    "/{encounter_id}/clinical-orders",
    response_model=EncounterDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["Clinical orders/results"],
)
def create_order(
    encounter_id: UUID,
    payload: ClinicalOrderCreateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="order_create",
        encounter_id=encounter_id,
    )


@router.put(
    "/{encounter_id}/clinical-orders/{order_id}",
    response_model=EncounterDetail,
    tags=["Clinical orders/results"],
)
def update_order(
    encounter_id: UUID,
    order_id: UUID,
    payload: ClinicalOrderUpdateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="order_update",
        encounter_id=encounter_id,
        order_id=order_id,
    )


@router.post(
    "/{encounter_id}/clinical-orders/{order_id}/cancel",
    response_model=EncounterDetail,
    tags=["Clinical orders/results"],
)
def cancel_order(
    encounter_id: UUID,
    order_id: UUID,
    payload: ClinicalOrderVersionRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="order_cancel",
        encounter_id=encounter_id,
        order_id=order_id,
    )


@router.delete(
    "/{encounter_id}/clinical-orders/{order_id}",
    response_model=EncounterDetail,
    tags=["Clinical orders/results"],
)
def delete_order(
    encounter_id: UUID,
    order_id: UUID,
    payload: ClinicalOrderVersionRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    """Soft-delete an order without results; returns the refreshed encounter/version."""
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="order_delete",
        encounter_id=encounter_id,
        order_id=order_id,
    )


@router.post(
    "/{encounter_id}/clinical-orders/{order_id}/results",
    response_model=EncounterDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["Clinical orders/results"],
)
def create_result(
    encounter_id: UUID,
    order_id: UUID,
    payload: ClinicalResultCreateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="result_create",
        encounter_id=encounter_id,
        order_id=order_id,
    )


@router.put(
    "/{encounter_id}/clinical-orders/{order_id}/results/{result_id}",
    response_model=EncounterDetail,
    tags=["Clinical orders/results"],
)
def update_result(
    encounter_id: UUID,
    order_id: UUID,
    result_id: UUID,
    payload: ClinicalResultUpdateRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="result_update",
        encounter_id=encounter_id,
        order_id=order_id,
        result_id=result_id,
    )


@router.delete(
    "/{encounter_id}/clinical-orders/{order_id}/results/{result_id}",
    response_model=EncounterDetail,
    tags=["Clinical orders/results"],
)
def delete_result(
    encounter_id: UUID,
    order_id: UUID,
    result_id: UUID,
    payload: ClinicalResultVersionRequest,
    request: Request,
    connection: DatabaseConnection,
    actor: CurrentUser,
):
    return EncounterService().write(
        connection,
        actor,
        request_metadata(request),
        payload,
        action="result_delete",
        encounter_id=encounter_id,
        order_id=order_id,
        result_id=result_id,
    )
