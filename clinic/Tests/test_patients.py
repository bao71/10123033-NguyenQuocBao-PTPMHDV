from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from API.dependencies import get_current_user
from API.main import app
from DAL.db import get_db
from Model.auth import UserResponse
from Model.patients import PatientCreateRequest, PatientUpdateRequest


def test_patient_inputs_reject_invalid_demographics_and_stale_version_shape() -> None:
    with pytest.raises(ValidationError):
        PatientCreateRequest(full_name="A", date_of_birth=date.today())
    with pytest.raises(ValidationError):
        PatientCreateRequest(full_name="Nguyễn An", gender="invalid")
    with pytest.raises(ValidationError):
        PatientUpdateRequest(full_name="Nguyễn An", version="not-a-row-version")


def test_patient_routes_require_patient_permissions() -> None:
    def no_database():
        yield object()

    app.dependency_overrides[get_db] = no_database
    app.dependency_overrides[get_current_user] = lambda: UserResponse(
        user_id=uuid4(),
        username="pharmacist_test",
        email="pharmacist@example.com",
        phone=None,
        role="Pharmacist",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        permissions=["drugs.read"],
    )
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/patients").status_code == 403
            assert client.get(f"/api/v1/patients/{uuid4()}").status_code == 403
            assert (
                client.post("/api/v1/patients", json={"full_name": "Nguyễn An"}).status_code == 403
            )
            assert (
                client.put(
                    f"/api/v1/patients/{uuid4()}",
                    json={"full_name": "Nguyễn An", "version": "0000000000000001"},
                ).status_code
                == 403
            )
            assert (
                client.delete(f"/api/v1/patients/{uuid4()}?version=0000000000000001").status_code
                == 403
            )
    finally:
        app.dependency_overrides.clear()
