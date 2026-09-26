import pyodbc


class RoleRepository:
    @staticmethod
    def list_roles(connection: pyodbc.Connection) -> tuple[list[dict], list[str]]:
        role_rows = connection.execute(
            "SELECT code, name, description FROM dbo.roles ORDER BY name"
        ).fetchall()
        permission_rows = connection.execute(
            "SELECT code FROM dbo.permissions ORDER BY code"
        ).fetchall()
        grant_rows = connection.execute(
            """
            SELECT r.code AS role_code, p.code AS permission_code
            FROM dbo.role_permissions AS rp
            JOIN dbo.roles AS r ON r.role_id = rp.role_id
            JOIN dbo.permissions AS p ON p.permission_id = rp.permission_id
            ORDER BY p.code
            """
        ).fetchall()
        grants: dict[str, list[str]] = {row.code: [] for row in role_rows}
        for row in grant_rows:
            grants[row.role_code].append(row.permission_code)
        roles = [
            {
                "code": row.code,
                "name": row.name,
                "description": row.description,
                "permissions": grants[row.code],
            }
            for row in role_rows
        ]
        return roles, [row.code for row in permission_rows]

    @staticmethod
    def lock_role(connection: pyodbc.Connection, role_code: str) -> str | None:
        row = connection.execute(
            "SELECT role_id FROM dbo.roles WITH (UPDLOCK, HOLDLOCK) WHERE code = ?",
            role_code,
        ).fetchone()
        return str(row.role_id) if row else None

    @staticmethod
    def permission_codes(connection: pyodbc.Connection) -> set[str]:
        return {row.code for row in connection.execute("SELECT code FROM dbo.permissions")}

    @staticmethod
    def granted_codes(connection: pyodbc.Connection, role_id: str) -> list[str]:
        rows = connection.execute(
            """
            SELECT p.code FROM dbo.role_permissions AS rp
            JOIN dbo.permissions AS p ON p.permission_id = rp.permission_id
            WHERE rp.role_id = ? ORDER BY p.code
            """,
            role_id,
        ).fetchall()
        return [row.code for row in rows]

    @staticmethod
    def replace_permissions(
        connection: pyodbc.Connection, role_id: str, permissions: list[str]
    ) -> None:
        connection.execute("DELETE FROM dbo.role_permissions WHERE role_id = ?", role_id)
        for permission in permissions:
            connection.execute(
                """
                INSERT INTO dbo.role_permissions(role_id, permission_id)
                SELECT ?, permission_id FROM dbo.permissions WHERE code = ?
                """,
                role_id,
                permission,
            )
