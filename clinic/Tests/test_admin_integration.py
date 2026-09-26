from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from API.main import app
from CLI.create_admin import create_admin
from DAL.db import connect


@pytest.mark.integration
def test_five_roles_screen_and_action_permissions() -> None:
    suffix = uuid4().hex[:10]
    password = "Clinic-Test!2026"
    created: list[UUID] = []
    original_pharmacist_permissions: list[str] | None = None
    admin_headers: dict[str, str] = {}

    with TestClient(app) as client:
        try:
            assert client.get("/app/").status_code == 200
            assert client.get("/app/assets/app.js").status_code == 200
            admin_name = f"admin_rbac_{suffix}"
            admin_id = create_admin(admin_name, f"{admin_name}@example.com", password)
            created.append(admin_id)
            admin_login = client.post(
                "/api/v1/auth/login", data={"username": admin_name, "password": password}
            )
            assert admin_login.status_code == 200, admin_login.text
            admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

            roles_response = client.get("/api/v1/admin/roles", headers=admin_headers)
            assert roles_response.status_code == 200, roles_response.text
            roles = {role["code"]: role for role in roles_response.json()["roles"]}
            assert set(roles) == {"Admin", "Receptionist", "Doctor", "Pharmacist", "Patient"}
            original_pharmacist_permissions = roles["Pharmacist"]["permissions"]

            staff_tokens: dict[str, dict] = {}
            for role in ("Receptionist", "Doctor", "Pharmacist"):
                username = f"{role.lower()}_{suffix}"
                payload = {
                    "username": username,
                    "email": f"{username}@example.com",
                    "password": password,
                    "role": role,
                }
                if role == "Doctor":
                    payload.update({"doctor_code": f"DR{suffix}", "specialty": "Nội khoa"})
                created_response = client.post(
                    "/api/v1/admin/users", json=payload, headers=admin_headers
                )
                assert created_response.status_code == 201, created_response.text
                assert created_response.json()["role"] == role
                created.append(UUID(created_response.json()["user_id"]))
                logged_in = client.post(
                    "/api/v1/auth/login", data={"username": username, "password": password}
                )
                assert logged_in.status_code == 200, logged_in.text
                staff_tokens[role] = logged_in.json()
                headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
                assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
                assert client.get("/api/v1/admin/roles", headers=headers).status_code == 403
                assert (
                    client.post("/api/v1/admin/users", json=payload, headers=headers).status_code
                    == 403
                )

            patient_name = f"patient_rbac_{suffix}"
            registered = client.post(
                "/api/v1/auth/register",
                json={
                    "username": patient_name,
                    "email": f"{patient_name}@example.com",
                    "password": password,
                    "full_name": "Bệnh nhân phân quyền",
                },
            )
            assert registered.status_code == 201, registered.text
            created.append(UUID(registered.json()["user"]["user_id"]))
            patient_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
            assert client.get("/api/v1/admin/roles", headers=patient_headers).status_code == 403

            connection = connect()
            try:
                doctor = connection.execute(
                    "SELECT doctor_code, specialty FROM dbo.doctors WHERE user_id=?",
                    str(created[2]),
                ).fetchone()
                assert doctor is not None
                assert doctor.doctor_code == f"DR{suffix}"
            finally:
                connection.close()

            pharmacist_headers = {
                "Authorization": f"Bearer {staff_tokens['Pharmacist']['access_token']}"
            }
            granted = client.put(
                "/api/v1/admin/roles/Pharmacist/permissions",
                json={"permissions": original_pharmacist_permissions + ["users.read"]},
                headers=admin_headers,
            )
            assert granted.status_code == 200, granted.text
            assert client.get("/api/v1/admin/users", headers=pharmacist_headers).status_code == 200

            invalid_admin = client.put(
                "/api/v1/admin/roles/Admin/permissions",
                json={"permissions": []},
                headers=admin_headers,
            )
            assert invalid_admin.status_code == 422

            receptionist_id = created[1]
            receptionist_headers = {
                "Authorization": f"Bearer {staff_tokens['Receptionist']['access_token']}"
            }
            deactivated = client.patch(
                f"/api/v1/admin/users/{receptionist_id}/status",
                json={"is_active": False},
                headers=admin_headers,
            )
            assert deactivated.status_code == 200, deactivated.text
            assert client.get("/api/v1/auth/me", headers=receptionist_headers).status_code == 401
            assert (
                client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": staff_tokens["Receptionist"]["refresh_token"]},
                ).status_code
                == 401
            )
            reactivated = client.patch(
                f"/api/v1/admin/users/{receptionist_id}/status",
                json={"is_active": True},
                headers=admin_headers,
            )
            assert reactivated.status_code == 200, reactivated.text
            assert client.get("/api/v1/auth/me", headers=receptionist_headers).status_code == 401
            assert (
                client.post(
                    "/api/v1/auth/login",
                    data={"username": f"receptionist_{suffix}", "password": password},
                ).status_code
                == 200
            )
            assert (
                client.patch(
                    f"/api/v1/admin/users/{admin_id}/status",
                    json={"is_active": False},
                    headers=admin_headers,
                ).status_code
                == 400
            )
        finally:
            if original_pharmacist_permissions is not None and admin_headers:
                restored = client.put(
                    "/api/v1/admin/roles/Pharmacist/permissions",
                    json={"permissions": original_pharmacist_permissions},
                    headers=admin_headers,
                )
                assert restored.status_code == 200, restored.text
            connection = connect()
            try:
                for user_id in created:
                    connection.execute(
                        "UPDATE dbo.refresh_tokens "
                        "SET revoked_at=COALESCE(revoked_at,SYSUTCDATETIME()) WHERE user_id=?",
                        str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.doctors SET deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE user_id=?",
                        str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.patients SET deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE user_id=?",
                        str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.users SET is_active=0, "
                        "deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) WHERE user_id=?",
                        str(user_id),
                    )
                connection.commit()
            finally:
                connection.close()
