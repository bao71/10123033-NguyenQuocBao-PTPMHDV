from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from API.dependencies import get_current_user
from API.main import app
from DAL.db import get_db
from Model.auth import UserResponse
from Model.users import StaffCreateRequest


def test_staff_request_requires_doctor_profile_and_excludes_patient_registration() -> None:
    base = {
        "username": "staff_test",
        "email": "staff@example.com",
        "password": "Strong-Test!2026",
    }
    with pytest.raises(ValidationError):
        StaffCreateRequest(**base, role="Doctor")
    with pytest.raises(ValidationError):
        StaffCreateRequest(**base, role="Patient")
    doctor = StaffCreateRequest(**base, role="Doctor", doctor_code="DR101", specialty="Nội khoa")
    assert doctor.doctor_code == "DR101"


def test_administration_routes_reject_users_without_action_permissions() -> None:
    def no_database():
        yield object()

    app.dependency_overrides[get_db] = no_database
    try:
        with TestClient(app) as client:
            for role in ("Receptionist", "Doctor", "Pharmacist", "Patient"):
                app.dependency_overrides[get_current_user] = lambda role=role: UserResponse(
                    user_id=uuid4(),
                    username=f"test_{role.lower()}",
                    email=f"{role.lower()}@example.com",
                    phone=None,
                    role=role,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    permissions=[],
                )
                assert client.get("/api/v1/admin/users").status_code == 403
                assert client.get("/api/v1/admin/roles").status_code == 403
                assert (
                    client.post(
                        "/api/v1/admin/users",
                        json={
                            "username": "staff_test",
                            "email": "staff@example.com",
                            "password": "Strong-Test!2026",
                            "role": "Receptionist",
                        },
                    ).status_code
                    == 403
                )
                assert (
                    client.patch(
                        f"/api/v1/admin/users/{uuid4()}/status", json={"is_active": False}
                    ).status_code
                    == 403
                )
                assert (
                    client.put(
                        "/api/v1/admin/roles/Doctor/permissions", json={"permissions": []}
                    ).status_code
                    == 403
                )
    finally:
        app.dependency_overrides.clear()
