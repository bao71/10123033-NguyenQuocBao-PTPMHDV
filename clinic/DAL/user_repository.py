from uuid import UUID

import pyodbc

from DAL.procedures import call


class UserRepository:
    @staticmethod
    def create_staff(
        connection: pyodbc.Connection,
        *,
        username: str,
        email: str,
        password_hash: str,
        phone: str | None,
        role: str,
        doctor_code: str | None,
        specialty: str | None,
        license_number: str | None,
    ) -> UUID:
        row = call(
            connection, "clinic_user_create_staff", username, email, password_hash,
            phone, role, doctor_code, specialty, license_number,
        ).fetchone()
        if row is None:
            raise ValueError("Vai trò nhân viên không tồn tại.")
        return UUID(str(row.user_id))

    @staticmethod
    def lock_user(connection: pyodbc.Connection, user_id: UUID) -> tuple[bool, str] | None:
        row = call(connection, "clinic_user_lock", str(user_id)).fetchone()
        return (bool(row.is_active), row.role) if row else None

    @staticmethod
    def set_status(connection: pyodbc.Connection, user_id: UUID, is_active: bool) -> None:
        call(connection, "clinic_user_set_status", str(user_id), int(is_active))

    @staticmethod
    def list_users(
        connection: pyodbc.Connection,
        *,
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[list[dict], int]:
        cursor = call(connection, "clinic_user_list", page, page_size, search)
        count_row = cursor.fetchone()
        cursor.nextset()
        rows = cursor.fetchall()
        items = [
            {
                "user_id": UUID(str(row.user_id)),
                "username": row.username,
                "email": row.email,
                "phone": row.phone,
                "role": row.role,
                "is_active": bool(row.is_active),
                "created_at": row.created_at,
            }
            for row in rows
        ]
        return items, int(count_row.total)
