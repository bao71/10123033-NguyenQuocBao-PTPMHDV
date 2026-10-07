from uuid import UUID

import pyodbc

from DAL.procedures import call


def _history(row: pyodbc.Row) -> dict:
    return {
        "history_id": UUID(str(row.history_id)),
        "patient_id": UUID(str(row.patient_id)),
        "created_by": UUID(str(row.created_by)),
        "type": row.type,
        "name": row.name,
        "description": row.description,
        "onset_date": row.onset_date,
        "is_active": bool(row.is_active),
        "version_no": int(row.version_no),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "version": bytes(row.row_version).hex().upper(),
    }


class MedicalHistoryRepository:
    @staticmethod
    def list_for_patient(
        connection: pyodbc.Connection,
        patient_id: UUID,
        *,
        page: int,
        page_size: int,
        type: str | None,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[dict], int]:
        cursor = call(
            connection, "clinic_history_list", str(patient_id), page, page_size,
            type, is_active, search, sort_by, sort_order,
        )
        count = cursor.fetchone()
        cursor.nextset()
        return [_history(row) for row in cursor.fetchall()], int(count.total)

    @staticmethod
    def get(connection: pyodbc.Connection, patient_id: UUID, history_id: UUID) -> dict | None:
        row = call(connection, "clinic_history_get", str(patient_id), str(history_id)).fetchone()
        return _history(row) if row else None

    @staticmethod
    def lock(
        connection: pyodbc.Connection, patient_id: UUID, history_id: UUID
    ) -> pyodbc.Row | None:
        return call(connection, "clinic_history_lock", str(patient_id), str(history_id)).fetchone()

    @staticmethod
    def create(
        connection: pyodbc.Connection, patient_id: UUID, doctor_user_id: UUID, fields: dict
    ) -> UUID:
        row = call(
            connection, "clinic_history_create", str(patient_id), str(doctor_user_id),
            fields["type"], fields["name"], fields["description"],
            fields["onset_date"], fields["is_active"],
        ).fetchone()
        return UUID(str(row.history_id))

    @staticmethod
    def update(
        connection: pyodbc.Connection, patient_id: UUID, history_id: UUID, fields: dict
    ) -> None:
        call(
            connection, "clinic_history_update", str(patient_id), str(history_id),
            fields["type"], fields["name"], fields["description"],
            fields["onset_date"], fields["is_active"],
        )

    @staticmethod
    def delete(connection: pyodbc.Connection, patient_id: UUID, history_id: UUID) -> None:
        call(connection, "clinic_history_delete", str(patient_id), str(history_id))
