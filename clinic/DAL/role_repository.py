import json

import pyodbc

from DAL.procedures import call


class RoleRepository:
    @staticmethod
    def list_roles(connection: pyodbc.Connection) -> tuple[list[dict], list[str]]:
        cursor = call(connection, "clinic_role_list")
        role_rows = cursor.fetchall()
        cursor.nextset()
        permission_rows = cursor.fetchall()
        cursor.nextset()
        grant_rows = cursor.fetchall()
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
        row = call(connection, "clinic_role_lock", role_code).fetchone()
        return str(row.role_id) if row else None

    @staticmethod
    def permission_codes(connection: pyodbc.Connection) -> set[str]:
        return {row.code for row in call(connection, "clinic_role_permission_codes")}

    @staticmethod
    def granted_codes(connection: pyodbc.Connection, role_id: str) -> list[str]:
        rows = call(connection, "clinic_role_granted_codes", role_id).fetchall()
        return [row.code for row in rows]

    @staticmethod
    def replace_permissions(
        connection: pyodbc.Connection, role_id: str, permissions: list[str]
    ) -> None:
        call(connection, "clinic_role_replace_permissions", role_id, json.dumps(permissions))
