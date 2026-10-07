from unittest.mock import Mock
from uuid import uuid4

import pyodbc
import pytest
from pydantic import ValidationError

from BLL.encounter_service import EncounterService
from Core.errors import AppError, PermissionDeniedError
from Model.encounters import (
    ClinicalResultCreateRequest,
    EncounterUpdateRequest,
    EncounterVersionRequest,
    VitalSigns,
)
from Tests.test_appointments import actor

VERSION = "0000000000000001"


def test_clinical_scopes_and_action_permissions_are_separate():
    service = EncounterService()
    assert service.read_scope(actor(["encounters.read_assigned"])) == "assigned"
    assert service.read_scope(actor(["encounters.read_self"])) == "self"
    for permissions in ([], ["appointments.read"], ["patients.read"]):
        with pytest.raises(PermissionDeniedError):
            service.read_scope(actor(permissions))
    for action in ("start", "save", "complete", "order_create", "result_create"):
        with pytest.raises(PermissionDeniedError):
            service.write(
                None,
                actor(["encounters.read_assigned"]),
                None,
                EncounterVersionRequest(version=VERSION),
                action=action,
            )


def test_vitals_diagnoses_and_result_validation():
    for values in (
        {"temperature_c": float("nan")},
        {"spo2_percent": 101},
        {"weight_kg": 0},
        {"systolic_mmhg": 90, "diastolic_mmhg": 100},
    ):
        with pytest.raises(ValidationError):
            VitalSigns(**values)
    with pytest.raises(ValidationError):
        EncounterUpdateRequest(
            version=VERSION,
            diagnoses=[
                {"name": "A", "is_primary": True},
                {"name": "B", "is_primary": True},
            ],
        )
    fields = {"version": VERSION, "order_version": VERSION}
    with pytest.raises(ValidationError):
        ClinicalResultCreateRequest(**fields, result_text="  ")
    assert ClinicalResultCreateRequest(**fields, numeric_value=0).numeric_value == 0
    with pytest.raises(ValidationError):
        ClinicalResultCreateRequest(**fields, numeric_value="1.0000001")
    with pytest.raises(ValidationError):
        EncounterUpdateRequest(version=VERSION, doctor_id=uuid4())


def test_clinical_database_conflict_rolls_back():
    service = EncounterService()
    connection = Mock()
    service.repository = Mock()
    service.repository.write.side_effect = pyodbc.Error("42000", "Encounter conflict. (51402)")
    with pytest.raises(AppError) as caught:
        service.write(
            connection,
            actor(["encounters.read_assigned", "encounters.update_assigned"]),
            None,
            EncounterVersionRequest(version=VERSION),
            action="save",
            encounter_id=uuid4(),
        )
    assert caught.value.code == "ENCOUNTER_VERSION_CONFLICT"
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_clinical_audit_failure_rolls_back_snapshot_and_change():
    service = EncounterService()
    connection = Mock()
    service.repository = Mock()
    saved_id = uuid4()
    service.repository.write.return_value = saved_id
    service.get = Mock(
        return_value=Mock(
            patient_id=uuid4(), appointment_id=uuid4(), status="in_progress", version_no=2
        )
    )
    service.appointments.audit = Mock(side_effect=RuntimeError("audit failed"))
    with pytest.raises(RuntimeError, match="audit failed"):
        service.write(
            connection,
            actor(["encounters.read_assigned", "encounters.update_assigned"]),
            None,
            EncounterVersionRequest(version=VERSION),
            action="save",
            encounter_id=saved_id,
        )
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
