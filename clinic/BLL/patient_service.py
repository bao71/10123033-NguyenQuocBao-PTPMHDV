from datetime import datetime, timezone
from uuid import UUID, uuid4

import pyodbc

from BLL.auth_service import RequestMetadata
from Core.errors import AppError, PermissionDeniedError
from DAL.auth_repository import AuthRepository
from DAL.patient_repository import PatientRepository
from Model.auth import UserResponse
from Model.patients import PatientCreateRequest, PatientListResponse, PatientUpdateRequest


class PatientService:
    def __init__(self) -> None:
        self.repository = PatientRepository()
        self.audit_repository = AuthRepository()

    @staticmethod
    def _read_scope(actor: UserResponse) -> str:
        for permission, scope in (
            ("patients.read", "all"),
            ("patients.read_assigned", "assigned"),
            ("patients.read_self", "self"),
        ):
            if permission in actor.permissions:
                return scope
        raise PermissionDeniedError(
            ["patients.read", "patients.read_assigned", "patients.read_self"]
        )

    def list_patients(
        self, connection: pyodbc.Connection, actor: UserResponse, **filters
    ) -> PatientListResponse:
        items, total = self.repository.list_patients(
            connection, scope=self._read_scope(actor), user_id=actor.user_id, **filters
        )
        return PatientListResponse(
            items=items, total=total, page=filters["page"], page_size=filters["page_size"]
        )

    def get_patient(
        self, connection: pyodbc.Connection, patient_id: UUID, actor: UserResponse
    ) -> dict:
        item = self.repository.get_patient(
            connection, patient_id, scope=self._read_scope(actor), user_id=actor.user_id
        )
        if item is None:
            raise AppError(404, "PATIENT_NOT_FOUND", "Không tìm thấy bệnh nhân.")
        return item

    def create_patient(
        self,
        connection: pyodbc.Connection,
        payload: PatientCreateRequest,
        actor: UserResponse,
        metadata: RequestMetadata,
    ) -> dict:
        if "patients.create" not in actor.permissions:
            raise PermissionDeniedError(["patients.create"])
        code = f"BN{datetime.now(timezone.utc):%Y%m%d}{uuid4().hex[:10].upper()}"
        fields = payload.model_dump(mode="python")
        try:
            patient_id = self.repository.create_patient(connection, code, fields)
            self.audit_repository.audit(
                connection,
                action="patients.create",
                entity_type="patients",
                actor_user_id=actor.user_id,
                entity_id=patient_id,
                after={"patient_code": code},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            item = self.repository.get_patient(
                connection, patient_id, scope="all", user_id=actor.user_id
            )
            if item is None:
                raise RuntimeError("Created patient could not be reloaded")
            connection.commit()
            return item
        except pyodbc.IntegrityError as exc:
            connection.rollback()
            raise AppError(409, "PATIENT_CONFLICT", "Mã bệnh nhân đã tồn tại.") from exc
        except Exception:
            connection.rollback()
            raise

    def update_patient(
        self,
        connection: pyodbc.Connection,
        patient_id: UUID,
        payload: PatientUpdateRequest,
        actor: UserResponse,
        metadata: RequestMetadata,
    ) -> dict:
        if "patients.update" not in actor.permissions:
            raise PermissionDeniedError(["patients.update"])
        try:
            current = self.repository.lock_patient(connection, patient_id)
            if current is None:
                raise AppError(404, "PATIENT_NOT_FOUND", "Không tìm thấy bệnh nhân.")
            if bytes(current.row_version).hex().upper() != payload.version.upper():
                raise AppError(
                    409, "PATIENT_VERSION_CONFLICT", "Hồ sơ đã được người khác cập nhật."
                )
            self.repository.update_patient(
                connection, patient_id, payload.model_dump(mode="python", exclude={"version"})
            )
            self.audit_repository.audit(
                connection,
                action="patients.update",
                entity_type="patients",
                actor_user_id=actor.user_id,
                entity_id=patient_id,
                after={"patient_code": current.patient_code},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            item = self.repository.get_patient(
                connection, patient_id, scope="all", user_id=actor.user_id
            )
            if item is None:
                raise RuntimeError("Updated patient could not be reloaded")
            connection.commit()
            return item
        except Exception:
            connection.rollback()
            raise

    def delete_patient(
        self,
        connection: pyodbc.Connection,
        patient_id: UUID,
        version: str,
        actor: UserResponse,
        metadata: RequestMetadata,
    ) -> None:
        if "patients.delete" not in actor.permissions:
            raise PermissionDeniedError(["patients.delete"])
        try:
            current = self.repository.lock_patient(connection, patient_id)
            if current is None:
                raise AppError(404, "PATIENT_NOT_FOUND", "Không tìm thấy bệnh nhân.")
            if bytes(current.row_version).hex().upper() != version.upper():
                raise AppError(
                    409, "PATIENT_VERSION_CONFLICT", "Hồ sơ đã được người khác cập nhật."
                )
            if self.repository.has_active_care(connection, patient_id):
                raise AppError(
                    409,
                    "PATIENT_HAS_ACTIVE_CARE",
                    "Không thể xóa hồ sơ khi còn lịch hẹn hoặc lượt khám đang mở.",
                )
            self.repository.delete_patient(connection, patient_id, current.user_id)
            self.audit_repository.audit(
                connection,
                action="patients.delete",
                entity_type="patients",
                actor_user_id=actor.user_id,
                entity_id=patient_id,
                after={"patient_code": current.patient_code},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
