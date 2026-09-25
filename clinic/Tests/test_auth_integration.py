import json
import re
from email import policy
from email.parser import Parser
from urllib.request import urlopen
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from API.main import app
from CLI.create_admin import create_admin
from DAL.db import connect


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


def _mail_body(message: dict) -> str:
    return Parser(policy=policy.default).parsestr(message["Raw"]["Data"]).get_content()


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


@pytest.mark.integration
def test_password_reset_email_expiry_reuse_and_session_revocation() -> None:
    suffix = uuid4().hex[:12]
    username = f"reset_{suffix}"
    email = f"{username}@example.com"
    old_password = "Old-Password!2026"
    new_password = "New-Password!2026"
    created_users: list[UUID] = []

    with TestClient(app) as client:
        try:
            registered = client.post(
                "/api/v1/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": old_password,
                    "full_name": "Bệnh nhân đặt lại mật khẩu",
                },
            )
            assert registered.status_code == 201, registered.text
            created_users.append(UUID(registered.json()["user"]["user_id"]))
            old_tokens = registered.json()

            missing = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": f"missing_{suffix}@example.com"},
            )
            requested = client.post(
                "/api/v1/auth/forgot-password", json={"email": email}
            )
            assert missing.status_code == requested.status_code == 200
            assert missing.json() == requested.json()
            with urlopen("http://mailhog:8025/api/v2/messages", timeout=5) as response:
                messages = json.load(response)["items"]
            matching = [
                item for item in messages
                if email in item["Content"]["Headers"].get("To", [])
            ]
            assert len(matching) == 1
            body = _mail_body(matching[0])
            token = re.search(
                r"Mã đặt lại: ([A-Za-z0-9_-]+)", body
            ).group(1)

            invalid = client.post(
                "/api/v1/auth/reset-password",
                json={"token": "x" * 64, "new_password": new_password},
            )
            assert invalid.status_code == 400

            connection = connect()
            try:
                connection.execute(
                    "UPDATE dbo.password_reset_tokens SET "
                    "created_at = DATEADD(HOUR, -1, SYSUTCDATETIME()), expires_at = "
                    "DATEADD(SECOND, -1, SYSUTCDATETIME()) "
                    "WHERE user_id = ? AND used_at IS NULL",
                    str(created_users[0]),
                )
                connection.commit()
            finally:
                connection.close()
            expired = client.post(
                "/api/v1/auth/reset-password",
                json={"token": token, "new_password": new_password},
            )
            assert expired.status_code == 400

            requested_again = client.post(
                "/api/v1/auth/forgot-password", json={"email": email}
            )
            assert requested_again.status_code == 200
            with urlopen("http://mailhog:8025/api/v2/messages", timeout=5) as response:
                messages = json.load(response)["items"]
            matching = [
                item for item in messages
                if email in item["Content"]["Headers"].get("To", [])
            ]
            assert len(matching) == 2
            body = _mail_body(matching[0])
            fresh_token = re.search(
                r"Mã đặt lại: ([A-Za-z0-9_-]+)", body
            ).group(1)
            assert fresh_token != token

            reset = client.post(
                "/api/v1/auth/reset-password",
                json={"token": fresh_token, "new_password": new_password},
            )
            assert reset.status_code == 200, reset.text
            reused = client.post(
                "/api/v1/auth/reset-password",
                json={"token": fresh_token, "new_password": new_password},
            )
            assert reused.status_code == 400

            old_access = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {old_tokens['access_token']}"},
            )
            assert old_access.status_code == 401
            old_refresh = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": old_tokens["refresh_token"]},
            )
            assert old_refresh.status_code == 401
            old_login = client.post(
                "/api/v1/auth/login",
                data={"username": username, "password": old_password},
            )
            assert old_login.status_code == 401
            new_login = client.post(
                "/api/v1/auth/login",
                data={"username": username, "password": new_password},
            )
            assert new_login.status_code == 200, new_login.text
        finally:
            _soft_delete_test_users(created_users)
