from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from API.main import app
from CLI.create_admin import create_admin
from DAL.db import connect


@pytest.mark.integration
def test_patient_crud_and_record_visibility_for_five_roles() -> None:
    suffix = uuid4().hex[:10]
    password = "Clinic-Test!2026"
    created_users: list[UUID] = []
    created_patients: list[UUID] = []

    with TestClient(app) as client:
        try:
            admin_name = f"admin_pat_{suffix}"
            admin_id = create_admin(admin_name, f"{admin_name}@example.com", password)
            created_users.append(admin_id)
            admin_token = client.post(
                "/api/v1/auth/login", data={"username": admin_name, "password": password}
            )
            assert admin_token.status_code == 200, admin_token.text
            admin_headers = {"Authorization": f"Bearer {admin_token.json()['access_token']}"}

            staff_headers = {}
            staff_ids = {}
            for role in ("Receptionist", "Doctor", "Pharmacist"):
                username = f"{role.lower()}_pat_{suffix}"
                body = {
                    "username": username,
                    "email": f"{username}@example.com",
                    "password": password,
                    "role": role,
                }
                if role == "Doctor":
                    body.update({"doctor_code": f"PAT{suffix}", "specialty": "Nội khoa"})
                response = client.post("/api/v1/admin/users", json=body, headers=admin_headers)
                assert response.status_code == 201, response.text
                staff_ids[role] = UUID(response.json()["user_id"])
                created_users.append(staff_ids[role])
                token = client.post(
                    "/api/v1/auth/login", data={"username": username, "password": password}
                )
                assert token.status_code == 200, token.text
                staff_headers[role] = {"Authorization": f"Bearer {token.json()['access_token']}"}

            patient_name = f"patient_pat_{suffix}"
            registered = client.post(
                "/api/v1/auth/register",
                json={
                    "username": patient_name,
                    "email": f"{patient_name}@example.com",
                    "password": password,
                    "full_name": "Bệnh nhân tự đăng ký",
                },
            )
            assert registered.status_code == 201, registered.text
            created_users.append(UUID(registered.json()["user"]["user_id"]))
            self_id = UUID(registered.json()["user"]["patient_id"])
            created_patients.append(self_id)
            patient_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

            assert client.get("/api/v1/patients", headers=admin_headers).status_code == 200
            assert (
                client.post(
                    "/api/v1/patients", json={"full_name": "Không được tạo"}, headers=admin_headers
                ).status_code
                == 403
            )
            assert (
                client.get("/api/v1/patients", headers=staff_headers["Pharmacist"]).status_code
                == 403
            )

            created = client.post(
                "/api/v1/patients",
                json={
                    "full_name": "Nguyễn Thị Lan",
                    "phone": "0901234567",
                    "gender": "female",
                    "date_of_birth": "1990-04-12",
                },
                headers=staff_headers["Receptionist"],
            )
            assert created.status_code == 201, created.text
            item = created.json()
            patient_id = UUID(item["patient_id"])
            created_patients.append(patient_id)
            assert item["patient_code"].startswith("BN")
            assert not item["has_account"]
            assert len(item["version"]) == 16

            listing = client.get(
                "/api/v1/patients",
                params={
                    "search": item["patient_code"],
                    "gender": "female",
                    "has_account": False,
                    "sort_by": "full_name",
                    "sort_order": "asc",
                    "page": 1,
                    "page_size": 1,
                },
                headers=staff_headers["Receptionist"],
            )
            assert listing.status_code == 200, listing.text
            assert listing.json()["total"] == 1
            assert listing.json()["items"][0]["patient_id"] == str(patient_id)
            assert (
                client.get(
                    "/api/v1/patients",
                    params={"sort_by": "DROP TABLE patients"},
                    headers=staff_headers["Receptionist"],
                ).status_code
                == 422
            )
            assert (
                client.get(f"/api/v1/patients/{patient_id}", headers=patient_headers).status_code
                == 404
            )
            self_list = client.get("/api/v1/patients", headers=patient_headers)
            assert self_list.status_code == 200, self_list.text
            assert self_list.json()["total"] == 1
            assert self_list.json()["items"][0]["patient_id"] == str(self_id)
            assert (
                client.get(f"/api/v1/patients/{self_id}", headers=patient_headers).status_code
                == 200
            )
            doctor_list = client.get(
                "/api/v1/patients",
                params={"search": item["patient_code"]},
                headers=staff_headers["Doctor"],
            )
            assert doctor_list.status_code == 200, doctor_list.text
            assert doctor_list.json()["total"] == 0
            assert (
                client.get(
                    f"/api/v1/patients/{patient_id}", headers=staff_headers["Doctor"]
                ).status_code
                == 404
            )

            updated = client.put(
                f"/api/v1/patients/{patient_id}",
                json={
                    "full_name": "Nguyễn Thị Lan Anh",
                    "phone": "0901234567",
                    "gender": "female",
                    "date_of_birth": "1990-04-12",
                    "version": item["version"],
                },
                headers=staff_headers["Receptionist"],
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["version"] != item["version"]
            assert (
                client.put(
                    f"/api/v1/patients/{patient_id}",
                    json={"full_name": "Ghi đè", "version": item["version"]},
                    headers=staff_headers["Receptionist"],
                ).status_code
                == 409
            )

            connection = connect()
            try:
                doctor_id = (
                    connection.execute(
                        "SELECT doctor_id FROM dbo.doctors WHERE user_id=?",
                        str(staff_ids["Doctor"]),
                    )
                    .fetchone()
                    .doctor_id
                )
                connection.execute(
                    """
                    INSERT INTO dbo.appointments(patient_id, doctor_id, created_by, appointment_at)
                    VALUES(?, ?, ?, DATEADD(DAY, 1, SYSUTCDATETIME()))
                    """,
                    str(patient_id),
                    str(doctor_id),
                    str(staff_ids["Receptionist"]),
                )
                connection.commit()
            finally:
                connection.close()
            assert (
                client.get(
                    f"/api/v1/patients/{patient_id}", headers=staff_headers["Doctor"]
                ).status_code
                == 200
            )
            doctor_list = client.get(
                "/api/v1/patients",
                params={"search": item["patient_code"]},
                headers=staff_headers["Doctor"],
            )
            assert doctor_list.status_code == 200, doctor_list.text
            assert doctor_list.json()["total"] == 1
            assert (
                client.delete(
                    f"/api/v1/patients/{patient_id}",
                    params={"version": updated.json()["version"]},
                    headers=staff_headers["Receptionist"],
                ).status_code
                == 409
            )

            connection = connect()
            try:
                connection.execute(
                    "UPDATE dbo.appointments SET status='cancelled', "
                    "cancellation_reason=N'Integration test', updated_at=SYSUTCDATETIME() "
                    "WHERE patient_id=?",
                    str(patient_id),
                )
                connection.commit()
            finally:
                connection.close()
            deleted = client.delete(
                f"/api/v1/patients/{patient_id}",
                params={"version": updated.json()["version"]},
                headers=staff_headers["Receptionist"],
            )
            assert deleted.status_code == 204, deleted.text
            assert (
                client.get(f"/api/v1/patients/{patient_id}", headers=admin_headers).status_code
                == 404
            )

            own = client.get(f"/api/v1/patients/{self_id}", headers=staff_headers["Receptionist"])
            assert own.status_code == 200, own.text
            removed_account = client.delete(
                f"/api/v1/patients/{self_id}",
                params={"version": own.json()["version"]},
                headers=staff_headers["Receptionist"],
            )
            assert removed_account.status_code == 204, removed_account.text
            assert client.get("/api/v1/auth/me", headers=patient_headers).status_code == 401
        finally:
            connection = connect()
            try:
                for patient_id in created_patients:
                    connection.execute(
                        "UPDATE dbo.appointments "
                        "SET deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE patient_id=?",
                        str(patient_id),
                    )
                    connection.execute(
                        "UPDATE dbo.patients SET deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE patient_id=?",
                        str(patient_id),
                    )
                for user_id in created_users:
                    connection.execute(
                        "UPDATE dbo.refresh_tokens "
                        "SET revoked_at=COALESCE(revoked_at,SYSUTCDATETIME()) "
                        "WHERE user_id=?",
                        str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.doctors SET deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE user_id=?",
                        str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.users SET is_active=0, "
                        "deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE user_id=?",
                        str(user_id),
                    )
                connection.commit()
            finally:
                connection.close()
