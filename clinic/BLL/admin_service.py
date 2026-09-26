from uuid import UUID

import pyodbc

from BLL.auth_service import AuthService, RequestMetadata
from Core.config import Settings
from Core.errors import AppError
from Core.security import hash_password
from DAL.auth_repository import AuthRepository
from DAL.role_repository import RoleRepository
from DAL.user_repository import UserRepository
from Model.auth import UserResponse
from Model.users import RoleItem, RoleListResponse, StaffCreateRequest

ADMIN_REQUIRED_PERMISSIONS = frozenset(
    ("users.read", "users.create", "users.update", "users.deactivate", "roles.read", "roles.update")
)


class AdminService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.auth_repository = AuthRepository()
        self.user_repository = UserRepository()
        self.role_repository = RoleRepository()

    def create_staff(
        self,
        connection: pyodbc.Connection,
        payload: StaffCreateRequest,
        actor_user_id: UUID,
        metadata: RequestMetadata,
    ) -> UserResponse:
        email = str(payload.email).lower()
        duplicate = self.auth_repository.duplicate_registration_field(
            connection, payload.username, email, payload.phone
        )
        if duplicate:
            raise AppError(
                409,
                "ACCOUNT_ALREADY_EXISTS",
                "Thông tin tài khoản đã được sử dụng.",
                {"field": duplicate},
            )
        try:
            user_id = self.user_repository.create_staff(
                connection,
                username=payload.username,
                email=email,
                password_hash=hash_password(payload.password),
                phone=payload.phone,
                role=payload.role,
                doctor_code=payload.doctor_code,
                specialty=payload.specialty,
                license_number=payload.license_number,
            )
            self.auth_repository.audit(
                connection,
                action="users.create",
                entity_type="users",
                actor_user_id=actor_user_id,
                entity_id=user_id,
                after={"username": payload.username, "role": payload.role},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            user = self.auth_repository.find_by_id(connection, user_id)
            if user is None:
                raise RuntimeError("Created staff user could not be reloaded")
            response = AuthService(self.settings, self.auth_repository)._user_response(
                connection, user
            )
            connection.commit()
            return response
        except pyodbc.IntegrityError as exc:
            connection.rollback()
            raise AppError(
                409, "ACCOUNT_ALREADY_EXISTS", "Thông tin tài khoản hoặc mã bác sĩ đã được sử dụng."
            ) from exc
        except Exception:
            connection.rollback()
            raise

    def set_user_status(
        self,
        connection: pyodbc.Connection,
        user_id: UUID,
        is_active: bool,
        actor_user_id: UUID,
        metadata: RequestMetadata,
    ) -> UserResponse:
        if user_id == actor_user_id and not is_active:
            raise AppError(400, "CANNOT_DEACTIVATE_SELF", "Không thể khóa tài khoản đang dùng.")
        try:
            previous = self.user_repository.lock_user(connection, user_id)
            if previous is None:
                raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy tài khoản.")
            if previous[0] != is_active:
                self.user_repository.set_status(connection, user_id, is_active)
                self.auth_repository.revoke_all_refresh_tokens(connection, user_id)
                self.auth_repository.audit(
                    connection,
                    action="users.activate" if is_active else "users.deactivate",
                    entity_type="users",
                    actor_user_id=actor_user_id,
                    entity_id=user_id,
                    after={"is_active": is_active},
                    ip_address=metadata.ip_address,
                    user_agent=metadata.user_agent,
                    request_id=metadata.request_id,
                )
            user = self.auth_repository.find_by_id(connection, user_id)
            if user is None:
                raise RuntimeError("Updated user could not be reloaded")
            response = AuthService(self.settings, self.auth_repository)._user_response(
                connection, user
            )
            connection.commit()
            return response
        except Exception:
            connection.rollback()
            raise

    def list_roles(self, connection: pyodbc.Connection) -> RoleListResponse:
        roles, available = self.role_repository.list_roles(connection)
        return RoleListResponse(roles=roles, available_permissions=available)

    def replace_role_permissions(
        self,
        connection: pyodbc.Connection,
        role_code: str,
        permission_codes: list[str],
        actor_user_id: UUID,
        metadata: RequestMetadata,
    ) -> RoleItem:
        requested = set(permission_codes)
        if len(requested) != len(permission_codes):
            raise AppError(422, "DUPLICATE_PERMISSION", "Danh sách quyền có mục trùng lặp.")
        try:
            role_id = self.role_repository.lock_role(connection, role_code)
            if role_id is None:
                raise AppError(404, "ROLE_NOT_FOUND", "Không tìm thấy vai trò.")
            unknown = sorted(requested - self.role_repository.permission_codes(connection))
            if unknown:
                raise AppError(
                    422,
                    "UNKNOWN_PERMISSION",
                    "Có quyền không tồn tại.",
                    {"permissions": unknown},
                )
            if role_code == "Admin" and not ADMIN_REQUIRED_PERMISSIONS.issubset(requested):
                raise AppError(
                    422,
                    "ADMIN_PERMISSIONS_REQUIRED",
                    "Admin phải giữ các quyền quản trị tài khoản và phân quyền.",
                )
            before = self.role_repository.granted_codes(connection, role_id)
            if set(before) != requested:
                self.role_repository.replace_permissions(connection, role_id, sorted(requested))
                self.auth_repository.audit(
                    connection,
                    action="roles.permissions_update",
                    entity_type="roles",
                    actor_user_id=actor_user_id,
                    entity_id=UUID(role_id),
                    after={
                        "role": role_code,
                        "added": sorted(requested - set(before)),
                        "removed": sorted(set(before) - requested),
                    },
                    ip_address=metadata.ip_address,
                    user_agent=metadata.user_agent,
                    request_id=metadata.request_id,
                )
            roles, _ = self.role_repository.list_roles(connection)
            result = next(role for role in roles if role["code"] == role_code)
            connection.commit()
            return RoleItem(**result)
        except Exception:
            connection.rollback()
            raise
