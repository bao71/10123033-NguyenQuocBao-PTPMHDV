from uuid import UUID

import pyodbc


class UserRepository:
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
