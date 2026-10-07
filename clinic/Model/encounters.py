from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Version = str
VERSION_PATTERN = r"^[0-9A-Fa-f]{16}$"
EncounterStatus = Literal["in_progress", "completed", "cancelled"]
OrderType = Literal["laboratory", "imaging", "other"]
OrderStatus = Literal["ordered", "in_progress", "completed", "cancelled"]


class ClinicalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VitalSigns(ClinicalInput):
    temperature_c: float | None = Field(default=None, ge=25, le=45, allow_inf_nan=False)
    pulse_bpm: int | None = Field(default=None, ge=20, le=300)
    systolic_mmhg: int | None = Field(default=None, ge=40, le=300)
    diastolic_mmhg: int | None = Field(default=None, ge=20, le=200)
    respiratory_rate: int | None = Field(default=None, ge=5, le=80)
    spo2_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    height_cm: float | None = Field(default=None, gt=0, le=250, allow_inf_nan=False)

    @model_validator(mode="after")
    def blood_pressure_order(self):
        if (
            self.systolic_mmhg is not None
            and self.diastolic_mmhg is not None
            and self.systolic_mmhg <= self.diastolic_mmhg
        ):
            raise ValueError("Huyết áp tâm thu phải lớn hơn huyết áp tâm trương")
        return self


class DiagnosisInput(ClinicalInput):
    code: str | None = Field(default=None, max_length=30, pattern=r"^[A-Za-z0-9.\-]+$")
    name: str = Field(min_length=1, max_length=500)
    is_primary: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class EncounterStartRequest(ClinicalInput):
    appointment_id: UUID
    appointment_version: Version = Field(pattern=VERSION_PATTERN)
    chief_complaint: str | None = Field(default=None, max_length=2000)


class EncounterVersionRequest(ClinicalInput):
    version: Version = Field(pattern=VERSION_PATTERN)


class EncounterUpdateRequest(EncounterVersionRequest):
    chief_complaint: str | None = Field(default=None, max_length=2000)
    clinical_notes: str | None = Field(default=None, max_length=20000)
    diagnosis_summary: str | None = Field(default=None, max_length=2000)
    treatment_plan: str | None = Field(default=None, max_length=20000)
    vital_signs: VitalSigns = Field(default_factory=VitalSigns)
    diagnoses: list[DiagnosisInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def one_primary_diagnosis(self):
        if sum(item.is_primary for item in self.diagnoses) > 1:
            raise ValueError("Chỉ được có một chẩn đoán chính")
        return self


class ClinicalOrderCreateRequest(EncounterVersionRequest):
    order_type: OrderType
    name: str = Field(min_length=1, max_length=300)
    instructions: str | None = Field(default=None, max_length=2000)


class ClinicalOrderUpdateRequest(ClinicalOrderCreateRequest):
    order_version: Version = Field(pattern=VERSION_PATTERN)
    status: Literal["ordered", "in_progress"] = "ordered"


class ClinicalOrderVersionRequest(EncounterVersionRequest):
    order_version: Version = Field(pattern=VERSION_PATTERN)


class ClinicalResultCreateRequest(ClinicalOrderVersionRequest):
    result_text: str | None = Field(default=None, max_length=20000)
    numeric_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    unit: str | None = Field(default=None, max_length=50)
    reference_range: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def nonempty_result(self):
        if not self.result_text and self.numeric_value is None:
            raise ValueError("Nhập nội dung hoặc giá trị kết quả")
        return self


class ClinicalResultUpdateRequest(ClinicalResultCreateRequest):
    result_version: Version = Field(pattern=VERSION_PATTERN)


class ClinicalResultVersionRequest(ClinicalOrderVersionRequest):
    result_version: Version = Field(pattern=VERSION_PATTERN)


class DiagnosisItem(DiagnosisInput):
    diagnosis_id: UUID
    version: Version


class ClinicalResultItem(BaseModel):
    result_id: UUID
    order_id: UUID
    entered_by: UUID
    result_text: str | None
    numeric_value: Decimal | None
    unit: str | None
    reference_range: str | None
    file_url: str | None
    result_at: datetime
    updated_at: datetime
    version: Version


class ClinicalOrderItem(BaseModel):
    order_id: UUID
    encounter_id: UUID
    ordered_by: UUID
    order_type: OrderType
    name: str
    instructions: str | None
    status: OrderStatus
    ordered_at: datetime
    updated_at: datetime
    version: Version
    results: list[ClinicalResultItem] = Field(default_factory=list)


class EncounterItem(BaseModel):
    encounter_id: UUID
    appointment_id: UUID | None
    patient_id: UUID
    patient_code: str
    patient_name: str
    doctor_id: UUID
    doctor_code: str
    doctor_name: str
    specialty: str
    started_at: datetime
    ended_at: datetime | None
    chief_complaint: str | None
    diagnosis_summary: str | None
    status: EncounterStatus
    version_no: int
    version: Version
    updated_at: datetime


class EncounterDetail(EncounterItem):
    clinical_notes: str | None
    treatment_plan: str | None
    vital_signs: VitalSigns
    diagnoses: list[DiagnosisItem]
    clinical_orders: list[ClinicalOrderItem]


class EncounterListResponse(BaseModel):
    items: list[EncounterItem]
    page: int
    page_size: int
    total: int


class EncounterRecordVersion(BaseModel):
    version_no: int
    changed_by: UUID
    changed_by_name: str
    change_reason: str
    changed_at: datetime
    data: dict


class EncounterVersionListResponse(BaseModel):
    items: list[EncounterRecordVersion]
    page: int
    page_size: int
    total: int
