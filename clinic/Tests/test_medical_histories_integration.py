from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from API.main import app
from CLI.create_admin import create_admin
from DAL.db import connect


@pytest.mark.integration
def test_medical_history_visibility_versioning_and_soft_delete() -> None:
    suffix = uuid4().hex[:10]
    password = "Clinic-Test!2026"
    users: list[UUID] = []
    patient_id: UUID | None = None
    history_id: UUID | None = None

    with TestClient(app) as client:
        try:
            admin_name = f"admin_hist_{suffix}"
            users.append(create_admin(admin_name, f"{admin_name}@example.com", password))
            admin_login = client.post(
                "/api/v1/auth/login", data={"username": admin_name, "password": password}
            )
            assert admin_login.status_code == 200, admin_login.text
            admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

            staff_headers = {}
            staff_ids = {}
            for role, label in (("Doctor", "doctor1"), ("Doctor", "doctor2"),
                                ("Receptionist", "receptionist")):
                username = f"{label}_hist_{suffix}"
                payload = {
                    "username": username,
                    "email": f"{username}@example.com",
                    "password": password,
                    "role": role,
                }
                if role == "Doctor":
                    payload.update({
                        "doctor_code": f"H{label[-1]}{suffix}",
                        "specialty": "Nội khoa",
                    })
                created = client.post("/api/v1/admin/users", json=payload, headers=admin_headers)
                assert created.status_code == 201, created.text
                staff_ids[label] = UUID(created.json()["user_id"])
                users.append(staff_ids[label])
                login = client.post(
                    "/api/v1/auth/login", data={"username": username, "password": password}
                )
                assert login.status_code == 200, login.text
                staff_headers[label] = {"Authorization": f"Bearer {login.json()['access_token']}"}

            patient_name = f"patient_hist_{suffix}"
            registered = client.post("/api/v1/auth/register", json={
                "username": patient_name,
                "email": f"{patient_name}@example.com",
                "password": password,
                "full_name": "Bệnh nhân kiểm thử tiền sử",
            })
            assert registered.status_code == 201, registered.text
            users.append(UUID(registered.json()["user"]["user_id"]))
            patient_id = UUID(registered.json()["user"]["patient_id"])
            patient_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
            path = f"/api/v1/patients/{patient_id}/medical-histories"

            assert client.get(path, headers=patient_headers).json()["total"] == 0
            assert client.get(path, headers=staff_headers["doctor1"]).status_code == 404
            assert client.get(path, headers=staff_headers["receptionist"]).status_code == 403
            assert client.get(path, headers=admin_headers).status_code == 403
            assert client.post(path, json={"type": "allergy", "name": "Penicillin"},
                               headers=patient_headers).status_code == 403

            connection = connect()
            try:
                doctor_id = connection.execute(
                    "SELECT doctor_id FROM dbo.doctors WHERE user_id=?",
                    str(staff_ids["doctor1"]),
                ).fetchone().doctor_id
                connection.execute(
                    "INSERT dbo.appointments(patient_id, doctor_id, created_by, appointment_at) "
                    "VALUES(?, ?, ?, DATEADD(DAY, 1, SYSUTCDATETIME()))",
                    str(patient_id), str(doctor_id), str(staff_ids["receptionist"]),
                )
                connection.commit()
            finally:
                connection.close()

            assert client.get(path, headers=staff_headers["doctor1"]).status_code == 200
            assert client.get(path, headers=staff_headers["doctor2"]).status_code == 404
            assert client.post(path, json={"type": "invalid", "name": "Test"},
                               headers=staff_headers["doctor1"]).status_code == 422
            assert client.post(path, json={
                "type": "allergy", "name": "Penicillin",
                "onset_date": (date.today() + timedelta(days=1)).isoformat(),
            }, headers=staff_headers["doctor1"]).status_code == 422

            created = client.post(path, json={
                "type": "allergy", "name": "Penicillin",
                "description": "Phát ban sau khi dùng thuốc", "is_active": True,
            }, headers=staff_headers["doctor1"])
            assert created.status_code == 201, created.text
            item = created.json()
            history_id = UUID(item["history_id"])
            assert item["version_no"] == 1
            assert len(item["version"]) == 16
            detail = f"{path}/{history_id}"

            listed = client.get(path, params={
                "type": "allergy", "is_active": True, "search": "Penic",
                "page": 1, "page_size": 1, "sort_by": "name", "sort_order": "asc",
            }, headers=patient_headers)
            assert listed.status_code == 200, listed.text
            assert listed.json()["total"] == 1
            assert listed.json()["items"][0]["history_id"] == str(history_id)
            assert client.get(detail, headers=patient_headers).status_code == 200
            assert client.get(detail, headers=staff_headers["doctor2"]).status_code == 404

            update = {
                "type": "allergy", "name": "Penicillin",
                "description": "Dị ứng đã xác nhận", "is_active": False,
                "version": "0000000000000000",
            }
            assert client.put(detail, json=update,
                              headers=staff_headers["doctor1"]).status_code == 409
            update["version"] = item["version"]
            changed = client.put(detail, json=update, headers=staff_headers["doctor1"])
            assert changed.status_code == 200, changed.text
            assert changed.json()["version_no"] == 2
            assert changed.json()["version"] != item["version"]
            assert changed.json()["is_active"] is False
            assert client.delete(detail, params={"version": item["version"]},
                                 headers=staff_headers["doctor1"]).status_code == 409
            assert client.delete(detail, params={"version": changed.json()["version"]},
                                 headers=patient_headers).status_code == 403
            deleted = client.delete(
                detail, params={"version": changed.json()["version"]},
                headers=staff_headers["doctor1"],
            )
            assert deleted.status_code == 204, deleted.text
            assert client.get(detail, headers=patient_headers).status_code == 404
            assert client.get(path, headers=patient_headers).json()["total"] == 0

            connection = connect()
            try:
                audit_count = connection.execute(
                    "SELECT COUNT(*) FROM dbo.audit_logs WHERE entity_type='medical_histories' "
                    "AND entity_id=?", str(history_id),
                ).fetchone()[0]
                assert audit_count == 3
            finally:
                connection.close()
        finally:
            connection = connect()
            try:
                if history_id is not None:
                    connection.execute(
                        "UPDATE dbo.medical_histories SET "
                        "deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE history_id=?", str(history_id),
                    )
                if patient_id is not None:
                    connection.execute(
                        "UPDATE dbo.appointments SET "
                        "deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE patient_id=?", str(patient_id),
                    )
                    connection.execute(
                        "UPDATE dbo.patients SET deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE patient_id=?", str(patient_id),
                    )
                for user_id in users:
                    connection.execute(
                        "UPDATE dbo.refresh_tokens SET "
                        "revoked_at=COALESCE(revoked_at,SYSUTCDATETIME()) "
                        "WHERE user_id=?", str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.doctors SET deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) "
                        "WHERE user_id=?", str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.users SET is_active=0, "
                        "deleted_at=COALESCE(deleted_at,SYSUTCDATETIME()) WHERE user_id=?",
                        str(user_id),
                    )
                connection.commit()
            finally:
                connection.close()
