import threading
import time
from collections import defaultdict, deque
from typing import Annotated
from uuid import UUID

import pyodbc
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from BLL.auth_service import RequestMetadata
from Core.config import Settings, get_settings
from Core.errors import AppError, AuthenticationError, PermissionDeniedError
from Core.security import decode_access_token
from DAL.auth_repository import AuthRepository
from DAL.db import get_db
from Model.auth import UserResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DatabaseConnection = Annotated[pyodbc.Connection, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise AppError(429, "RATE_LIMITED", "Quá nhiều yêu cầu. Vui lòng thử lại sau.")
            events.append(now)
            if len(self._events) > 10_000:
                empty_keys = [item for item, values in self._events.items() if not values]
                for item in empty_keys:
                    self._events.pop(item, None)


auth_limiter = FixedWindowRateLimiter()


def request_metadata(request: Request) -> RequestMetadata:
    request_id = getattr(request.state, "request_id", None)
    return RequestMetadata(
        request_id=request_id if isinstance(request_id, UUID) else UUID(str(request_id)),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def enforce_auth_rate_limit(request: Request, settings: AppSettings) -> None:
    address = request.client.host if request.client else "unknown"
    auth_limiter.check(
        f"{address}:{request.url.path}", settings.auth_rate_limit_per_minute
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    connection: DatabaseConnection,
    settings: AppSettings,
) -> UserResponse:
    claims = decode_access_token(token, settings)
    repository = AuthRepository()
    user = repository.find_by_id(connection, claims.user_id)
    if user is None or not user.is_active or user.is_locked:
        raise AuthenticationError("Tài khoản không còn khả dụng.")
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        patient_id=user.patient_id,
        patient_code=user.patient_code,
        full_name=user.full_name,
        permissions=repository.permissions_for_user(connection, user.user_id),
    )


CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


class RequirePermissions:
    def __init__(self, *permissions: str) -> None:
        self.required = frozenset(permissions)

    def __call__(self, current_user: CurrentUser) -> UserResponse:
        missing = sorted(self.required.difference(current_user.permissions))
        if missing:
            raise PermissionDeniedError(missing)
        return current_user
