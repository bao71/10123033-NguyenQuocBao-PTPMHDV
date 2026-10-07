from uuid import UUID

from DAL.appointment_repository import _appointment
from DAL.procedures import call


class ReceptionRepository:
    @staticmethod
    def list(
        connection,
        *,
        start_at,
        end_at,
        page,
        page_size,
        search=None,
        doctor_id=None,
        status=None,
        sort_order="asc",
    ):
        cursor = call(
            connection,
            "clinic_reception_list",
            start_at,
            end_at,
            page,
            page_size,
            search,
            str(doctor_id) if doctor_id else None,
            status,
            sort_order,
        )
        columns = [column[0] for column in cursor.description]
        summary = dict(zip(columns, cursor.fetchone(), strict=True))
        cursor.nextset()
        total = cursor.fetchone().total
        cursor.nextset()
        return [_appointment(row) for row in cursor.fetchall()], total, summary

    @staticmethod
    def receive(connection, appointment_id, *, target_status, version):
        row = call(
            connection,
            "clinic_appointment_receive",
            str(appointment_id),
            target_status,
            bytes.fromhex(version),
        ).fetchone()
        return UUID(str(row.appointment_id)), row.previous_status
