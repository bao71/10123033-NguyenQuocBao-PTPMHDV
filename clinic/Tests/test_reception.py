from unittest.mock import Mock
from uuid import uuid4

import pyodbc
import pytest
from pydantic import ValidationError

from BLL.auth_service import RequestMetadata
from BLL.reception_service import ReceptionService
from Core.errors import AppError, PermissionDeniedError
from Model.reception import ReceptionRequest
from Tests.test_appointments import actor


def test_reception_requires_global_action_and_read_permissions():
    service = ReceptionService()
    for permissions in (
        ["appointments.read_self"],
        ["appointments.read_assigned"],
        ["appointments.read"],
        ["appointments.check_in"],
    ):
        with pytest.raises(PermissionDeniedError):
            service.list(None, actor(permissions), page=1, page_size=20)
    with pytest.raises(PermissionDeniedError):
        service.receive(
            None,
            actor(["appointments.read", "appointments.check_in"]),
            None,
            uuid4(),
            ReceptionRequest(version="0000000000000001"),
            action="confirm",
        )


def test_reception_audit_failure_rolls_back_state_change():
    service = ReceptionService()
    connection = Mock()
    saved_id = uuid4()
    service.repository = Mock()
    service.repository.receive.return_value = (saved_id, "booked")
    service.appointments.repository = Mock()
    service.appointments.repository.get.return_value = {
        "status": "checked_in",
        "patient_id": uuid4(),
        "doctor_id": uuid4(),
    }
    service.appointments.audit_repository = Mock()
    service.appointments.audit_repository.audit.side_effect = RuntimeError("audit unavailable")
    metadata = RequestMetadata(ip_address="127.0.0.1", user_agent="test", request_id=uuid4())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.receive(
            connection,
            actor(["appointments.read", "appointments.check_in"]),
            metadata,
            saved_id,
            ReceptionRequest(version="0000000000000001"),
            action="check_in",
        )
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_reception_maps_database_conflicts_without_committing():
    service = ReceptionService()
    connection = Mock()
    service.repository = Mock()
    service.repository.receive.side_effect = pyodbc.Error("42000", "Version conflict. (51302)")
    with pytest.raises(AppError) as caught:
        service.receive(
            connection,
            actor(["appointments.read", "appointments.check_in"]),
            None,
            uuid4(),
            ReceptionRequest(version="0000000000000001"),
            action="check_in",
        )
    assert caught.value.code == "APPOINTMENT_VERSION_CONFLICT"
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_reception_requires_version_and_rejects_client_status():
    for payload in ({}, {"version": "1"}, {"version": "0000000000000001", "status": "completed"}):
        with pytest.raises(ValidationError):
            ReceptionRequest(**payload)
