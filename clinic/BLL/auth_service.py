import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pyodbc

from Core.config import Settings
from Core.errors import AppError, AuthenticationError
from Core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from DAL.auth_repository import AuthRepository, UserRecord
from Model.auth import RegisterRequest, TokenResponse, UserResponse


@dataclass(frozen=True)
class RequestMetadata:
    request_id: UUID
    ip_address: str | None
    user_agent: str | None


class AuthService:
    def __init__(self, settings: Settings, repository: AuthRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or AuthRepository()

    def _user_response(
        self, connection: pyodbc.Connection, user: UserRecord
    ) -> UserResponse:
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
            permissions=self.repository.permissions_for_user(connection, user.user_id),
        )

    def _issue_tokens(
        self, connection: pyodbc.Connection, user: UserRecord
    ) -> TokenResponse:
        access_token, expires_in = create_access_token(
            user.user_id, user.role, self.settings, user.auth_version
        )
        refresh_token, refresh_hash = create_refresh_token()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            days=self.settings.refresh_token_days
        )
        self.repository.insert_refresh_token(connection, user.user_id, refresh_hash, expires_at)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=self._user_response(connection, user),
        )

    def register(
        self,
        connection: pyodbc.Connection,
        payload: RegisterRequest,
        metadata: RequestMetadata,
    ) -> TokenResponse:
        duplicate = self.repository.duplicate_registration_field(
            connection, payload.username, str(payload.email).lower(), payload.phone
        )
        if duplicate:
            raise AppError(
                409,
                "ACCOUNT_ALREADY_EXISTS",
                "Thông tin đăng ký đã được sử dụng.",
                {"field": duplicate},
            )

        patient_code = f"BN{datetime.now(timezone.utc):%Y%m%d}{uuid4().hex[:10].upper()}"
        try:
            user_id, _ = self.repository.create_patient_user(
                connection,
                username=payload.username,
                email=str(payload.email).lower(),
                phone=payload.phone,
                password_hash=hash_password(payload.password),
                full_name=payload.full_name,
                date_of_birth=payload.date_of_birth,
                gender=payload.gender,
                patient_code=patient_code,
            )
            self.repository.audit(
                connection,
                action="auth.register",
                entity_type="users",
                actor_user_id=user_id,
                entity_id=user_id,
                after={"username": payload.username, "role": "Patient"},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            user = self.repository.find_by_id(connection, user_id)
            if user is None:
                raise RuntimeError("Registered user could not be reloaded")
            response = self._issue_tokens(connection, user)
            connection.commit()
            return response
        except pyodbc.IntegrityError as exc:
            connection.rollback()
            raise AppError(
                409, "ACCOUNT_ALREADY_EXISTS", "Thông tin đăng ký đã được sử dụng."
            ) from exc
        except Exception:
            connection.rollback()
            raise

    def login(
        self,
        connection: pyodbc.Connection,
        login: str,
        password: str,
        metadata: RequestMetadata,
    ) -> TokenResponse:
        normalized_login = login.strip().lower()
        user = self.repository.find_by_login(connection, normalized_login)
        password_valid = verify_password(password, user.password_hash if user else None)
        valid = bool(user and user.is_active and not user.is_locked and password_valid)

        if not valid:
            if user and user.is_active and not user.is_locked:
                self.repository.record_failed_login(
                    connection,
                    user.user_id,
                    self.settings.login_max_failures,
                    self.settings.login_lock_minutes,
                )
            self.repository.audit(
                connection,
                action="auth.login_failed",
                entity_type="users",
                actor_user_id=user.user_id if user else None,
                entity_id=user.user_id if user else None,
                after={"login": normalized_login, "reason": "invalid_credentials_or_state"},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            connection.commit()
            raise AuthenticationError()

        assert user is not None
        try:
            self.repository.record_successful_login(connection, user.user_id)
            self.repository.audit(
                connection,
                action="auth.login",
                entity_type="users",
                actor_user_id=user.user_id,
                entity_id=user.user_id,
                after=None,
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            response = self._issue_tokens(connection, user)
            connection.commit()
            return response
        except Exception:
            connection.rollback()
            raise

    def refresh(
        self,
        connection: pyodbc.Connection,
        refresh_token: str,
        metadata: RequestMetadata,
    ) -> TokenResponse:
        old_hash = hash_refresh_token(refresh_token)
        try:
            user_id = self.repository.lock_refresh_token(connection, old_hash)
            if user_id is None:
                connection.rollback()
                raise AuthenticationError("Refresh token không hợp lệ hoặc đã hết hạn.")
            self.repository.revoke_refresh_token(connection, old_hash, user_id)
            user = self.repository.find_by_id(connection, user_id)
            if user is None or not user.is_active or user.is_locked:
                connection.rollback()
                raise AuthenticationError("Tài khoản không còn khả dụng.")
            self.repository.audit(
                connection,
                action="auth.refresh",
                entity_type="users",
                actor_user_id=user_id,
                entity_id=user_id,
                after=None,
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            response = self._issue_tokens(connection, user)
            connection.commit()
            return response
        except AppError:
            raise
        except Exception:
            connection.rollback()
            raise

    def logout(
        self,
        connection: pyodbc.Connection,
        user_id: UUID,
        refresh_token: str,
        all_sessions: bool,
        metadata: RequestMetadata,
    ) -> None:
        try:
            if all_sessions:
                self.repository.revoke_all_refresh_tokens(connection, user_id)
            else:
                self.repository.revoke_refresh_token(
                    connection, hash_refresh_token(refresh_token), user_id
                )
            self.repository.audit(
                connection,
                action="auth.logout_all" if all_sessions else "auth.logout",
                entity_type="users",
                actor_user_id=user_id,
                entity_id=user_id,
                after=None,
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def request_password_reset(
        self, connection: pyodbc.Connection, email: str, metadata: RequestMetadata
    ) -> tuple[str, str] | None:
        user = self.repository.find_by_login(connection, email.strip().lower())
        if user is None or not user.is_active or not user.email:
            return None

        token = secrets.token_urlsafe(48)
        token_hash = hash_refresh_token(token)
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            minutes=self.settings.password_reset_minutes
        )
        try:
            self.repository.invalidate_password_reset_tokens(connection, user.user_id)
            self.repository.insert_password_reset_token(
                connection, user.user_id, token_hash, expires_at
            )
            self.repository.audit(
                connection,
                action="auth.password_reset_requested",
                entity_type="users",
                actor_user_id=None,
                entity_id=user.user_id,
                after=None,
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return user.email, token

    def reset_password(
        self, connection: pyodbc.Connection, token: str, new_password: str,
        metadata: RequestMetadata,
    ) -> None:
        try:
            user_id = self.repository.lock_password_reset_token(
                connection, hash_refresh_token(token)
            )
            if user_id is None:
                connection.rollback()
                raise AppError(
                    400, "INVALID_RESET_TOKEN", "Mã đặt lại không hợp lệ hoặc đã hết hạn."
                )
            self.repository.update_password_after_reset(
                connection, user_id, hash_password(new_password)
            )
            self.repository.invalidate_password_reset_tokens(connection, user_id)
            self.repository.revoke_all_refresh_tokens(connection, user_id)
            self.repository.audit(
                connection,
                action="auth.password_reset",
                entity_type="users",
                actor_user_id=user_id,
                entity_id=user_id,
                after=None,
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            connection.commit()
        except AppError:
            raise
        except Exception:
            connection.rollback()
            raise
