from datetime import datetime

import pyodbc

from BLL.appointment_service import (
    CLINIC_TIMEZONE,
    AppointmentService,
    database_error,
    date_range,
)
from Core.errors import AppError
from DAL.reception_repository import ReceptionRepository
from Model.reception import ReceptionListResponse


class ReceptionService:
    def __init__(self):
        self.repository = ReceptionRepository()
        self.appointments = AppointmentService()

    def list(self, connection, actor, *, work_date=None, **filters):
        self.appointments.require(actor, "appointments.check_in")
        self.appointments.require(actor, "appointments.read")
        work_date = work_date or datetime.now(CLINIC_TIMEZONE).date()
        items, total, summary = self.repository.list(
            connection,
            **date_range(work_date, work_date),
            **filters,
        )
        return ReceptionListResponse(
            work_date=work_date,
            summary=summary,
            items=items,
            total=total,
            page=filters["page"],
            page_size=filters["page_size"],
        )

    def receive(self, connection, actor, metadata, appointment_id, payload, *, action):
        target = {"confirm": "confirmed", "check_in": "checked_in", "no_show": "no_show"}
        if action not in target:
            raise AppError(422, "INVALID_RECEPTION_ACTION", "Thao tác tiếp nhận không hợp lệ.")
        permission = "appointments.update" if action == "confirm" else "appointments.check_in"
        self.appointments.require(actor, permission)
        self.appointments.require(actor, "appointments.read")
        try:
            saved_id, previous_status = self.repository.receive(
                connection,
                appointment_id,
                target_status=target[action],
                version=payload.version,
            )
            item = self.appointments.repository.get(
                connection,
                saved_id,
                scope="all",
                user_id=actor.user_id,
            )
            if item is None:
                raise RuntimeError("Received appointment could not be reloaded")
            self.appointments.audit(
                connection,
                actor,
                metadata,
                f"appointments.{action}",
                "appointments",
                saved_id,
                {
                    "previous_status": previous_status,
                    "status": item["status"],
                    "patient_id": str(item["patient_id"]),
                    "doctor_id": str(item["doctor_id"]),
                },
            )
            connection.commit()
            return item
        except pyodbc.Error as exc:
            connection.rollback()
            mapped = database_error(exc)
            if mapped:
                raise mapped from exc
            raise
        except Exception:
            connection.rollback()
            raise
