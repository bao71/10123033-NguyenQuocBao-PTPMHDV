from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from API.dependencies import (
    AppSettings,
    CurrentUser,
    DatabaseConnection,
    RequirePermissions,
    request_metadata,
)
from BLL.admin_service import AdminService
from Core.errors import PermissionDeniedError
from DAL.user_repository import UserRepository
from Model.auth import UserResponse
from Model.users import (
    RoleItem,
    RoleListResponse,
    RolePermissionsRequest,
    StaffCreateRequest,
    UserListResponse,
    UserStatusRequest,
)

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=UserListResponse)
def list_users(
    connection: DatabaseConnection,
    _: Annotated[UserResponse, Depends(RequirePermissions("users.read"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> UserListResponse:
    items, total = UserRepository.list_users(
        connection, page=page, page_size=page_size, search=search
    )
    return UserListResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreateRequest,
    request: Request,
    connection: DatabaseConnection,
    settings: AppSettings,
    actor: Annotated[UserResponse, Depends(RequirePermissions("users.create"))],
) -> UserResponse:
    return AdminService(settings).create_staff(
        connection, payload, actor.user_id, request_metadata(request)
    )


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def set_user_status(
    user_id: UUID,
    payload: UserStatusRequest,
    request: Request,
    connection: DatabaseConnection,
    settings: AppSettings,
    actor: CurrentUser,
) -> UserResponse:
    required = "users.update" if payload.is_active else "users.deactivate"
    if required not in actor.permissions:
        raise PermissionDeniedError([required])
    return AdminService(settings).set_user_status(
        connection, user_id, payload.is_active, actor.user_id, request_metadata(request)
    )


@router.get("/roles", response_model=RoleListResponse)
def list_roles(
    connection: DatabaseConnection,
    settings: AppSettings,
    _: Annotated[UserResponse, Depends(RequirePermissions("roles.read"))],
) -> RoleListResponse:
    return AdminService(settings).list_roles(connection)


@router.put("/roles/{role_code}/permissions", response_model=RoleItem)
def replace_role_permissions(
    role_code: str,
    payload: RolePermissionsRequest,
    request: Request,
    connection: DatabaseConnection,
    settings: AppSettings,
    actor: Annotated[UserResponse, Depends(RequirePermissions("roles.update"))],
) -> RoleItem:
    return AdminService(settings).replace_role_permissions(
        connection, role_code, payload.permissions, actor.user_id, request_metadata(request)
    )
