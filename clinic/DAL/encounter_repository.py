import json
from datetime import datetime, timezone
from uuid import UUID

from DAL.procedures import call


def records(cursor):
    columns = [column[0] for column in cursor.description]
    items = []
    for row in cursor.fetchall():
        item = dict(zip(columns, row, strict=True))
        for key, value in list(item.items()):
            if isinstance(value, datetime):
                item[key] = value.replace(tzinfo=timezone.utc)
        if "row_version" in item:
            item["version"] = bytes(item.pop("row_version")).hex().upper()
        if "vital_signs_json" in item:
            item["vital_signs"] = json.loads(item.pop("vital_signs_json"))
        items.append(item)
    return items


class EncounterRepository:
    @staticmethod
    def list(
        connection,
        *,
        scope,
        user_id,
        page,
        page_size,
        search=None,
        patient_id=None,
        status=None,
        start_at=None,
        end_at=None,
        sort_by="started_at",
        sort_order="desc",
        appointment_id=None,
    ):
        cursor = call(
            connection,
            "clinic_encounter_list",
            scope,
            str(user_id),
            page,
            page_size,
            search,
            str(patient_id) if patient_id else None,
            status,
            start_at,
            end_at,
            sort_by,
            sort_order,
            str(appointment_id) if appointment_id else None,
        )
        total = cursor.fetchone().total
        cursor.nextset()
        return records(cursor), total

    @staticmethod
    def get(connection, encounter_id, *, scope, user_id):
        cursor = call(connection, "clinic_encounter_get", scope, str(user_id), str(encounter_id))
        items = records(cursor)
        if not items:
            return None
        item = items[0]
        cursor.nextset()
        item["diagnoses"] = records(cursor)
        cursor.nextset()
        orders = records(cursor)
        cursor.nextset()
        results = records(cursor)
        for order in orders:
            order["results"] = [
                result for result in results if result["order_id"] == order["order_id"]
            ]
        item["clinical_orders"] = orders
        return item

    @staticmethod
    def write(
        connection,
        *,
        action,
        actor_id,
        encounter_id=None,
        appointment_id=None,
        appointment_version=None,
        version=None,
        chief_complaint=None,
        clinical_notes=None,
        diagnosis_summary=None,
        treatment_plan=None,
        vital_signs=None,
        diagnoses=None,
        order_id=None,
        order_version=None,
        order_type=None,
        name=None,
        instructions=None,
        status=None,
        result_id=None,
        result_version=None,
        result_text=None,
        numeric_value=None,
        unit=None,
        reference_range=None,
    ):
        row = call(
            connection,
            "clinic_encounter_write",
            action,
            str(actor_id),
            str(encounter_id) if encounter_id else None,
            str(appointment_id) if appointment_id else None,
            bytes.fromhex(appointment_version) if appointment_version else None,
            bytes.fromhex(version) if version else None,
            chief_complaint,
            clinical_notes,
            diagnosis_summary,
            treatment_plan,
            json.dumps(vital_signs) if vital_signs is not None else None,
            json.dumps(diagnoses, ensure_ascii=False) if diagnoses is not None else None,
            str(order_id) if order_id else None,
            bytes.fromhex(order_version) if order_version else None,
            order_type,
            name,
            instructions,
            status,
            str(result_id) if result_id else None,
            bytes.fromhex(result_version) if result_version else None,
            result_text,
            numeric_value,
            unit,
            reference_range,
        ).fetchone()
        return UUID(str(row.encounter_id))

    @staticmethod
    def versions(connection, encounter_id, *, user_id, page, page_size):
        cursor = call(
            connection,
            "clinic_encounter_versions",
            str(encounter_id),
            str(user_id),
            page,
            page_size,
        )
        total = cursor.fetchone().total
        cursor.nextset()
        items = records(cursor)
        for item in items:
            item["data"] = json.loads(item.pop("data_json"))
        return items, total
