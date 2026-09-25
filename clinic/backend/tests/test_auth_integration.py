from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.cli.create_admin import create_admin
from app.db import connect
from app.main import app


def _soft_delete_test_users(user_ids: list[UUID]) -> None:
    if not user_ids:
        return
    connection = connect()
    try:
        for user_id in user_ids:
            connection.execute(
                "UPDATE dbo.refresh_tokens SET revoked_at=COALESCE(revoked_at,SYSUTCDATETIME()) "
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


def _create_admin(username: str, email: str, password: str) -> UUID:
    return create_admin(username, email, password)


@pytest.mark.integration
def test_authentication_refresh_logout_and_rbac() -> None:
    suffix = uuid4().hex[:12]
    patient_username = f"patient_{suffix}"
    patient_email = f"{patient_username}@example.com"
    patient_password = "Patient-Test!2026"
    admin_username = f"admin_{suffix}"
    admin_email = f"{admin_username}@example.com"
    admin_password = "Admin-Test!2026"
    created_users: list[UUID] = []

    with TestClient(app) as client:
        try:
            assert client.get("/health/live").status_code == 200
            assert client.get("/health/ready").status_code == 200

            registered = client.post(
                "/api/v1/auth/register",
                json={
                    "username": patient_username,
                    "email": patient_email,
                    "password": patient_password,
                    "full_name": "Bệnh nhân kiểm thử",
                    "phone": "+84912345678",
                    "date_of_birth": "2000-01-02",
                    "gender": "other",
                },
            )
            assert registered.status_code == 201, registered.text
            patient_user_id = UUID(registered.json()["user"]["user_id"])
            created_users.append(patient_user_id)
            assert registered.json()["user"]["role"] == "Patient"
            assert "appointments.create_self" in registered.json()["user"]["permissions"]

            bad_login = client.post(
                "/api/v1/auth/login",
                data={"username": patient_username, "password": "incorrect-password"},
            )
            assert bad_login.status_code == 401

            logged_in = client.post(
                "/api/v1/auth/login",
                data={"username": patient_username, "password": patient_password},
            )
            assert logged_in.status_code == 200, logged_in.text
            patient_tokens = logged_in.json()
            patient_headers = {"Authorization": f"Bearer {patient_tokens['access_token']}"}

            me = client.get("/api/v1/auth/me", headers=patient_headers)
            assert me.status_code == 200
            assert me.json()["username"] == patient_username

            forbidden = client.get("/api/v1/admin/users", headers=patient_headers)
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["details"]["missing_permissions"] == ["users.read"]

            refreshed = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": patient_tokens["refresh_token"]},
            )
            assert refreshed.status_code == 200, refreshed.text
            assert refreshed.json()["refresh_token"] != patient_tokens["refresh_token"]

            reused = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": patient_tokens["refresh_token"]},
            )
            assert reused.status_code == 401

            admin_user_id = _create_admin(admin_username, admin_email, admin_password)
            created_users.append(admin_user_id)
            admin_login = client.post(
                "/api/v1/auth/login",
                data={"username": admin_username, "password": admin_password},
            )
            assert admin_login.status_code == 200, admin_login.text
            admin_headers = {
                "Authorization": f"Bearer {admin_login.json()['access_token']}"
            }
            user_list = client.get(
                "/api/v1/admin/users?page=1&page_size=10&search=admin_",
                headers=admin_headers,
            )
            assert user_list.status_code == 200, user_list.text
            assert user_list.json()["total"] >= 1

            logout = client.post(
                "/api/v1/auth/logout",
                headers={
                    "Authorization": f"Bearer {refreshed.json()['access_token']}"
                },
                json={"refresh_token": refreshed.json()["refresh_token"]},
            )
            assert logout.status_code == 200
            after_logout = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refreshed.json()["refresh_token"]},
            )
            assert after_logout.status_code == 401
        finally:
            _soft_delete_test_users(created_users)
