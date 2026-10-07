from uuid import UUID

import pyodbc

from BLL.auth_service import RequestMetadata
from Core.errors import AppError, PermissionDeniedError
from DAL.auth_repository import AuthRepository
from DAL.medical_history_repository import MedicalHistoryRepository
from DAL.patient_repository import PatientRepository
from Model.auth import UserResponse
from Model.medical_histories import (
    MedicalHistoryCreateRequest,
    MedicalHistoryListResponse,
    MedicalHistoryUpdateRequest,
)


class MedicalHistoryService:
    def __init__(self) -> None:
        self.repository = MedicalHistoryRepository()
        self.patients = PatientRepository()
        self.audit_repository = AuthRepository()

    @staticmethod
    def _read_scope(actor: UserResponse) -> str:
        if "medical_histories.read_assigned" in actor.permissions:
            return "assigned"
        if "medical_histories.read_self" in actor.permissions:
            return "self"
        raise PermissionDeniedError(
            ["medical_histories.read_assigned", "medical_histories.read_self"]
        )

    @staticmethod
    def _write_scope(actor: UserResponse) -> str:
        if "medical_histories.write_assigned" not in actor.permissions:
            raise PermissionDeniedError(["medical_histories.write_assigned"])
        return "assigned"

    def _assert_patient(
        self, connection: pyodbc.Connection, patient_id: UUID, actor: UserResponse, scope: str
    ) -> None:
        patient = self.patients.get_patient(
            connection, patient_id, scope=scope, user_id=actor.user_id
        )
        if patient is None:
            raise AppError(
                404, "PATIENT_NOT_FOUND", "Không tìm thấy bệnh nhân trong phạm vi được xem."
            )

    @staticmethod
    def _missing_history() -> AppError:
        return AppError(404, "MEDICAL_HISTORY_NOT_FOUND", "Không tìm thấy mục tiền sử bệnh.")

    def list_for_patient(
        self, connection: pyodbc.Connection, patient_id: UUID, actor: UserResponse, **filters
    ) -> MedicalHistoryListResponse:
        self._assert_patient(connection, patient_id, actor, self._read_scope(actor))
        items, total = self.repository.list_for_patient(connection, patient_id, **filters)
        return MedicalHistoryListResponse(
            items=items, total=total, page=filters["page"], page_size=filters["page_size"]
        )

    def get(
        self, connection: pyodbc.Connection, patient_id: UUID, history_id: UUID, actor: UserResponse
    ) -> dict:
        self._assert_patient(connection, patient_id, actor, self._read_scope(actor))
        item = self.repository.get(connection, patient_id, history_id)
        if item is None:
            raise self._missing_history()
        return item

    def create(
        self,
        connection: pyodbc.Connection,
        patient_id: UUID,
        payload: MedicalHistoryCreateRequest,
        actor: UserResponse,
        metadata: RequestMetadata,
    ) -> dict:
        scope = self._write_scope(actor)
        try:
            self._assert_patient(connection, patient_id, actor, scope)
            fields = payload.model_dump(mode="python")
            history_id = self.repository.create(connection, patient_id, actor.user_id, fields)
            self.audit_repository.audit(
                connection,
                action="medical_histories.create",
                entity_type="medical_histories",
                actor_user_id=actor.user_id,
                entity_id=history_id,
                after={"patient_id": str(patient_id), "type": fields["type"], "version_no": 1},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            item = self.repository.get(connection, patient_id, history_id)
            if item is None:
                raise RuntimeError("Created medical history could not be reloaded")
            connection.commit()
            return item
        except Exception:
            connection.rollback()
            raise

    def update(
        self,
        connection: pyodbc.Connection,
        patient_id: UUID,
        history_id: UUID,
        payload: MedicalHistoryUpdateRequest,
        actor: UserResponse,
        metadata: RequestMetadata,
    ) -> dict:
        scope = self._write_scope(actor)
        try:
            self._assert_patient(connection, patient_id, actor, scope)
            current = self.repository.lock(connection, patient_id, history_id)
            if current is None:
                raise self._missing_history()
            if bytes(current.row_version).hex().upper() != payload.version.upper():
                raise AppError(
                    409, "MEDICAL_HISTORY_VERSION_CONFLICT",
                    "Mục tiền sử bệnh đã được người khác cập nhật.",
                )
            fields = payload.model_dump(mode="python", exclude={"version"})
            self.repository.update(connection, patient_id, history_id, fields)
            self.audit_repository.audit(
                connection,
                action="medical_histories.update",
                entity_type="medical_histories",
                actor_user_id=actor.user_id,
                entity_id=history_id,
                after={
                    "patient_id": str(patient_id),
                    "type": fields["type"],
                    "version_no": int(current.version_no) + 1,
                },
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            item = self.repository.get(connection, patient_id, history_id)
            if item is None:
                raise RuntimeError("Updated medical history could not be reloaded")
            connection.commit()
            return item
        except Exception:
            connection.rollback()
            raise

    def delete(
        self,
        connection: pyodbc.Connection,
        patient_id: UUID,
        history_id: UUID,
        version: str,
        actor: UserResponse,
        metadata: RequestMetadata,
    ) -> None:
        scope = self._write_scope(actor)
        try:
            self._assert_patient(connection, patient_id, actor, scope)
            current = self.repository.lock(connection, patient_id, history_id)
            if current is None:
                raise self._missing_history()
            if bytes(current.row_version).hex().upper() != version.upper():
                raise AppError(
                    409, "MEDICAL_HISTORY_VERSION_CONFLICT",
                    "Mục tiền sử bệnh đã được người khác cập nhật.",
                )
            self.repository.delete(connection, patient_id, history_id)
            self.audit_repository.audit(
                connection,
                action="medical_histories.delete",
                entity_type="medical_histories",
                actor_user_id=actor.user_id,
                entity_id=history_id,
                after={"patient_id": str(patient_id), "type": current.type, "deleted": True},
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                request_id=metadata.request_id,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
