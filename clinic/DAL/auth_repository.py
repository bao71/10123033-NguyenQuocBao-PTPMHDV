import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

import pyodbc

from DAL.procedures import call


@dataclass(frozen=True)
class UserRecord:
    user_id: UUID
    username: str
    email: str | None
    phone: str | None
    password_hash: str
    role: str
    is_active: bool
    is_locked: bool
    created_at: datetime
    patient_id: UUID | None
    patient_code: str | None
    full_name: str | None
    auth_version: int


class AuthRepository:
    @staticmethod
    def _user_from_row(row: pyodbc.Row) -> UserRecord:
        return UserRecord(
            user_id=UUID(str(row.user_id)),
            username=row.username,
            email=row.email,
            phone=row.phone,
            password_hash=row.password_hash,
            role=row.role,
            is_active=bool(row.is_active),
            is_locked=bool(row.is_locked),
            created_at=row.created_at,
            patient_id=UUID(str(row.patient_id)) if row.patient_id else None,
            patient_code=row.patient_code,
            full_name=row.full_name,
            auth_version=int(row.auth_version),
        )

    def find_by_login(self, connection: pyodbc.Connection, login: str) -> UserRecord | None:
        row = call(connection, "clinic_auth_find_by_login", login).fetchone()
        return self._user_from_row(row) if row else None

    def find_by_id(self, connection: pyodbc.Connection, user_id: UUID) -> UserRecord | None:
        row = call(connection, "clinic_auth_find_by_id", str(user_id)).fetchone()
        return self._user_from_row(row) if row else None

    @staticmethod
    def permissions_for_user(connection: pyodbc.Connection, user_id: UUID) -> list[str]:
        rows = call(connection, "clinic_auth_permissions", str(user_id)).fetchall()
        return [row.code for row in rows]

    @staticmethod
    def duplicate_registration_field(
        connection: pyodbc.Connection, username: str, email: str, phone: str | None
    ) -> str | None:
        row = call(connection, "clinic_auth_duplicate", username, email, phone).fetchone()
        return row.duplicate_field if row else None

    @staticmethod
    def create_patient_user(
        connection: pyodbc.Connection,
        *,
        username: str,
        email: str,
        phone: str | None,
        password_hash: str,
        full_name: str,
        date_of_birth: date | None,
        gender: str | None,
        patient_code: str,
    ) -> tuple[UUID, UUID]:
        row = call(
            connection, "clinic_auth_create_patient", username, email, phone,
            password_hash, full_name, date_of_birth, gender, patient_code,
        ).fetchone()
        return UUID(str(row.user_id)), UUID(str(row.patient_id))

    @staticmethod
    def record_failed_login(
        connection: pyodbc.Connection, user_id: UUID, max_failures: int, lock_minutes: int
    ) -> None:
        call(connection, "clinic_auth_failed_login", str(user_id), max_failures, lock_minutes)

    @staticmethod
    def record_successful_login(connection: pyodbc.Connection, user_id: UUID) -> None:
        call(connection, "clinic_auth_successful_login", str(user_id))

    @staticmethod
    def insert_refresh_token(
        connection: pyodbc.Connection,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        call(connection, "clinic_auth_insert_refresh", str(user_id), token_hash, expires_at)

    @staticmethod
    def lock_refresh_token(connection: pyodbc.Connection, token_hash: str) -> UUID | None:
        row = call(connection, "clinic_auth_lock_refresh", token_hash).fetchone()
        return UUID(str(row.user_id)) if row else None

    @staticmethod
    def revoke_refresh_token(
        connection: pyodbc.Connection, token_hash: str, user_id: UUID | None = None
    ) -> bool:
        row = call(
            connection, "clinic_auth_revoke_refresh", token_hash,
            str(user_id) if user_id is not None else None,
        ).fetchone()
        return bool(row.revoked)

    @staticmethod
    def revoke_all_refresh_tokens(connection: pyodbc.Connection, user_id: UUID) -> None:
        call(connection, "clinic_auth_revoke_all_refresh", str(user_id))

    @staticmethod
    def invalidate_password_reset_tokens(connection: pyodbc.Connection, user_id: UUID) -> None:
        call(connection, "clinic_auth_invalidate_resets", str(user_id))

    @staticmethod
    def insert_password_reset_token(
        connection: pyodbc.Connection, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> None:
        call(connection, "clinic_auth_insert_reset", str(user_id), token_hash, expires_at)

    @staticmethod
    def lock_password_reset_token(connection: pyodbc.Connection, token_hash: str) -> UUID | None:
        row = call(connection, "clinic_auth_lock_reset", token_hash).fetchone()
        return UUID(str(row.user_id)) if row else None

    @staticmethod
    def update_password_after_reset(
        connection: pyodbc.Connection, user_id: UUID, new_password_hash: str
    ) -> None:
        call(connection, "clinic_auth_update_password", str(user_id), new_password_hash)

    @staticmethod
    def audit(
        connection: pyodbc.Connection,
        *,
        action: str,
        entity_type: str,
        actor_user_id: UUID | None,
        entity_id: UUID | None,
        after: dict | None,
        ip_address: str | None,
        user_agent: str | None,
        request_id: UUID,
    ) -> None:
        call(
            connection, "clinic_audit_insert",
            str(actor_user_id) if actor_user_id else None,
            action,
            entity_type,
            str(entity_id) if entity_id else None,
            json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
            ip_address,
            user_agent[:512] if user_agent else None,
            str(request_id),
        )
