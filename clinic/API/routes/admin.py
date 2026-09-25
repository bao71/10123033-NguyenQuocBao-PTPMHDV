from typing import Annotated

from fastapi import APIRouter, Depends, Query

from API.dependencies import DatabaseConnection, RequirePermissions
from DAL.user_repository import UserRepository
from Model.auth import UserResponse
from Model.users import UserListResponse

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
