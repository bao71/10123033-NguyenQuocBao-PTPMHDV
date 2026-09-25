import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

import pyodbc


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
        row = connection.execute(
            """
            SELECT TOP (1)
                u.user_id, u.username, u.email, u.phone, u.password_hash, u.auth_version,
                r.code AS role, u.is_active, u.created_at,
                CONVERT(bit, CASE WHEN u.locked_until > SYSUTCDATETIME()
                            THEN 1 ELSE 0 END) AS is_locked,
                p.patient_id, p.patient_code, p.full_name
            FROM dbo.users AS u
            JOIN dbo.roles AS r ON r.role_id = u.role_id
            LEFT JOIN dbo.patients AS p ON p.user_id = u.user_id AND p.deleted_at IS NULL
            WHERE u.deleted_at IS NULL AND (u.username = ? OR u.email = ?)
            """,
            login,
            login,
        ).fetchone()
        return self._user_from_row(row) if row else None

    def find_by_id(self, connection: pyodbc.Connection, user_id: UUID) -> UserRecord | None:
        row = connection.execute(
            """
            SELECT
                u.user_id, u.username, u.email, u.phone, u.password_hash, u.auth_version,
                r.code AS role, u.is_active, u.created_at,
                CONVERT(bit, CASE WHEN u.locked_until > SYSUTCDATETIME()
                            THEN 1 ELSE 0 END) AS is_locked,
                p.patient_id, p.patient_code, p.full_name
            FROM dbo.users AS u
            JOIN dbo.roles AS r ON r.role_id = u.role_id
            LEFT JOIN dbo.patients AS p ON p.user_id = u.user_id AND p.deleted_at IS NULL
            WHERE u.user_id = ? AND u.deleted_at IS NULL
            """,
            str(user_id),
        ).fetchone()
        return self._user_from_row(row) if row else None

    @staticmethod
    def permissions_for_user(connection: pyodbc.Connection, user_id: UUID) -> list[str]:
        rows = connection.execute(
            """
            SELECT permission_item.code
            FROM dbo.users AS user_item
            JOIN dbo.role_permissions AS role_grant ON role_grant.role_id = user_item.role_id
            JOIN dbo.permissions AS permission_item
                ON permission_item.permission_id = role_grant.permission_id
            WHERE user_item.user_id = ? AND user_item.deleted_at IS NULL AND user_item.is_active = 1
            ORDER BY permission_item.code
            """,
            str(user_id),
        ).fetchall()
        return [row.code for row in rows]

    @staticmethod
    def duplicate_registration_field(
        connection: pyodbc.Connection, username: str, email: str, phone: str | None
    ) -> str | None:
        row = connection.execute(
            """
            SELECT TOP (1)
                CASE
                    WHEN username = ? THEN 'username'
                    WHEN email = ? THEN 'email'
                    WHEN ? IS NOT NULL AND phone = ? THEN 'phone'
                END AS duplicate_field
            FROM dbo.users
            WHERE deleted_at IS NULL
              AND (username = ? OR email = ? OR (? IS NOT NULL AND phone = ?))
            """,
            username,
            email,
            phone,
            phone,
            username,
            email,
            phone,
            phone,
        ).fetchone()
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
        row = connection.execute(
            """
            DECLARE @role_id uniqueidentifier =
                (SELECT role_id FROM dbo.roles WHERE code = 'Patient');
            IF @role_id IS NULL THROW 51200, 'Patient role is not configured.', 1;
            INSERT INTO dbo.users(role_id, username, email, password_hash, phone)
            OUTPUT inserted.user_id
            VALUES(@role_id, ?, ?, ?, ?);
            """,
            username,
            email,
            password_hash,
            phone,
        ).fetchone()
        user_id = UUID(str(row.user_id))
        patient_row = connection.execute(
            """
            INSERT INTO dbo.patients(
                user_id, patient_code, full_name, date_of_birth, gender, phone, email
            )
            OUTPUT inserted.patient_id
            VALUES(?, ?, ?, ?, ?, ?, ?);
            """,
            str(user_id),
            patient_code,
            full_name,
            date_of_birth,
            gender,
            phone,
            email,
        ).fetchone()
        return user_id, UUID(str(patient_row.patient_id))

    @staticmethod
    def record_failed_login(
        connection: pyodbc.Connection, user_id: UUID, max_failures: int, lock_minutes: int
    ) -> None:
        connection.execute(
            """
            UPDATE dbo.users
            SET failed_login_count = failed_login_count + 1,
                locked_until = CASE
                    WHEN failed_login_count + 1 >= ?
                    THEN DATEADD(MINUTE, ?, SYSUTCDATETIME())
                    ELSE locked_until
                END,
                updated_at = SYSUTCDATETIME()
            WHERE user_id = ?;
            """,
            max_failures,
            lock_minutes,
            str(user_id),
        )

    @staticmethod
    def record_successful_login(connection: pyodbc.Connection, user_id: UUID) -> None:
        connection.execute(
            """
            UPDATE dbo.users
            SET failed_login_count = 0, locked_until = NULL, updated_at = SYSUTCDATETIME()
            WHERE user_id = ?;
            """,
            str(user_id),
        )

    @staticmethod
    def insert_refresh_token(
        connection: pyodbc.Connection,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO dbo.refresh_tokens(user_id, token_hash, expires_at)
            VALUES(?, ?, ?);
            """,
            str(user_id),
            token_hash,
            expires_at,
        )

    @staticmethod
    def lock_refresh_token(connection: pyodbc.Connection, token_hash: str) -> UUID | None:
        row = connection.execute(
            """
            SELECT token_item.user_id
            FROM dbo.refresh_tokens AS token_item WITH (UPDLOCK, HOLDLOCK)
            JOIN dbo.users AS user_item ON user_item.user_id = token_item.user_id
            WHERE token_item.token_hash = ?
              AND token_item.revoked_at IS NULL
              AND token_item.expires_at > SYSUTCDATETIME()
              AND user_item.is_active = 1
              AND user_item.deleted_at IS NULL;
            """,
            token_hash,
        ).fetchone()
        return UUID(str(row.user_id)) if row else None

    @staticmethod
    def revoke_refresh_token(
        connection: pyodbc.Connection, token_hash: str, user_id: UUID | None = None
    ) -> bool:
        sql = """
            UPDATE dbo.refresh_tokens
            SET revoked_at = COALESCE(revoked_at, SYSUTCDATETIME())
            WHERE token_hash = ? AND revoked_at IS NULL
        """
        parameters: list[str] = [token_hash]
        if user_id is not None:
            sql += " AND user_id = ?"
            parameters.append(str(user_id))
        cursor = connection.execute(sql, *parameters)
        return cursor.rowcount > 0

    @staticmethod
    def revoke_all_refresh_tokens(connection: pyodbc.Connection, user_id: UUID) -> None:
        connection.execute(
            """
            UPDATE dbo.refresh_tokens
            SET revoked_at = COALESCE(revoked_at, SYSUTCDATETIME())
            WHERE user_id = ? AND revoked_at IS NULL;
            """,
            str(user_id),
        )

    @staticmethod
    def invalidate_password_reset_tokens(connection: pyodbc.Connection, user_id: UUID) -> None:
        connection.execute(
            "UPDATE dbo.password_reset_tokens SET used_at = SYSUTCDATETIME() "
            "WHERE user_id = ? AND used_at IS NULL",
            str(user_id),
        )

    @staticmethod
    def insert_password_reset_token(
        connection: pyodbc.Connection, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> None:
        connection.execute(
            "INSERT INTO dbo.password_reset_tokens(user_id, token_hash, expires_at) "
            "VALUES(?, ?, ?)",
            str(user_id),
            token_hash,
            expires_at,
        )

    @staticmethod
    def lock_password_reset_token(connection: pyodbc.Connection, token_hash: str) -> UUID | None:
        row = connection.execute(
            """
            SELECT reset_item.user_id
            FROM dbo.password_reset_tokens AS reset_item WITH (UPDLOCK, HOLDLOCK)
            JOIN dbo.users AS user_item ON user_item.user_id = reset_item.user_id
            WHERE reset_item.token_hash = ?
              AND reset_item.used_at IS NULL
              AND reset_item.expires_at > SYSUTCDATETIME()
              AND user_item.is_active = 1
              AND user_item.deleted_at IS NULL
            """,
            token_hash,
        ).fetchone()
        return UUID(str(row.user_id)) if row else None

    @staticmethod
    def update_password_after_reset(
        connection: pyodbc.Connection, user_id: UUID, new_password_hash: str
    ) -> None:
        connection.execute(
            """
            UPDATE dbo.users
            SET password_hash = ?, auth_version = auth_version + 1,
                failed_login_count = 0, locked_until = NULL,
                updated_at = SYSUTCDATETIME()
            WHERE user_id = ? AND is_active = 1 AND deleted_at IS NULL
            """,
            new_password_hash,
            str(user_id),
        )

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
        connection.execute(
            """
            INSERT INTO dbo.audit_logs(
                actor_user_id, action, entity_type, entity_id, after_json,
                ip_address, user_agent, request_id
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?);
            """,
            str(actor_user_id) if actor_user_id else None,
            action,
            entity_type,
            str(entity_id) if entity_id else None,
            json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
            ip_address,
            user_agent[:512] if user_agent else None,
            str(request_id),
        )
