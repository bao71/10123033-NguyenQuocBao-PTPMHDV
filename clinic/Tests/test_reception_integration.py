import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest

from BLL.appointment_service import CLINIC_TIMEZONE
from DAL.db import connect
from Tests.test_appointments_integration import clinic_booking as clinic_booking

pytestmark = pytest.mark.integration


def appointment(env, at, status="booked", encounter=False):
    """Controlled legacy appointments let tests exercise past/day-boundary reception rules."""
    identifier = str(uuid4())
    connection = connect()
    try:
        connection.execute(
            "INSERT dbo.appointments(appointment_id,patient_id,doctor_id,appointment_at,"
            "duration_minutes,status,created_by) "
            "VALUES(?,?,?,?,5,?,(SELECT user_id FROM dbo.patients WHERE patient_id=?))",
            identifier,
            env["patients"][0],
            env["doctors"][0],
            at.astimezone(timezone.utc).replace(tzinfo=None),
            status,
            env["patients"][0],
        )
        if encounter:
            connection.execute(
                "INSERT dbo.encounters(appointment_id,patient_id,doctor_id) VALUES(?,?,?)",
                identifier,
                env["patients"][0],
                env["doctors"][0],
            )
        connection.commit()
    finally:
        connection.close()
    response = env["client"].get(
        f"/api/v1/appointments/{identifier}",
        headers=env["headers"]["Receptionist"],
    )
    assert response.status_code == 200, response.text
    return response.json()


def receive(env, item, action, role="Receptionist"):
    return env["client"].post(
        f"/api/v1/appointments/{item['appointment_id']}/{action}",
        json={"version": item["version"]},
        headers=env["headers"][role],
    )


def test_confirmation_checkin_permissions_versions_and_audit(clinic_booking):
    env = clinic_booking
    now = datetime.now(CLINIC_TIMEZONE)
    item = appointment(env, now + timedelta(days=1, minutes=12))
    for role in ("Admin", "Doctor1", "Doctor2", "Pharmacist", "Patient0", "Patient1"):
        assert (
            env["client"].get("/api/v1/reception", headers=env["headers"][role]).status_code == 403
        )
        for action in ("confirm", "check-in", "no-show"):
            assert receive(env, item, action, role).status_code == 403
    result = receive(env, item, "confirm")
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "confirmed"
    assert result.json()["version"] != item["version"]
    assert receive(env, item, "confirm").json()["error"]["code"] == "APPOINTMENT_VERSION_CONFLICT"
    assert (
        receive(env, result.json(), "check-in").json()["error"]["code"] == "RECEPTION_TIME_CONFLICT"
    )
    today = appointment(env, now.replace(hour=12, minute=0, second=0, microsecond=0))
    checked = receive(env, today, "check-in")
    assert checked.status_code == 200, checked.text
    checked = checked.json()
    assert checked["status"] == "checked_in"
    path = f"/api/v1/appointments/{checked['appointment_id']}"
    for role in ("Doctor1", "Patient0"):
        assert (
            env["client"].get(path, headers=env["headers"][role]).json()["status"] == "checked_in"
        )
    assert env["client"].get(path, headers=env["headers"]["Patient1"]).status_code == 404
    assert env["client"].get(path, headers=env["headers"]["Doctor2"]).status_code == 404
    cancelled = env["client"].post(
        path + "/cancel",
        json={"version": checked["version"], "cancellation_reason": "Đổi ý"},
        headers=env["headers"]["Patient0"],
    )
    assert cancelled.status_code == 409
    assert receive(env, checked, "check-in").json()["error"]["code"] == "RECEPTION_STATE_CONFLICT"
    assert receive(env, checked, "no-show").status_code == 409
    connection = connect()
    try:
        row = connection.execute(
            "SELECT action,after_json FROM dbo.audit_logs WHERE entity_id=? "
            "AND action='appointments.check_in'",
            checked["appointment_id"],
        ).fetchone()
        assert row is not None
        assert json.loads(row.after_json)["previous_status"] == "booked"
        assert json.loads(row.after_json)["status"] == "checked_in"
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM dbo.encounters WHERE appointment_id=?",
                checked["appointment_id"],
            ).fetchone()[0]
            == 0
        )
    finally:
        connection.close()


def test_no_show_requires_elapsed_slot_and_no_encounter(clinic_booking):
    env = clinic_booking
    now = datetime.now(CLINIC_TIMEZONE)
    future = appointment(env, now + timedelta(days=2))
    assert receive(env, future, "no-show").json()["error"]["code"] == "RECEPTION_TIME_CONFLICT"
    past = appointment(env, now - timedelta(hours=2))
    assert receive(env, past, "confirm").status_code == 409
    absent = receive(env, past, "no-show")
    assert absent.status_code == 200, absent.text
    assert absent.json()["status"] == "no_show"
    assert receive(env, absent.json(), "check-in").status_code == 409
    with_record = appointment(env, now - timedelta(days=2), encounter=True)
    assert (
        receive(env, with_record, "no-show").json()["error"]["code"] == "RECEPTION_STATE_CONFLICT"
    )
    yesterday = appointment(env, now - timedelta(days=3))
    assert receive(env, yesterday, "check-in").json()["error"]["code"] == "RECEPTION_TIME_CONFLICT"


def test_reception_day_boundaries_search_status_pagination_and_sort(clinic_booking):
    env = clinic_booking
    day = (datetime.now(CLINIC_TIMEZONE) + timedelta(days=5)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    before = appointment(env, day - timedelta(minutes=10))
    first = appointment(env, day)
    second = appointment(env, day + timedelta(hours=1), "confirmed")
    after = appointment(env, day + timedelta(days=1))
    params = {
        "work_date": day.date().isoformat(),
        "search": env["suffix"],
        "doctor_id": env["doctors"][0],
        "page_size": 1,
    }
    client, headers = env["client"], env["headers"]["Receptionist"]
    result = client.get("/api/v1/reception", params=params, headers=headers)
    assert result.status_code == 200, result.text
    listing = result.json()
    assert listing["total"] == listing["summary"]["total"] == 2
    assert listing["summary"]["booked"] == listing["summary"]["confirmed"] == 1
    assert listing["items"][0]["appointment_id"] == first["appointment_id"]
    listing = client.get("/api/v1/reception", params={**params, "page": 2}, headers=headers).json()
    assert listing["items"][0]["appointment_id"] == second["appointment_id"]
    listing = client.get(
        "/api/v1/reception", params={**params, "status": "confirmed"}, headers=headers
    ).json()
    assert listing["total"] == 1 and listing["summary"]["total"] == 2
    listing = client.get(
        "/api/v1/reception", params={**params, "sort_order": "desc"}, headers=headers
    ).json()
    assert listing["items"][0]["appointment_id"] == second["appointment_id"]
    excluded = {before["appointment_id"], after["appointment_id"]}
    assert not excluded.intersection(item["appointment_id"] for item in listing["items"])
    empty = client.get(
        "/api/v1/reception", params={**params, "search": "%_'["}, headers=headers
    ).json()
    assert empty["total"] == empty["summary"]["total"] == 0
    assert (
        client.get("/api/v1/reception", params={**params, "page": 0}, headers=headers).status_code
        == 422
    )


def test_concurrent_checkin_only_one_change_and_audit(clinic_booking):
    env = clinic_booking
    now = datetime.now(CLINIC_TIMEZONE).replace(hour=13, minute=0, second=0, microsecond=0)
    item = appointment(env, now)
    barrier = Barrier(2)

    def check_in():
        barrier.wait(timeout=10)
        return receive(env, item, "check-in")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: check_in(), range(2)))
    assert sorted(response.status_code for response in results) == [200, 409]
    rejected = next(response for response in results if response.status_code == 409)
    assert rejected.json()["error"]["code"] == "APPOINTMENT_VERSION_CONFLICT"
    connection = connect()
    try:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM dbo.audit_logs WHERE entity_id=? "
                "AND action='appointments.check_in'",
                item["appointment_id"],
            ).fetchone()[0]
            == 1
        )
    finally:
        connection.close()
