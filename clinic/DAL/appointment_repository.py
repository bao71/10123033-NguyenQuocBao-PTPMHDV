from datetime import datetime, time, timezone
from uuid import UUID

import pyodbc

from DAL.procedures import call


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc)


def _appointment(row: pyodbc.Row) -> dict:
    return {
        "appointment_id": row.appointment_id,
        "patient_id": row.patient_id,
        "patient_code": row.patient_code,
        "patient_name": row.patient_name,
        "doctor_id": row.doctor_id,
        "doctor_code": row.doctor_code,
        "doctor_name": row.doctor_name,
        "specialty": row.specialty,
        "schedule_id": row.schedule_id,
        "appointment_at": _utc(row.appointment_at),
        "ends_at": _utc(row.ends_at),
        "duration_minutes": row.duration_minutes,
        "reason": row.reason,
        "status": row.status,
        "cancellation_reason": row.cancellation_reason,
        "created_at": _utc(row.created_at),
        "updated_at": _utc(row.updated_at),
        "version": bytes(row.row_version).hex().upper(),
    }


def _schedule(row: pyodbc.Row) -> dict:
    # TIME columns are returned as datetime.time by pyodbc.
    start = (
        row.start_time if isinstance(row.start_time, time) else time.fromisoformat(row.start_time)
    )
    end = row.end_time if isinstance(row.end_time, time) else time.fromisoformat(row.end_time)
    return {
        "schedule_id": row.schedule_id,
        "doctor_id": row.doctor_id,
        "doctor_code": row.doctor_code,
        "doctor_name": row.doctor_name,
        "specialty": row.specialty,
        "start_at": datetime.combine(row.work_date, start, timezone.utc),
        "end_at": datetime.combine(row.work_date, end, timezone.utc),
        "slot_minutes": row.slot_minutes,
        "status": row.status,
        "version": bytes(row.row_version).hex().upper(),
    }


class AppointmentRepository:
    @staticmethod
    def list_appointments(
        connection: pyodbc.Connection,
        *,
        scope: str,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search=None,
        doctor_id=None,
        patient_id=None,
        status=None,
        start_at=None,
        end_at=None,
        sort_by="appointment_at",
        sort_order="asc",
        appointment_id=None,
    ) -> tuple[list[dict], int]:
        cursor = call(
            connection,
            "clinic_appointment_list",
            scope,
            str(user_id),
            page,
            page_size,
            search,
            str(doctor_id) if doctor_id else None,
            str(patient_id) if patient_id else None,
            status,
            start_at,
            end_at,
            sort_by,
            sort_order,
            str(appointment_id) if appointment_id else None,
        )
        total = int(cursor.fetchone().total)
        cursor.nextset()
        return [_appointment(row) for row in cursor.fetchall()], total

    @classmethod
    def get(cls, connection, appointment_id, *, scope, user_id) -> dict | None:
        items, _ = cls.list_appointments(
            connection,
            scope=scope,
            user_id=user_id,
            appointment_id=appointment_id,
        )
        return items[0] if items else None

    @staticmethod
    def write(
        connection,
        *,
        action,
        scope,
        actor_id,
        appointment_id=None,
        patient_id=None,
        doctor_id=None,
        schedule_id=None,
        appointment_at=None,
        reason=None,
        version=None,
        cancellation_reason=None,
    ) -> UUID:
        row = call(
            connection,
            "clinic_appointment_write",
            action,
            scope,
            str(actor_id),
            str(appointment_id) if appointment_id else None,
            str(patient_id) if patient_id else None,
            str(doctor_id) if doctor_id else None,
            str(schedule_id) if schedule_id else None,
            appointment_at,
            reason,
            bytes.fromhex(version) if version else None,
            cancellation_reason,
        ).fetchone()
        return UUID(str(row.appointment_id))

    @staticmethod
    def doctors(connection, *, page, page_size, search) -> tuple[list[dict], int]:
        cursor = call(connection, "clinic_doctor_list", page, page_size, search)
        total = int(cursor.fetchone().total)
        cursor.nextset()
        return [
            dict(zip([c[0] for c in cursor.description], row, strict=True))
            for row in cursor.fetchall()
        ], total

    @staticmethod
    def schedules(
        connection,
        *,
        page=1,
        page_size=20,
        doctor_id=None,
        start_at=None,
        end_at=None,
        status=None,
        schedule_id=None,
    ) -> tuple[list[dict], int]:
        cursor = call(
            connection,
            "clinic_schedule_list",
            page,
            page_size,
            str(doctor_id) if doctor_id else None,
            start_at,
            end_at,
            status,
            str(schedule_id) if schedule_id else None,
        )
        total = int(cursor.fetchone().total)
        cursor.nextset()
        return [_schedule(row) for row in cursor.fetchall()], total

    @staticmethod
    def write_schedule(
        connection,
        *,
        action,
        schedule_id=None,
        doctor_id=None,
        start_at=None,
        end_at=None,
        slot_minutes=30,
        version=None,
    ) -> UUID:
        row = call(
            connection,
            "clinic_schedule_write",
            action,
            str(schedule_id) if schedule_id else None,
            str(doctor_id) if doctor_id else None,
            start_at,
            end_at,
            slot_minutes,
            bytes.fromhex(version) if version else None,
        ).fetchone()
        return UUID(str(row.schedule_id))

    @staticmethod
    def slots(
        connection, doctor_id, start_at, end_at, patient_id=None, exclude_appointment_id=None
    ) -> list[dict]:
        rows = call(
            connection,
            "clinic_appointment_slots",
            str(doctor_id),
            start_at,
            end_at,
            str(patient_id) if patient_id else None,
            str(exclude_appointment_id) if exclude_appointment_id else None,
        ).fetchall()
        return [
            {
                "schedule_id": row.schedule_id,
                "appointment_at": _utc(row.appointment_at),
                "ends_at": _utc(row.ends_at),
                "duration_minutes": row.duration_minutes,
                "available": bool(row.available),
            }
            for row in rows
        ]
