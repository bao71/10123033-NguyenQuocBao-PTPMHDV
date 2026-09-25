from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from API.dependencies import (
    AppSettings,
    CurrentUser,
    DatabaseConnection,
    enforce_auth_rate_limit,
    request_metadata,
)
from BLL.auth_service import AuthService
from Model.auth import (
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def register(
    payload: RegisterRequest,
    request: Request,
    connection: DatabaseConnection,
    settings: AppSettings,
) -> TokenResponse:
    return AuthService(settings).register(connection, payload, request_metadata(request))


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    connection: DatabaseConnection,
    settings: AppSettings,
) -> TokenResponse:
    return AuthService(settings).login(
        connection, form.username, form.password, request_metadata(request)
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def refresh(
    payload: RefreshRequest,
    request: Request,
    connection: DatabaseConnection,
    settings: AppSettings,
) -> TokenResponse:
    return AuthService(settings).refresh(
        connection, payload.refresh_token, request_metadata(request)
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: LogoutRequest,
    request: Request,
    current_user: CurrentUser,
    connection: DatabaseConnection,
    settings: AppSettings,
) -> MessageResponse:
    AuthService(settings).logout(
        connection,
        current_user.user_id,
        payload.refresh_token,
        payload.all_sessions,
        request_metadata(request),
    )
    return MessageResponse(message="Đăng xuất thành công.")


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    return current_user
