from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from BLL.appointment_service import AppointmentService, date_range
from Core.errors import AppError, PermissionDeniedError
from Model.appointments import AppointmentCreateRequest, ScheduleCreateRequest
from Model.auth import UserResponse


def actor(permissions):
    return UserResponse(
        user_id=uuid4(),
        username="test",
        email=None,
        phone=None,
        role="Patient",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        permissions=permissions,
    )


def test_appointment_role_scopes_require_action_permissions():
    patient = actor(["appointments.read_self", "appointments.create_self"])
    assert AppointmentService.read_scope(patient) == "self"
    assert AppointmentService.write_scope(patient, "create") == "self"
    with pytest.raises(PermissionDeniedError):
        AppointmentService.write_scope(patient, "update")
    doctor = actor(["appointments.read_assigned"])
    assert AppointmentService.read_scope(doctor) == "assigned"
    with pytest.raises(PermissionDeniedError):
        AppointmentService.write_scope(doctor, "cancel")


def test_date_filters_use_vietnam_calendar_day():
    bounds = date_range(date(2030, 1, 2), date(2030, 1, 2))
    assert bounds["start_at"] == datetime(2030, 1, 1, 17)
    assert bounds["end_at"] == datetime(2030, 1, 2, 17)
    with pytest.raises(AppError):
        date_range(date(2030, 1, 3), date(2030, 1, 2))


def test_booking_requires_offset_and_full_minutes():
    fields = {"doctor_id": uuid4(), "schedule_id": uuid4()}
    for value in ("2030-01-02T08:00:00", "2030-01-02T08:00:01+07:00"):
        with pytest.raises(ValidationError):
            AppointmentCreateRequest(**fields, appointment_at=value)
    request = AppointmentCreateRequest(**fields, appointment_at="2030-01-02T08:00:00+07:00")
    assert request.appointment_at.utcoffset().total_seconds() == 25200


def test_schedule_requires_complete_nonempty_slots():
    with pytest.raises(ValidationError):
        ScheduleCreateRequest(
            doctor_id=uuid4(),
            start_at="2030-01-02T08:00:00+07:00",
            end_at="2030-01-02T08:40:00+07:00",
            slot_minutes=30,
        )
