from uuid import UUID

import pyodbc


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
        row = connection.execute(
            """
            INSERT INTO dbo.users(role_id, username, email, password_hash, phone)
            OUTPUT inserted.user_id
            SELECT role_id, ?, ?, ?, ? FROM dbo.roles WHERE code = ?
            """,
            username,
            email,
            password_hash,
            phone,
            role,
        ).fetchone()
        if row is None:
            raise ValueError("Vai trò nhân viên không tồn tại.")
        user_id = UUID(str(row.user_id))
        if role == "Doctor":
            connection.execute(
                """
                INSERT INTO dbo.doctors(user_id, doctor_code, specialty, license_number)
                VALUES(?, ?, ?, ?)
                """,
                str(user_id),
                doctor_code,
                specialty,
                license_number,
            )
        return user_id

    @staticmethod
    def lock_user(connection: pyodbc.Connection, user_id: UUID) -> tuple[bool, str] | None:
        row = connection.execute(
            """
            SELECT u.is_active, r.code AS role
            FROM dbo.users AS u WITH (UPDLOCK, HOLDLOCK)
            JOIN dbo.roles AS r ON r.role_id = u.role_id
            WHERE u.user_id = ? AND u.deleted_at IS NULL
            """,
            str(user_id),
        ).fetchone()
        return (bool(row.is_active), row.role) if row else None

    @staticmethod
    def set_status(connection: pyodbc.Connection, user_id: UUID, is_active: bool) -> None:
        connection.execute(
            """
            UPDATE dbo.users SET is_active = ?, auth_version = auth_version + 1,
                updated_at = SYSUTCDATETIME()
            WHERE user_id = ? AND deleted_at IS NULL
            """,
            int(is_active),
            str(user_id),
        )

    @staticmethod
    def list_users(
        connection: pyodbc.Connection,
        *,
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[list[dict], int]:
        pattern = f"%{search.replace('%', '[%]').replace('_', '[_]')}%" if search else None
        where = "WHERE u.deleted_at IS NULL"
        parameters: list[object] = []
        if pattern:
            where += " AND (u.username LIKE ? OR u.email LIKE ? OR u.phone LIKE ?)"
            parameters.extend([pattern, pattern, pattern])

        count_row = connection.execute(
            f"SELECT COUNT_BIG(*) AS total FROM dbo.users AS u {where}",  # noqa: S608
            *parameters,
        ).fetchone()
        offset = (page - 1) * page_size
        rows = connection.execute(
            f"""
            SELECT u.user_id, u.username, u.email, u.phone, r.code AS role,
                   u.is_active, u.created_at
            FROM dbo.users AS u
            JOIN dbo.roles AS r ON r.role_id = u.role_id
            {where}
            ORDER BY u.created_at DESC, u.user_id
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
            """,  # noqa: S608
            *parameters,
            offset,
            page_size,
        ).fetchall()
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
