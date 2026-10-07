import re

import pyodbc

from BLL.appointment_service import AppointmentService, date_range
from Core.errors import AppError, PermissionDeniedError
from DAL.encounter_repository import EncounterRepository
from Model.encounters import EncounterDetail, EncounterListResponse, EncounterVersionListResponse

CLINICAL_ERRORS = {
    51401: (404, "ENCOUNTER_NOT_FOUND", "Không tìm thấy bệnh án trong phạm vi được phép."),
    51402: (409, "ENCOUNTER_VERSION_CONFLICT", "Bệnh án đã thay đổi. Hãy tải lại trước khi sửa."),
    51403: (
        409,
        "ENCOUNTER_STATE_CONFLICT",
        "Bệnh án đã khóa hoặc trạng thái không cho phép thao tác.",
    ),
    51404: (409, "APPOINTMENT_NOT_READY", "Lịch hẹn phải được check-in trước khi bắt đầu khám."),
    51405: (422, "DIAGNOSIS_REQUIRED", "Cần kết luận và một chẩn đoán chính trước khi hoàn tất."),
    51406: (
        409,
        "CLINICAL_ORDERS_PENDING",
        "Còn chỉ định chưa có kết quả. Nhập kết quả hoặc hủy chỉ định.",
    ),
    51407: (404, "CLINICAL_ORDER_NOT_FOUND", "Không tìm thấy chỉ định trong bệnh án."),
    51408: (409, "CLINICAL_ORDER_STATE_CONFLICT", "Chỉ định đã có kết quả hoặc đã bị hủy."),
    51409: (404, "CLINICAL_RESULT_NOT_FOUND", "Không tìm thấy kết quả trong chỉ định."),
    51410: (503, "ENCOUNTER_BUSY", "Đang xử lý bệnh án. Vui lòng thử lại."),
}


class EncounterService:
    def __init__(self):
        self.repository = EncounterRepository()
        self.appointments = AppointmentService()

    @staticmethod
    def read_scope(actor):
        if "encounters.read_assigned" in actor.permissions:
            return "assigned"
        if "encounters.read_self" in actor.permissions:
            return "self"
        raise PermissionDeniedError(["encounters.read_assigned", "encounters.read_self"])

    def list(self, connection, actor, *, date_from=None, date_to=None, **filters):
        items, total = self.repository.list(
            connection,
            scope=self.read_scope(actor),
            user_id=actor.user_id,
            **date_range(date_from, date_to),
            **filters,
        )
        return EncounterListResponse(
            items=items, total=total, page=filters["page"], page_size=filters["page_size"]
        )

    def get(self, connection, encounter_id, actor):
        item = self.repository.get(
            connection, encounter_id, scope=self.read_scope(actor), user_id=actor.user_id
        )
        if item is None:
            raise AppError(*CLINICAL_ERRORS[51401])
        if (
            self.read_scope(actor) == "self"
            and "clinical_results.read_self" not in actor.permissions
        ):
            for order in item["clinical_orders"]:
                order["results"] = []
        return EncounterDetail.model_validate(item)

    def write(
        self,
        connection,
        actor,
        metadata,
        payload,
        *,
        action,
        encounter_id=None,
        order_id=None,
        result_id=None,
    ):
        if action.startswith("order_"):
            permission = "clinical_orders.write_assigned"
        elif action.startswith("result_"):
            permission = "clinical_results.write_assigned"
        else:
            permission = {
                "start": "encounters.create_assigned",
                "save": "encounters.update_assigned",
                "complete": "encounters.complete_assigned",
            }[action]
        self.appointments.require(actor, permission)
        self.appointments.require(actor, "encounters.read_assigned")
        fields = payload.model_dump(mode="python")
        try:
            saved_id = self.repository.write(
                connection,
                action=action,
                actor_id=actor.user_id,
                encounter_id=encounter_id,
                order_id=order_id,
                result_id=result_id,
                **fields,
            )
            item = self.get(connection, saved_id, actor)
            self.appointments.audit(
                connection,
                actor,
                metadata,
                f"encounters.{action}",
                "encounters",
                saved_id,
                {
                    "status": item.status,
                    "version_no": item.version_no,
                    "patient_id": str(item.patient_id),
                    "appointment_id": str(item.appointment_id),
                    "order_id": str(order_id) if order_id else None,
                    "result_id": str(result_id) if result_id else None,
                },
            )
            connection.commit()
            return item
        except pyodbc.Error as exc:
            connection.rollback()
            match = re.search(r"\((514\d{2})\)", str(exc))
            if match and int(match.group(1)) in CLINICAL_ERRORS:
                raise AppError(*CLINICAL_ERRORS[int(match.group(1))]) from exc
            if isinstance(exc, pyodbc.IntegrityError):
                raise AppError(409, "ENCOUNTER_CONFLICT", "Dữ liệu bệnh án xung đột.") from exc
            raise
        except Exception:
            connection.rollback()
            raise

    def versions(self, connection, encounter_id, actor, *, page, page_size):
        self.appointments.require(actor, "record_versions.read_assigned")
        self.appointments.require(actor, "encounters.read_assigned")
        self.get(connection, encounter_id, actor)
        items, total = self.repository.versions(
            connection, encounter_id, user_id=actor.user_id, page=page, page_size=page_size
        )
        return EncounterVersionListResponse(
            items=items, total=total, page=page, page_size=page_size
        )
