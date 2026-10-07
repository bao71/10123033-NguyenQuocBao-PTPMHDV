import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pyodbc

from BLL.auth_service import RequestMetadata
from Core.errors import AppError, PermissionDeniedError
from DAL.appointment_repository import AppointmentRepository
from DAL.auth_repository import AuthRepository
from DAL.patient_repository import PatientRepository
from Model.appointments import (
    AppointmentCancelRequest,
    AppointmentCreateRequest,
    AppointmentListResponse,
    AppointmentUpdateRequest,
    DoctorListResponse,
    ScheduleCreateRequest,
    ScheduleListResponse,
    SlotListResponse,
)
from Model.auth import UserResponse

CLINIC_TIMEZONE = timezone(timedelta(hours=7))
DATABASE_ERRORS = {
    51313: (409, "RECEPTION_STATE_CONFLICT", "Trạng thái lịch hẹn không cho phép tiếp nhận."),
    51314: (
        409,
        "RECEPTION_TIME_CONFLICT",
        "Chỉ check-in đúng ngày hẹn; chỉ ghi vắng sau khi hết lượt khám.",
    ),
    51301: (404, "APPOINTMENT_NOT_FOUND", "Không tìm thấy lịch hẹn hoặc ca làm."),
    51302: (409, "APPOINTMENT_VERSION_CONFLICT", "Dữ liệu đã thay đổi. Hãy tải lại trước khi sửa."),
    51303: (409, "APPOINTMENT_STATE_CONFLICT", "Lịch hẹn hiện tại không thể sửa/hủy."),
    51304: (422, "INVALID_APPOINTMENT_TIME", "Giờ hẹn hoặc ca làm không hợp lệ, hoặc đã qua."),
    51305: (409, "SCHEDULE_UNAVAILABLE", "Giờ hẹn không thuộc khung giờ của ca làm hoạt động."),
    51306: (409, "DOCTOR_TIME_CONFLICT", "Bác sĩ đã có lịch khám trùng giờ."),
    51307: (409, "PATIENT_TIME_CONFLICT", "Bệnh nhân đã có lịch khám trùng giờ."),
    51308: (404, "PATIENT_NOT_FOUND", "Không tìm thấy bệnh nhân trong phạm vi được phép."),
    51309: (404, "DOCTOR_NOT_FOUND", "Bác sĩ không còn hoạt động."),
    51310: (503, "APPOINTMENT_BUSY", "Hệ thống đang xử lý lịch hẹn. Vui lòng thử lại."),
    51311: (409, "SCHEDULE_TIME_CONFLICT", "Ca làm của bác sĩ bị trùng giờ."),
    51312: (
        409,
        "SCHEDULE_HAS_APPOINTMENTS",
        "Cần đổi/hủy lịch hẹn đang hoạt động trong ca trước.",
    ),
}


def database_error(exc: pyodbc.Error) -> AppError | None:
    match = re.search(r"\((513\d{2})\)", str(exc))
    if match and int(match.group(1)) in DATABASE_ERRORS:
        return AppError(*DATABASE_ERRORS[int(match.group(1))])
    if isinstance(exc, pyodbc.IntegrityError):
        return AppError(409, "APPOINTMENT_CONFLICT", "Lịch hẹn xung đột với dữ liệu hiện có.")
    return None


def utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def date_range(date_from: date | None, date_to: date | None) -> dict:
    if date_from and date_to and date_from > date_to:
        raise AppError(422, "INVALID_DATE_RANGE", "Ngày bắt đầu không được sau ngày kết thúc.")
    if date_to == date.max:
        raise AppError(422, "INVALID_DATE_RANGE", "Ngày kết thúc vượt phạm vi được hỗ trợ.")

    def midnight(value: date) -> datetime:
        return utc_naive(datetime.combine(value, datetime.min.time(), CLINIC_TIMEZONE))

    return {
        "start_at": midnight(date_from) if date_from else None,
        "end_at": midnight(date_to + timedelta(days=1)) if date_to else None,
    }


class AppointmentService:
    def __init__(self) -> None:
        self.repository = AppointmentRepository()
        self.audit_repository = AuthRepository()

    @staticmethod
    def read_scope(actor: UserResponse) -> str:
        for permission, scope in (
            ("appointments.read", "all"),
            ("appointments.read_assigned", "assigned"),
            ("appointments.read_self", "self"),
        ):
            if permission in actor.permissions:
                return scope
        raise PermissionDeniedError(
            ["appointments.read", "appointments.read_assigned", "appointments.read_self"]
        )

    @staticmethod
    def write_scope(actor: UserResponse, action: str) -> str:
        if f"appointments.{action}" in actor.permissions:
            return "all"
        if f"appointments.{action}_self" in actor.permissions:
            return "self"
        raise PermissionDeniedError([f"appointments.{action}", f"appointments.{action}_self"])

    @staticmethod
    def require(actor: UserResponse, permission: str) -> None:
        if permission not in actor.permissions:
            raise PermissionDeniedError([permission])

    def audit(self, connection, actor, metadata, action, entity, entity_id, after) -> None:
        self.audit_repository.audit(
            connection,
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            actor_user_id=actor.user_id,
            after=after,
            ip_address=metadata.ip_address,
            user_agent=metadata.user_agent,
            request_id=metadata.request_id,
        )

    def list(self, connection, actor, *, date_from=None, date_to=None, **filters):
        items, total = self.repository.list_appointments(
            connection,
            scope=self.read_scope(actor),
            user_id=actor.user_id,
            **date_range(date_from, date_to),
            **filters,
        )
        return AppointmentListResponse(
            items=items, total=total, page=filters["page"], page_size=filters["page_size"]
        )

    def get(self, connection, appointment_id, actor) -> dict:
        item = self.repository.get(
            connection,
            appointment_id,
            scope=self.read_scope(actor),
            user_id=actor.user_id,
        )
        if item is None:
            raise AppError(404, "APPOINTMENT_NOT_FOUND", "Không tìm thấy lịch hẹn.")
        return item

    def write(
        self,
        connection: pyodbc.Connection,
        actor: UserResponse,
        metadata: RequestMetadata,
        payload: AppointmentCreateRequest | AppointmentUpdateRequest | AppointmentCancelRequest,
        *,
        action: str,
        appointment_id: UUID | None = None,
    ) -> dict:
        scope = self.write_scope(actor, action)
        fields = payload.model_dump(mode="python")
        if action == "create":
            if scope == "self":
                if fields["patient_id"] not in (None, actor.patient_id) or not actor.patient_id:
                    raise AppError(404, "PATIENT_NOT_FOUND", "Không tìm thấy hồ sơ của bạn.")
                fields["patient_id"] = actor.patient_id
            elif not fields["patient_id"]:
                raise AppError(422, "PATIENT_REQUIRED", "Vui lòng chọn bệnh nhân.")
        if "appointment_at" in fields:
            fields["appointment_at"] = utc_naive(fields["appointment_at"])
        try:
            saved_id = self.repository.write(
                connection,
                action=action,
                scope=scope,
                actor_id=actor.user_id,
                appointment_id=appointment_id,
                **fields,
            )
            item = self.repository.get(connection, saved_id, scope=scope, user_id=actor.user_id)
            if item is None:
                raise RuntimeError("Saved appointment could not be reloaded")
            self.audit(
                connection,
                actor,
                metadata,
                f"appointments.{action}",
                "appointments",
                saved_id,
                {
                    "patient_id": str(item["patient_id"]),
                    "doctor_id": str(item["doctor_id"]),
                    "appointment_at": item["appointment_at"].isoformat(),
                    "status": item["status"],
                },
            )
            connection.commit()
            return item
        except pyodbc.Error as exc:
            connection.rollback()
            error = database_error(exc)
            if error:
                raise error from exc
            raise
        except Exception:
            connection.rollback()
            raise

    def doctors(self, connection, actor, **filters) -> DoctorListResponse:
        self.require(actor, "doctors.read")
        items, total = self.repository.doctors(connection, **filters)
        return DoctorListResponse(
            items=items, total=total, page=filters["page"], page_size=filters["page_size"]
        )

    def schedules(self, connection, actor, *, date_from=None, date_to=None, **filters):
        self.require(actor, "doctor_schedules.read")
        items, total = self.repository.schedules(
            connection, **date_range(date_from, date_to), **filters
        )
        return ScheduleListResponse(
            items=items, total=total, page=filters["page"], page_size=filters["page_size"]
        )

    def write_schedule(
        self, connection, actor, metadata, *, payload=None, schedule_id=None, version=None
    ) -> dict:
        self.require(actor, "doctor_schedules.manage")
        fields = {}
        action = "cancel"
        if isinstance(payload, ScheduleCreateRequest):
            action = "create"
            fields = payload.model_dump(mode="python")
            fields["start_at"] = utc_naive(fields["start_at"])
            fields["end_at"] = utc_naive(fields["end_at"])
            if fields["start_at"].date() != fields["end_at"].date():
                raise AppError(422, "INVALID_SCHEDULE_RANGE", "Ca làm phải nằm trong một ngày UTC.")
        try:
            saved_id = self.repository.write_schedule(
                connection,
                action=action,
                schedule_id=schedule_id,
                version=version,
                **fields,
            )
            items, _ = self.repository.schedules(connection, schedule_id=saved_id)
            if not items:
                raise RuntimeError("Saved schedule could not be reloaded")
            self.audit(
                connection,
                actor,
                metadata,
                f"doctor_schedules.{action}",
                "doctor_schedules",
                saved_id,
                {
                    "doctor_id": str(items[0]["doctor_id"]),
                    "start_at": items[0]["start_at"].isoformat(),
                    "status": items[0]["status"],
                },
            )
            connection.commit()
            return items[0]
        except pyodbc.Error as exc:
            connection.rollback()
            error = database_error(exc)
            if error:
                raise error from exc
            raise
        except Exception:
            connection.rollback()
            raise

    def slots(
        self, connection, actor, doctor_id, work_date, patient_id=None, exclude_appointment_id=None
    ):
        self.require(actor, "doctor_schedules.read")
        if exclude_appointment_id:
            scope = self.write_scope(actor, "update")
            existing = self.repository.get(
                connection,
                exclude_appointment_id,
                scope=scope,
                user_id=actor.user_id,
            )
            if existing is None:
                raise AppError(404, "APPOINTMENT_NOT_FOUND", "Không tìm thấy lịch hẹn.")
            patient_id = UUID(str(existing["patient_id"]))
        if "appointments.create" not in actor.permissions:
            patient_id = actor.patient_id
        elif patient_id:
            if (
                PatientRepository.get_patient(
                    connection, patient_id, scope="all", user_id=actor.user_id
                )
                is None
            ):
                raise AppError(404, "PATIENT_NOT_FOUND", "Không tìm thấy bệnh nhân.")
        try:
            bounds = date_range(work_date, work_date)
            items = self.repository.slots(
                connection,
                doctor_id,
                bounds["start_at"],
                bounds["end_at"],
                patient_id,
                exclude_appointment_id,
            )
            return SlotListResponse(doctor_id=doctor_id, work_date=work_date, items=items)
        except pyodbc.Error as exc:
            error = database_error(exc)
            if error:
                raise error from exc
            raise
