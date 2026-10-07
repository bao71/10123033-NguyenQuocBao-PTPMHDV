from uuid import UUID

import pyodbc

from DAL.procedures import call


def _patient(row: pyodbc.Row) -> dict:
    return {
        "patient_id": UUID(str(row.patient_id)),
        "patient_code": row.patient_code,
        "full_name": row.full_name,
        "date_of_birth": row.date_of_birth,
        "gender": row.gender,
        "phone": row.phone,
        "email": row.email,
        "address": row.address,
        "insurance_number": row.insurance_number,
        "has_account": bool(row.has_account),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "version": bytes(row.row_version).hex().upper(),
    }


class PatientRepository:
    @classmethod
    def list_patients(
        cls,
        connection: pyodbc.Connection,
        *,
        scope: str,
        user_id: UUID,
        page: int,
        page_size: int,
        search: str | None,
        gender: str | None,
        has_account: bool | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[dict], int]:
        cursor = call(
            connection, "clinic_patient_list", scope, str(user_id), page, page_size,
            search, gender, has_account, sort_by, sort_order,
        )
        count = cursor.fetchone()
        cursor.nextset()
        rows = cursor.fetchall()
        return [_patient(row) for row in rows], int(count.total)

    @classmethod
    def get_patient(
        cls, connection: pyodbc.Connection, patient_id: UUID, *, scope: str, user_id: UUID
    ) -> dict | None:
        row = call(
            connection, "clinic_patient_get", str(patient_id), scope, str(user_id)
        ).fetchone()
        return _patient(row) if row else None

    @staticmethod
    def create_patient(connection: pyodbc.Connection, code: str, fields: dict) -> UUID:
        row = call(
            connection, "clinic_patient_create", code,
            fields["full_name"],
            fields["date_of_birth"],
            fields["gender"],
            fields["phone"],
            fields["email"],
            fields["address"],
            fields["insurance_number"],
        ).fetchone()
        return UUID(str(row.patient_id))

    @staticmethod
    def lock_patient(connection: pyodbc.Connection, patient_id: UUID) -> pyodbc.Row | None:
        return call(connection, "clinic_patient_lock", str(patient_id)).fetchone()

    @staticmethod
    def update_patient(connection: pyodbc.Connection, patient_id: UUID, fields: dict) -> None:
        call(
            connection, "clinic_patient_update", str(patient_id),
            fields["full_name"],
            fields["date_of_birth"],
            fields["gender"],
            fields["phone"],
            fields["email"],
            fields["address"],
            fields["insurance_number"],
        )

    @staticmethod
    def delete_patient(
        connection: pyodbc.Connection, patient_id: UUID, user_id: UUID | None
    ) -> None:
        call(
            connection, "clinic_patient_delete", str(patient_id),
            str(user_id) if user_id else None,
        )

    @staticmethod
    def has_active_care(connection: pyodbc.Connection, patient_id: UUID) -> bool:
        row = call(connection, "clinic_patient_has_active_care", str(patient_id)).fetchone()
        return bool(row.has_active_care)
