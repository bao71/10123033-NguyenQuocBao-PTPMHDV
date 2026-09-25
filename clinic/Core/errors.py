from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class AuthenticationError(AppError):
    def __init__(self, message: str = "Thông tin xác thực không hợp lệ.") -> None:
        super().__init__(401, "AUTHENTICATION_FAILED", message)


class PermissionDeniedError(AppError):
    def __init__(self, missing_permissions: list[str]) -> None:
        super().__init__(
            403,
            "PERMISSION_DENIED",
            "Bạn không có quyền thực hiện hành động này.",
            {"missing_permissions": missing_permissions},
        )
