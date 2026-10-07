from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from API.main import app
from CLI.create_admin import create_admin
from DAL.db import connect

pytestmark = pytest.mark.integration
LOCAL_ZONE = timezone(timedelta(hours=7))


@pytest.fixture(scope="module")
def clinic_booking():
    suffix = uuid4().hex[:10]
    password = "Clinic-Test!2026"
    users, patients, doctors = [], [], []
    env = {"headers": {}, "doctors": [], "patients": [], "suffix": suffix}
    # Give this suite a separate source IP so fixture logins do not consume the
    # other API suites' rate-limit quota. The application's limiter stays enabled.
    with TestClient(app, client=("127.0.0.2", 50000)) as client:
        env["client"] = client
        try:
            admin_name = f"admin_apt_{suffix}"
            users.append(create_admin(admin_name, f"{admin_name}@example.com", password))
            login = client.post(
                "/api/v1/auth/login",
                data={
                    "username": admin_name,
                    "password": password,
                },
            )
            assert login.status_code == 200, login.text
            env["headers"]["Admin"] = {"Authorization": f"Bearer {login.json()['access_token']}"}
            for role, label in (
                ("Receptionist", "Receptionist"),
                ("Doctor", "Doctor1"),
                ("Doctor", "Doctor2"),
                ("Pharmacist", "Pharmacist"),
            ):
                username = f"{label.lower()}_apt_{suffix}"
                payload = {
                    "username": username,
                    "email": f"{username}@example.com",
                    "password": password,
                    "role": role,
                }
                if role == "Doctor":
                    payload.update(
                        {"doctor_code": f"APT{label[-1]}{suffix}", "specialty": "Nội khoa"}
                    )
                created = client.post(
                    "/api/v1/admin/users", json=payload, headers=env["headers"]["Admin"]
                )
                assert created.status_code == 201, created.text
                users.append(UUID(created.json()["user_id"]))
                login = client.post(
                    "/api/v1/auth/login",
                    data={
                        "username": username,
                        "password": password,
                    },
                )
                assert login.status_code == 200, login.text
                env["headers"][label] = {"Authorization": f"Bearer {login.json()['access_token']}"}
                if role == "Doctor":
                    connection = connect()
                    try:
                        doctor_id = (
                            connection.execute(
                                "SELECT doctor_id FROM dbo.doctors WHERE user_id=?",
                                str(users[-1]),
                            )
                            .fetchone()
                            .doctor_id
                        )
                        doctors.append(UUID(str(doctor_id)))
                        env["doctors"].append(str(doctor_id))
                    finally:
                        connection.close()
            for i in range(2):
                username = f"patient{i}_apt_{suffix}"
                registered = client.post(
                    "/api/v1/auth/register",
                    json={
                        "username": username,
                        "email": f"{username}@example.com",
                        "password": password,
                        "full_name": f"Bệnh nhân lịch hẹn {i} {suffix}",
                    },
                )
                assert registered.status_code == 201, registered.text
                users.append(UUID(registered.json()["user"]["user_id"]))
                patients.append(UUID(registered.json()["user"]["patient_id"]))
                env["patients"].append(str(patients[-1]))
                env["headers"][f"Patient{i}"] = {
                    "Authorization": f"Bearer {registered.json()['access_token']}"
                }
            yield env
        finally:
            connection = connect()
            try:
                for patient_id in patients:
                    connection.execute(
                        "UPDATE dbo.appointments SET deleted_at=SYSUTCDATETIME() "
                        "WHERE patient_id=?",
                        str(patient_id),
                    )
                    connection.execute(
                        "UPDATE dbo.patients SET deleted_at=SYSUTCDATETIME() WHERE patient_id=?",
                        str(patient_id),
                    )
                for doctor_id in doctors:
                    connection.execute(
                        "UPDATE dbo.doctor_schedules SET status='cancelled' WHERE doctor_id=?",
                        str(doctor_id),
                    )
                for user_id in users:
                    connection.execute(
                        "UPDATE dbo.refresh_tokens SET revoked_at=SYSUTCDATETIME() WHERE user_id=?",
                        str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.doctors SET deleted_at=SYSUTCDATETIME() WHERE user_id=?",
                        str(user_id),
                    )
                    connection.execute(
                        "UPDATE dbo.users SET is_active=0,deleted_at=SYSUTCDATETIME() "
                        "WHERE user_id=?",
                        str(user_id),
                    )
                connection.commit()
            finally:
                connection.close()


def time_at(days, hour=8, minute=0):
    value = datetime.now(LOCAL_ZONE) + timedelta(days=days)
    return value.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()


def shift(env, days, doctor=0, hour=8, minute=0, duration=30):
    start = datetime.fromisoformat(time_at(days, hour, minute))
    response = env["client"].post(
        "/api/v1/doctor-schedules",
        json={
            "doctor_id": env["doctors"][doctor],
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=3)).isoformat(),
            "slot_minutes": duration,
        },
        headers=env["headers"]["Receptionist"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def booking(schedule, days, hour=8, minute=0, patient_id=None):
    payload = {
        "doctor_id": schedule["doctor_id"],
        "schedule_id": schedule["schedule_id"],
        "appointment_at": time_at(days, hour, minute),
        "reason": "Khám định kỳ",
    }
    if patient_id:
        payload["patient_id"] = patient_id
    return payload


def test_booking_roles_slots_changes_cancellation_and_audit(clinic_booking):
    env = clinic_booking
    client, headers = env["client"], env["headers"]
    schedule = shift(env, 2)
    second = shift(env, 2, doctor=1, minute=15, duration=45)
    payload = booking(schedule, 2)
    date = payload["appointment_at"][:10]
    assert client.get("/api/v1/doctors", headers=headers["Patient0"]).status_code == 200
    assert client.get("/api/v1/doctors", headers=headers["Pharmacist"]).status_code == 403
    denied = {
        "doctor_id": schedule["doctor_id"],
        "start_at": time_at(3),
        "end_at": time_at(3, 11),
        "slot_minutes": 30,
    }
    for role in ("Patient0", "Doctor1"):
        assert (
            client.post("/api/v1/doctor-schedules", json=denied, headers=headers[role]).status_code
            == 403
        )
    assert (
        client.post(
            "/api/v1/doctor-schedules",
            json={
                **denied,
                "start_at": time_at(2),
                "end_at": time_at(2, 11),
            },
            headers=headers["Receptionist"],
        ).status_code
        == 409
    )
    slots_path = f"/api/v1/doctors/{schedule['doctor_id']}/slots"
    slots = client.get(slots_path, params={"work_date": date}, headers=headers["Patient0"])
    assert slots.status_code == 200, slots.text
    assert len(slots.json()["items"]) == 6
    assert all(slot["available"] for slot in slots.json()["items"])
    assert slots.json()["items"][0]["appointment_at"] == time_at(2, 1)[:-6] + "Z"
    assert (
        client.post(
            "/api/v1/appointments",
            json={
                **payload,
                "appointment_at": payload["appointment_at"][:19],
            },
            headers=headers["Patient0"],
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/appointments",
            json={
                **payload,
                "patient_id": env["patients"][1],
            },
            headers=headers["Patient0"],
        ).status_code
        == 404
    )
    for role in ("Admin", "Doctor1", "Pharmacist"):
        assert (
            client.post("/api/v1/appointments", json=payload, headers=headers[role]).status_code
            == 403
        )
    assert (
        client.post(
            "/api/v1/appointments",
            json={
                **payload,
                "appointment_at": time_at(-1),
            },
            headers=headers["Patient0"],
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/appointments",
            json={
                **payload,
                "appointment_at": time_at(2, 8, 15),
            },
            headers=headers["Patient0"],
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/appointments",
            json={
                **payload,
                "appointment_at": time_at(2, 11),
            },
            headers=headers["Patient0"],
        ).status_code
        == 409
    )
    created = client.post("/api/v1/appointments", json=payload, headers=headers["Patient0"])
    assert created.status_code == 201, created.text
    item = created.json()
    path = f"/api/v1/appointments/{item['appointment_id']}"
    assert item["patient_id"] == env["patients"][0]
    assert item["duration_minutes"] == 30
    assert (
        client.post("/api/v1/appointments", json=payload, headers=headers["Patient1"]).json()[
            "error"
        ]["code"]
        == "DOCTOR_TIME_CONFLICT"
    )
    overlap = client.post(
        "/api/v1/appointments", json=booking(second, 2, minute=15), headers=headers["Patient0"]
    )
    assert overlap.status_code == 409, overlap.text
    assert overlap.json()["error"]["code"] == "PATIENT_TIME_CONFLICT"
    adjacent = client.post(
        "/api/v1/appointments",
        json=booking(
            schedule,
            2,
            minute=30,
            patient_id=env["patients"][1],
        ),
        headers=headers["Receptionist"],
    )
    assert adjacent.status_code == 201, adjacent.text
    params = {
        "date_from": date,
        "date_to": date,
        "doctor_id": schedule["doctor_id"],
        "status": "booked",
        "page_size": 1,
        "sort_by": "appointment_at",
    }
    listing = client.get("/api/v1/appointments", params=params, headers=headers["Receptionist"])
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 2
    assert len(listing.json()["items"]) == 1
    assert (
        client.get("/api/v1/appointments", params=params, headers=headers["Patient0"]).json()[
            "total"
        ]
        == 1
    )
    assert (
        client.get("/api/v1/appointments", params=params, headers=headers["Doctor1"]).json()[
            "total"
        ]
        == 2
    )
    for role in ("Patient1", "Doctor2"):
        assert client.get(path, headers=headers[role]).status_code == 404
    assert client.get(path, headers=headers["Admin"]).status_code == 200
    assert client.get(path, headers=headers["Pharmacist"]).status_code == 403
    assert (
        client.get(f"/api/v1/patients/{item['patient_id']}", headers=headers["Doctor1"]).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/appointments",
            params={"date_from": date, "date_to": "2020-01-01"},
            headers=headers["Patient0"],
        ).status_code
        == 422
    )
    change = {**booking(schedule, 2, hour=9), "version": item["version"]}
    updated = client.put(path, json=change, headers=headers["Patient0"])
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] != item["version"]
    assert client.put(path, json=change, headers=headers["Patient0"]).status_code == 409
    conflict = client.put(
        path,
        json={**booking(schedule, 2, minute=30), "version": updated.json()["version"]},
        headers=headers["Patient0"],
    )
    assert conflict.status_code == 409
    assert (
        client.get(path, headers=headers["Patient0"]).json()["appointment_at"]
        == updated.json()["appointment_at"]
    )
    own_slot = client.get(
        slots_path,
        params={
            "work_date": date,
            "exclude_appointment_id": item["appointment_id"],
        },
        headers=headers["Patient0"],
    )
    assert own_slot.status_code == 200, own_slot.text
    assert own_slot.json()["items"][2]["available"]
    assert (
        client.post(
            f"/api/v1/doctor-schedules/{schedule['schedule_id']}/cancel",
            json={"version": schedule["version"]},
            headers=headers["Receptionist"],
        ).status_code
        == 409
    )
    cancel = {"version": updated.json()["version"], "cancellation_reason": "Bận công việc"}
    assert (
        client.post(path + "/cancel", json=cancel, headers=headers["Patient1"]).status_code == 404
    )
    assert (
        client.post(
            path + "/cancel",
            json={**cancel, "cancellation_reason": " "},
            headers=headers["Patient0"],
        ).status_code
        == 422
    )
    cancelled = client.post(path + "/cancel", json=cancel, headers=headers["Patient0"])
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert (
        client.post(
            path + "/cancel",
            json={**cancel, "version": cancelled.json()["version"]},
            headers=headers["Patient0"],
        ).status_code
        == 409
    )
    available = client.get(slots_path, params={"work_date": date}, headers=headers["Patient0"])
    assert available.json()["items"][2]["available"]
    connection = connect()
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM dbo.audit_logs WHERE entity_type='appointments' AND entity_id=?",
            item["appointment_id"],
        ).fetchone()[0]
        assert count == 3
        connection.execute(
            "UPDATE dbo.appointments SET status='completed' WHERE appointment_id=?",
            adjacent.json()["appointment_id"],
        )
        connection.commit()
    finally:
        connection.close()
    completed_path = f"/api/v1/appointments/{adjacent.json()['appointment_id']}"
    completed = client.get(completed_path, headers=headers["Receptionist"]).json()
    assert (
        client.post(
            completed_path + "/cancel",
            json={
                "version": completed["version"],
                "cancellation_reason": "Không được hủy",
            },
            headers=headers["Receptionist"],
        ).status_code
        == 409
    )


@pytest.mark.parametrize("same_patient", [False, True])
def test_concurrent_bookings_only_one_wins(clinic_booking, same_patient):
    env = clinic_booking
    days = 5 if same_patient else 4
    schedule = shift(env, days)
    second_schedule = shift(env, days, doctor=1) if same_patient else schedule
    barrier = Barrier(2)

    def send(i):
        barrier.wait(timeout=10)
        return env["client"].post(
            "/api/v1/appointments",
            json=booking(
                schedule if i == 0 else second_schedule,
                days,
            ),
            headers=env["headers"][f"Patient{0 if same_patient else i}"],
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]
    loser = next(r for r in responses if r.status_code == 409)
    expected = "PATIENT_TIME_CONFLICT" if same_patient else "DOCTOR_TIME_CONFLICT"
    assert loser.json()["error"]["code"] == expected


def test_schedule_cancellation_versioning_and_unavailable_booking(clinic_booking):
    env = clinic_booking
    schedule = shift(env, 7)
    path = f"/api/v1/doctor-schedules/{schedule['schedule_id']}/cancel"
    stale = env["client"].post(
        path, json={"version": "0000000000000000"}, headers=env["headers"]["Admin"]
    )
    assert stale.status_code == 409, stale.text
    cancelled = env["client"].post(
        path, json={"version": schedule["version"]}, headers=env["headers"]["Admin"]
    )
    assert cancelled.status_code == 200, cancelled.text
    response = env["client"].post(
        "/api/v1/appointments", json=booking(schedule, 7), headers=env["headers"]["Patient0"]
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "SCHEDULE_UNAVAILABLE"
    reopened = shift(env, 7)
    assert reopened["schedule_id"] == schedule["schedule_id"]
    assert reopened["status"] == "active"
