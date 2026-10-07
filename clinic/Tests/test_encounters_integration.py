import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from unittest.mock import patch

import pytest

from BLL.appointment_service import CLINIC_TIMEZONE
from DAL.auth_repository import AuthRepository
from DAL.db import connect
from Tests.test_appointments_integration import clinic_booking as clinic_booking
from Tests.test_reception_integration import appointment, receive

pytestmark = pytest.mark.integration


def checked_appointment(env, hour, minute=0, status="checked_in"):
    return appointment(
        env,
        datetime.now(CLINIC_TIMEZONE).replace(hour=hour, minute=minute, second=0, microsecond=0),
        status=status,
    )


def start(env, item, role="Doctor1"):
    return env["client"].post(
        "/api/v1/encounters",
        json={
            "appointment_id": item["appointment_id"],
            "appointment_version": item["version"],
        },
        headers=env["headers"][role],
    )


def write(env, item, path="", method="POST", fields=None, role="Doctor1"):
    return env["client"].request(
        method,
        f"/api/v1/encounters/{item['encounter_id']}" + path,
        json={"version": item["version"], **(fields or {})},
        headers=env["headers"][role],
    )


def new_encounter(env, hour, minute=0):
    result = start(env, checked_appointment(env, hour, minute))
    assert result.status_code == 201, result.text
    return result.json()


def notes():
    return {
        "chief_complaint": "Khám định kỳ",
        "clinical_notes": "Nội dung khám kiểm thử",
        "diagnosis_summary": "Kết luận kiểm thử",
        "treatment_plan": "Tái khám theo hẹn",
        "vital_signs": {
            "temperature_c": 36.8,
            "pulse_bpm": 75,
            "systolic_mmhg": 120,
            "diastolic_mmhg": 80,
            "weight_kg": 60,
        },
        "diagnoses": [
            {"code": "TEST.1", "name": "Chẩn đoán kiểm thử", "is_primary": True},
            {"name": "Chẩn đoán kèm theo", "is_primary": False},
        ],
    }


def test_start_requires_checkin_assignment_and_hides_draft_from_patient(clinic_booking):
    env = clinic_booking
    item = checked_appointment(env, 8, status="booked")
    assert start(env, item).json()["error"]["code"] == "APPOINTMENT_NOT_READY"
    received = receive(env, item, "check-in")
    assert received.status_code == 200, received.text
    item = received.json()
    for role in ("Admin", "Receptionist", "Pharmacist", "Patient0", "Patient1"):
        assert start(env, item, role).status_code == 403
        assert env["client"].get(
            "/api/v1/encounters", headers=env["headers"][role]
        ).status_code == (200 if role.startswith("Patient") else 403)
    assert start(env, item, "Doctor2").status_code == 404
    response = start(env, item)
    assert response.status_code == 201, response.text
    encounter = response.json()
    assert encounter["status"] == "in_progress" and encounter["version_no"] == 1
    assert encounter["appointment_id"] == item["appointment_id"]
    for role in ("Patient0", "Patient1", "Doctor2"):
        assert (
            env["client"]
            .get(f"/api/v1/encounters/{encounter['encounter_id']}", headers=env["headers"][role])
            .status_code
            == 404
        )
    assert start(env, item).status_code == 409
    changed = (
        env["client"]
        .get(f"/api/v1/appointments/{item['appointment_id']}", headers=env["headers"]["Doctor1"])
        .json()
    )
    assert changed["status"] == "in_progress"
    assert start(env, changed).json()["error"]["code"] == "APPOINTMENT_NOT_READY"


def test_complete_clinical_flow_versions_results_and_immutable_record(clinic_booking):
    env = clinic_booking
    item = new_encounter(env, 9)
    assert write(env, item, "/complete").json()["error"]["code"] == "DIAGNOSIS_REQUIRED"
    saved = write(env, item, method="PUT", fields=notes())
    assert saved.status_code == 200, saved.text
    current = saved.json()
    assert current["vital_signs"]["temperature_c"] == 36.8
    assert len(current["diagnoses"]) == 2 and current["diagnoses"][0]["is_primary"]
    assert write(env, item, method="PUT", fields=notes()).status_code == 409
    assert write(env, current, method="PUT", fields=notes(), role="Doctor2").status_code == 404
    for role in ("Admin", "Receptionist", "Pharmacist", "Patient0"):
        assert write(env, current, method="PUT", fields=notes(), role=role).status_code == 403
    # Saving replacement diagnoses is a soft-delete, not a loss of prior content.
    current = write(env, current, method="PUT", fields=notes()).json()
    created = write(
        env,
        current,
        "/clinical-orders",
        fields={
            "order_type": "laboratory",
            "name": "Xét nghiệm kiểm thử",
            "instructions": "Chỉ định demo",
        },
    )
    assert created.status_code == 201, created.text
    current = created.json()
    order = current["clinical_orders"][0]
    order_path = f"/clinical-orders/{order['order_id']}"
    assert write(env, current, "/complete").json()["error"]["code"] == "CLINICAL_ORDERS_PENDING"
    updated = write(
        env,
        current,
        order_path,
        method="PUT",
        fields={
            "order_version": order["version"],
            "order_type": "laboratory",
            "name": order["name"],
            "status": "in_progress",
        },
    )
    assert updated.status_code == 200, updated.text
    current, order = updated.json(), updated.json()["clinical_orders"][0]
    result = write(
        env,
        current,
        order_path + "/results",
        fields={
            "order_version": order["version"],
            "result_text": "Kết quả kiểm thử",
            "numeric_value": "5.500000",
            "unit": "demo",
            "reference_range": "Tham chiếu demo",
        },
    )
    assert result.status_code == 201, result.text
    current, order = result.json(), result.json()["clinical_orders"][0]
    assert order["status"] == "completed"
    assert (
        write(
            env, current, order_path + "/cancel", fields={"order_version": order["version"]}
        ).status_code
        == 409
    )
    value = order["results"][0]
    updated = write(
        env,
        current,
        order_path + f"/results/{value['result_id']}",
        method="PUT",
        fields={
            "order_version": order["version"],
            "result_version": value["version"],
            "result_text": "Kết quả đã sửa",
            "numeric_value": "6.500000",
        },
    )
    assert updated.status_code == 200, updated.text
    current, order = updated.json(), updated.json()["clinical_orders"][0]
    value = order["results"][0]
    deleted = write(
        env,
        current,
        order_path + f"/results/{value['result_id']}",
        method="DELETE",
        fields={"order_version": order["version"], "result_version": value["version"]},
    )
    assert deleted.status_code == 200, deleted.text
    current, order = deleted.json(), deleted.json()["clinical_orders"][0]
    assert order["status"] == "ordered" and order["results"] == []
    assert write(env, current, "/complete").status_code == 409
    result = write(
        env,
        current,
        order_path + "/results",
        fields={
            "order_version": order["version"],
            "numeric_value": "0",
            "unit": "demo",
        },
    )
    assert result.status_code == 201, result.text
    current = result.json()
    completed = write(env, current, "/complete")
    assert completed.status_code == 200, completed.text
    current = completed.json()
    assert current["status"] == "completed" and current["ended_at"] is not None
    patient_record = env["client"].get(
        f"/api/v1/encounters/{current['encounter_id']}", headers=env["headers"]["Patient0"]
    )
    assert patient_record.status_code == 200, patient_record.text
    assert patient_record.json()["clinical_orders"][0]["results"][0]["numeric_value"] == "0.000000"
    assert write(env, current, method="PUT", fields=notes()).status_code == 409
    assert write(env, current, "/complete").status_code == 409
    assert (
        write(
            env,
            current,
            "/clinical-orders",
            fields={"order_type": "other", "name": "Không được thêm sau khi hoàn tất"},
        ).status_code
        == 409
    )
    linked = (
        env["client"]
        .get(
            f"/api/v1/appointments/{current['appointment_id']}",
            headers=env["headers"]["Receptionist"],
        )
        .json()
    )
    assert linked["status"] == "completed"
    history = env["client"].get(
        f"/api/v1/encounters/{current['encounter_id']}/versions",
        headers=env["headers"]["Doctor1"],
        params={"page_size": 2},
    )
    assert history.status_code == 200, history.text
    assert history.json()["total"] == current["version_no"]
    assert history.json()["items"][0]["data"]["status"] == "completed"
    assert len(history.json()["items"]) == 2
    for role in ("Patient0", "Receptionist", "Admin"):
        assert (
            env["client"]
            .get(
                f"/api/v1/encounters/{current['encounter_id']}/versions",
                headers=env["headers"][role],
            )
            .status_code
            == 403
        )
    connection = connect()
    try:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM dbo.diagnoses WHERE encounter_id=? "
                "AND deleted_at IS NOT NULL",
                current["encounter_id"],
            ).fetchone()[0]
            == 2
        )
        assert (
            connection.execute(
                "SELECT deleted_at FROM dbo.clinical_results WHERE result_id=?", value["result_id"]
            ).fetchone()[0]
            is not None
        )
        audit = connection.execute(
            "SELECT COUNT(*) FROM dbo.audit_logs WHERE entity_id=? AND action LIKE 'encounters.%'",
            current["encounter_id"],
        ).fetchone()[0]
        assert audit == current["version_no"]
    finally:
        connection.close()


def test_orders_cancel_delete_and_child_context_are_enforced(clinic_booking):
    env = clinic_booking
    first = new_encounter(env, 10)
    other = new_encounter(env, 11)
    for index in range(2):
        result = write(
            env,
            first,
            "/clinical-orders",
            fields={
                "order_type": "imaging",
                "name": f"Chỉ định {index}",
            },
        )
        assert result.status_code == 201, result.text
        first = result.json()
    orders = first["clinical_orders"]
    foreign_path = f"/clinical-orders/{orders[0]['order_id']}"
    assert (
        write(
            env,
            other,
            foreign_path + "/results",
            fields={
                "order_version": orders[0]["version"],
                "result_text": "Sai bệnh án",
            },
        ).status_code
        == 404
    )
    cancelled = write(
        env, first, foreign_path + "/cancel", fields={"order_version": orders[0]["version"]}
    )
    assert cancelled.status_code == 200, cancelled.text
    first = cancelled.json()
    cancelled_order = next(o for o in first["clinical_orders"] if o["status"] == "cancelled")
    assert (
        write(
            env,
            first,
            foreign_path + "/results",
            fields={
                "order_version": cancelled_order["version"],
                "result_text": "Không được nhập",
            },
        ).status_code
        == 409
    )
    active = next(o for o in first["clinical_orders"] if o["status"] == "ordered")
    deleted = write(
        env,
        first,
        f"/clinical-orders/{active['order_id']}",
        method="DELETE",
        fields={"order_version": active["version"]},
    )
    assert deleted.status_code == 200, deleted.text
    assert len(deleted.json()["clinical_orders"]) == 1
    connection = connect()
    try:
        assert (
            connection.execute(
                "SELECT deleted_at FROM dbo.clinical_orders WHERE order_id=?", active["order_id"]
            ).fetchone()[0]
            is not None
        )
    finally:
        connection.close()


def test_concurrent_start_and_save_produce_one_version_each(clinic_booking):
    env = clinic_booking
    item = checked_appointment(env, 12)
    barrier = Barrier(2)

    def start_once(_):
        barrier.wait(timeout=10)
        return start(env, item)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start_once, range(2)))
    assert sorted(r.status_code for r in results) == [201, 409]
    encounter = next(r.json() for r in results if r.status_code == 201)
    barrier = Barrier(2)

    def save_once(_):
        barrier.wait(timeout=10)
        return write(env, encounter, method="PUT", fields=notes())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save_once, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    current = next(r.json() for r in results if r.status_code == 200)
    assert current["version_no"] == 2
    history = env["client"].get(
        f"/api/v1/encounters/{current['encounter_id']}/versions", headers=env["headers"]["Doctor1"]
    )
    assert history.json()["total"] == 2
    assert (
        json.loads(json.dumps(history.json()["items"][0]["data"]))["diagnoses"][0]["name"]
        == "Chẩn đoán kiểm thử"
    )


def test_encounter_listing_scopes_filters_pagination_validation(clinic_booking):
    env = clinic_booking
    current = new_encounter(env, 13)
    client, headers = env["client"], env["headers"]
    params = {"search": env["suffix"], "page_size": 1, "sort_order": "asc"}
    listing = client.get("/api/v1/encounters", params=params, headers=headers["Doctor1"])
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] >= 4 and len(listing.json()["items"]) == 1
    assert (
        client.get("/api/v1/encounters", params=params, headers=headers["Doctor2"]).json()["total"]
        == 0
    )
    for role in ("Patient0", "Patient1"):
        response = client.get(
            "/api/v1/encounters",
            params={"appointment_id": current["appointment_id"]},
            headers=headers[role],
        )
        assert response.json()["total"] == 0
    filtered = client.get(
        "/api/v1/encounters",
        params={"appointment_id": current["appointment_id"]},
        headers=headers["Doctor1"],
    ).json()
    assert (
        filtered["total"] == 1 and filtered["items"][0]["encounter_id"] == current["encounter_id"]
    )
    escaped = client.get(
        "/api/v1/encounters", params={"search": "%_'["}, headers=headers["Doctor1"]
    ).json()
    assert escaped["total"] == 0
    invalid = write(
        env,
        current,
        method="PUT",
        fields={
            "diagnoses": [{"name": "A", "is_primary": True}, {"name": "B", "is_primary": True}]
        },
    )
    assert invalid.status_code == 422
    assert (
        client.get(
            "/api/v1/encounters", params={"page_size": 101}, headers=headers["Doctor1"]
        ).status_code
        == 422
    )


def test_multiple_results_keep_order_completed_and_guard_result_identity(clinic_booking):
    env = clinic_booking
    current = new_encounter(env, 14)
    current = write(
        env,
        current,
        "/clinical-orders",
        fields={
            "order_type": "laboratory",
            "name": "Nhiều kết quả kiểm thử",
        },
    ).json()
    order = current["clinical_orders"][0]
    path = f"/clinical-orders/{order['order_id']}/results"
    for value in (0, 7):
        response = write(
            env,
            current,
            path,
            fields={
                "order_version": order["version"],
                "numeric_value": value,
            },
        )
        assert response.status_code == 201, response.text
        current, order = response.json(), response.json()["clinical_orders"][0]
    first, second = order["results"]
    rejected = write(
        env,
        current,
        path + f"/{first['result_id']}",
        method="PUT",
        fields={
            "order_version": order["version"],
            "result_version": "0000000000000000",
            "result_text": "Version sai",
        },
    )
    assert rejected.status_code == 409
    deleted = write(
        env,
        current,
        path + f"/{first['result_id']}",
        method="DELETE",
        fields={
            "order_version": order["version"],
            "result_version": first["version"],
        },
    )
    assert deleted.status_code == 200, deleted.text
    current, order = deleted.json(), deleted.json()["clinical_orders"][0]
    assert order["status"] == "completed" and len(order["results"]) == 1
    assert order["results"][0]["result_id"] == second["result_id"]
    missing = write(
        env,
        current,
        path + f"/{first['result_id']}",
        method="DELETE",
        fields={
            "order_version": order["version"],
            "result_version": first["version"],
        },
    )
    assert missing.status_code == 404


def test_failed_audit_rolls_back_encounter_appointment_and_snapshot(clinic_booking):
    env = clinic_booking
    item = checked_appointment(env, 15)
    connection = connect()
    try:
        before = connection.execute(
            "SELECT COUNT(*) FROM dbo.record_versions WHERE changed_by="
            "(SELECT user_id FROM dbo.doctors WHERE doctor_id=?)",
            env["doctors"][0],
        ).fetchone()[0]
    finally:
        connection.close()
    with patch.object(AuthRepository, "audit", side_effect=RuntimeError("audit offline")):
        with pytest.raises(RuntimeError, match="audit offline"):
            start(env, item)
    connection = connect()
    try:
        assert (
            connection.execute(
                "SELECT status FROM dbo.appointments WHERE appointment_id=?",
                item["appointment_id"],
            ).fetchone()[0]
            == "checked_in"
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM dbo.encounters WHERE appointment_id=?",
                item["appointment_id"],
            ).fetchone()[0]
            == 0
        )
        after = connection.execute(
            "SELECT COUNT(*) FROM dbo.record_versions WHERE changed_by="
            "(SELECT user_id FROM dbo.doctors WHERE doctor_id=?)",
            env["doctors"][0],
        ).fetchone()[0]
        assert after == before
    finally:
        connection.close()
