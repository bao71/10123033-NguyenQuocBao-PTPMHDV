-- ClinicManagement: physical schema derived from the 30-table SRS/ERD.
-- SQL Server 2022. Executed once by the migration runner in its transaction.
-- All DATETIME2 values and schedule date/time pairs use UTC. DATE-only clinical
-- values (birth, onset, expiry) represent calendar dates, not UTC instants.
-- No cascading deletes: historical clinical/financial relations must survive.
-- The API must enforce record ownership, state transitions and cross-row rules
-- under transactions: overlapping bookings, total payments, drug/line matching,
-- FEFO/expiry, inventory reconciliation, immutable audit and version snapshots.

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET ARITHABORT ON;
SET NUMERIC_ROUNDABORT OFF;

CREATE TABLE dbo.roles (
    role_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_roles_id DEFAULT NEWSEQUENTIALID(),
    code VARCHAR(40) NOT NULL,
    name NVARCHAR(100) NOT NULL,
    description NVARCHAR(500) NULL,
    CONSTRAINT PK_roles PRIMARY KEY (role_id),
    CONSTRAINT UQ_roles_code UNIQUE (code)
);

CREATE TABLE dbo.permissions (
    permission_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_permissions_id DEFAULT NEWSEQUENTIALID(),
    code VARCHAR(120) NOT NULL,
    resource VARCHAR(60) NOT NULL,
    action VARCHAR(60) NOT NULL,
    CONSTRAINT PK_permissions PRIMARY KEY (permission_id),
    CONSTRAINT UQ_permissions_code UNIQUE (code),
    CONSTRAINT UQ_permissions_resource_action UNIQUE (resource, action)
);

CREATE TABLE dbo.role_permissions (
    role_id UNIQUEIDENTIFIER NOT NULL,
    permission_id UNIQUEIDENTIFIER NOT NULL,
    CONSTRAINT PK_role_permissions PRIMARY KEY (role_id, permission_id),
    CONSTRAINT FK_role_permissions_role FOREIGN KEY (role_id) REFERENCES dbo.roles(role_id),
    CONSTRAINT FK_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES dbo.permissions(permission_id)
);
CREATE INDEX IX_role_permissions_permission ON dbo.role_permissions(permission_id);

CREATE TABLE dbo.users (
    user_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_users_id DEFAULT NEWSEQUENTIALID(),
    role_id UNIQUEIDENTIFIER NOT NULL,
    username NVARCHAR(100) NOT NULL,
    email NVARCHAR(254) NULL,
    password_hash VARCHAR(512) NOT NULL,
    phone VARCHAR(20) NULL,
    is_active BIT NOT NULL CONSTRAINT DF_users_active DEFAULT 1,
    failed_login_count INT NOT NULL CONSTRAINT DF_users_failures DEFAULT 0,
    locked_until DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_users_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_users_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_users PRIMARY KEY (user_id),
    CONSTRAINT FK_users_role FOREIGN KEY (role_id) REFERENCES dbo.roles(role_id),
    CONSTRAINT CK_users_failures CHECK (failed_login_count >= 0),
    CONSTRAINT CK_users_username CHECK (LEN(LTRIM(RTRIM(username))) > 0),
    CONSTRAINT CK_users_contact CHECK (email IS NOT NULL OR phone IS NOT NULL),
    CONSTRAINT CK_users_email CHECK (email IS NULL OR LEN(LTRIM(RTRIM(email))) > 0),
    CONSTRAINT CK_users_phone CHECK (phone IS NULL OR LEN(LTRIM(RTRIM(phone))) > 0),
    CONSTRAINT CK_users_password CHECK (LEN(password_hash) >= 20)
);
CREATE UNIQUE INDEX UX_users_username_active ON dbo.users(username) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX UX_users_email_active ON dbo.users(email) WHERE deleted_at IS NULL AND email IS NOT NULL;
CREATE UNIQUE INDEX UX_users_phone_active ON dbo.users(phone) WHERE deleted_at IS NULL AND phone IS NOT NULL;
CREATE INDEX IX_users_role ON dbo.users(role_id, is_active) INCLUDE (deleted_at);

CREATE TABLE dbo.refresh_tokens (
    token_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_refresh_tokens_id DEFAULT NEWSEQUENTIALID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at DATETIME2(3) NOT NULL,
    revoked_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_refresh_tokens_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_refresh_tokens PRIMARY KEY (token_id),
    CONSTRAINT UQ_refresh_tokens_hash UNIQUE (token_hash),
    CONSTRAINT FK_refresh_tokens_user FOREIGN KEY (user_id) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_refresh_tokens_expiry CHECK (expires_at > created_at)
);
CREATE INDEX IX_refresh_tokens_user ON dbo.refresh_tokens(user_id, expires_at) INCLUDE (revoked_at);

CREATE TABLE dbo.password_reset_tokens (
    token_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_password_reset_tokens_id DEFAULT NEWSEQUENTIALID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at DATETIME2(3) NOT NULL,
    used_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_password_reset_tokens_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_password_reset_tokens PRIMARY KEY (token_id),
    CONSTRAINT UQ_password_reset_tokens_hash UNIQUE (token_hash),
    CONSTRAINT FK_password_reset_tokens_user FOREIGN KEY (user_id) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_password_reset_tokens_expiry CHECK (expires_at > created_at)
);
CREATE INDEX IX_password_reset_tokens_user ON dbo.password_reset_tokens(user_id, expires_at);

CREATE TABLE dbo.patients (
    patient_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_patients_id DEFAULT NEWSEQUENTIALID(),
    user_id UNIQUEIDENTIFIER NULL,
    patient_code VARCHAR(30) NOT NULL,
    full_name NVARCHAR(200) NOT NULL,
    date_of_birth DATE NULL,
    gender VARCHAR(20) NULL,
    phone VARCHAR(20) NULL,
    email NVARCHAR(254) NULL,
    address NVARCHAR(500) NULL,
    blood_type VARCHAR(3) NULL,
    insurance_number VARCHAR(50) NULL,
    emergency_contact NVARCHAR(500) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_patients_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_patients_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_patients PRIMARY KEY (patient_id),
    CONSTRAINT UQ_patients_code UNIQUE (patient_code),
    CONSTRAINT FK_patients_user FOREIGN KEY (user_id) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_patients_name CHECK (LEN(LTRIM(RTRIM(full_name))) > 0),
    CONSTRAINT CK_patients_gender CHECK (gender IS NULL OR gender IN ('male', 'female', 'other', 'unknown')),
    CONSTRAINT CK_patients_blood CHECK (blood_type IS NULL OR blood_type IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'))
);
CREATE UNIQUE INDEX UX_patients_user ON dbo.patients(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IX_patients_name ON dbo.patients(full_name) INCLUDE (patient_code, phone) WHERE deleted_at IS NULL;
CREATE INDEX IX_patients_phone ON dbo.patients(phone) INCLUDE (patient_code, full_name) WHERE deleted_at IS NULL;

CREATE TABLE dbo.doctors (
    doctor_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_doctors_id DEFAULT NEWSEQUENTIALID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    doctor_code VARCHAR(30) NOT NULL,
    specialty NVARCHAR(200) NOT NULL,
    license_number NVARCHAR(100) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_doctors_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_doctors_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_doctors PRIMARY KEY (doctor_id),
    CONSTRAINT UQ_doctors_user UNIQUE (user_id),
    CONSTRAINT UQ_doctors_code UNIQUE (doctor_code),
    CONSTRAINT FK_doctors_user FOREIGN KEY (user_id) REFERENCES dbo.users(user_id)
);
CREATE UNIQUE INDEX UX_doctors_license ON dbo.doctors(license_number) WHERE license_number IS NOT NULL;

CREATE TABLE dbo.doctor_schedules (
    schedule_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_doctor_schedules_id DEFAULT NEWSEQUENTIALID(),
    doctor_id UNIQUEIDENTIFIER NOT NULL,
    work_date DATE NOT NULL,
    start_time TIME(0) NOT NULL,
    end_time TIME(0) NOT NULL,
    slot_minutes SMALLINT NOT NULL CONSTRAINT DF_doctor_schedules_slot DEFAULT 30,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_doctor_schedules_status DEFAULT 'active',
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_doctor_schedules_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_doctor_schedules_updated DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_doctor_schedules PRIMARY KEY (schedule_id),
    CONSTRAINT UQ_doctor_schedules_doctor_range UNIQUE (doctor_id, work_date, start_time, end_time),
    CONSTRAINT UQ_doctor_schedules_doctor UNIQUE (schedule_id, doctor_id),
    CONSTRAINT FK_doctor_schedules_doctor FOREIGN KEY (doctor_id) REFERENCES dbo.doctors(doctor_id),
    CONSTRAINT CK_doctor_schedules_time CHECK (end_time > start_time),
    CONSTRAINT CK_doctor_schedules_slot CHECK (slot_minutes BETWEEN 5 AND 240 AND DATEDIFF(MINUTE, start_time, end_time) >= slot_minutes),
    CONSTRAINT CK_doctor_schedules_status CHECK (status IN ('active', 'cancelled'))
);

CREATE TABLE dbo.appointments (
    appointment_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_appointments_id DEFAULT NEWSEQUENTIALID(),
    patient_id UNIQUEIDENTIFIER NOT NULL,
    doctor_id UNIQUEIDENTIFIER NOT NULL,
    schedule_id UNIQUEIDENTIFIER NULL,
    created_by UNIQUEIDENTIFIER NOT NULL,
    appointment_at DATETIME2(3) NOT NULL,
    duration_minutes SMALLINT NOT NULL CONSTRAINT DF_appointments_duration DEFAULT 30,
    reason NVARCHAR(1000) NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_appointments_status DEFAULT 'booked',
    cancellation_reason NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_appointments_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_appointments_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_appointments PRIMARY KEY (appointment_id),
    CONSTRAINT UQ_appointments_context UNIQUE (appointment_id, patient_id, doctor_id),
    CONSTRAINT FK_appointments_patient FOREIGN KEY (patient_id) REFERENCES dbo.patients(patient_id),
    CONSTRAINT FK_appointments_doctor FOREIGN KEY (doctor_id) REFERENCES dbo.doctors(doctor_id),
    CONSTRAINT FK_appointments_schedule_doctor FOREIGN KEY (schedule_id, doctor_id) REFERENCES dbo.doctor_schedules(schedule_id, doctor_id),
    CONSTRAINT FK_appointments_creator FOREIGN KEY (created_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_appointments_duration CHECK (duration_minutes BETWEEN 5 AND 240),
    CONSTRAINT CK_appointments_status CHECK (status IN ('booked', 'confirmed', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show')),
    CONSTRAINT CK_appointments_cancel_reason CHECK (status <> 'cancelled' OR LEN(LTRIM(RTRIM(cancellation_reason))) > 0 AND cancellation_reason IS NOT NULL)
);
-- These block identical active start times; partial time overlaps need a
-- serializable service transaction over the doctor/patient time-range index.
CREATE UNIQUE INDEX UX_appointments_doctor_start ON dbo.appointments(doctor_id, appointment_at)
    WHERE deleted_at IS NULL AND status <> 'cancelled' AND status <> 'no_show';
CREATE UNIQUE INDEX UX_appointments_patient_start ON dbo.appointments(patient_id, appointment_at)
    WHERE deleted_at IS NULL AND status <> 'cancelled' AND status <> 'no_show';
CREATE INDEX IX_appointments_status_date ON dbo.appointments(status, appointment_at) INCLUDE (doctor_id, patient_id, deleted_at);
CREATE INDEX IX_appointments_schedule ON dbo.appointments(schedule_id);
CREATE INDEX IX_appointments_creator ON dbo.appointments(created_by);

CREATE TABLE dbo.medical_histories (
    history_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_medical_histories_id DEFAULT NEWSEQUENTIALID(),
    patient_id UNIQUEIDENTIFIER NOT NULL,
    created_by UNIQUEIDENTIFIER NOT NULL,
    type VARCHAR(30) NOT NULL,
    name NVARCHAR(200) NOT NULL,
    description NVARCHAR(MAX) NULL,
    onset_date DATE NULL,
    is_active BIT NOT NULL CONSTRAINT DF_medical_histories_active DEFAULT 1,
    version_no INT NOT NULL CONSTRAINT DF_medical_histories_version DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_medical_histories_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_medical_histories_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_medical_histories PRIMARY KEY (history_id),
    CONSTRAINT FK_medical_histories_patient FOREIGN KEY (patient_id) REFERENCES dbo.patients(patient_id),
    CONSTRAINT FK_medical_histories_creator FOREIGN KEY (created_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_medical_histories_type CHECK (type IN ('allergy', 'condition', 'surgery', 'family', 'medication', 'other')),
    CONSTRAINT CK_medical_histories_version CHECK (version_no > 0)
);
CREATE INDEX IX_medical_histories_patient ON dbo.medical_histories(patient_id, type) INCLUDE (is_active, deleted_at);
CREATE INDEX IX_medical_histories_creator ON dbo.medical_histories(created_by);

CREATE TABLE dbo.encounters (
    encounter_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_encounters_id DEFAULT NEWSEQUENTIALID(),
    appointment_id UNIQUEIDENTIFIER NULL,
    patient_id UNIQUEIDENTIFIER NOT NULL,
    doctor_id UNIQUEIDENTIFIER NOT NULL,
    started_at DATETIME2(3) NOT NULL CONSTRAINT DF_encounters_started DEFAULT SYSUTCDATETIME(),
    ended_at DATETIME2(3) NULL,
    chief_complaint NVARCHAR(2000) NULL,
    clinical_notes NVARCHAR(MAX) NULL,
    diagnosis_summary NVARCHAR(2000) NULL,
    treatment_plan NVARCHAR(MAX) NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_encounters_status DEFAULT 'in_progress',
    version_no INT NOT NULL CONSTRAINT DF_encounters_version DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_encounters_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_encounters_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_encounters PRIMARY KEY (encounter_id),
    CONSTRAINT UQ_encounters_context UNIQUE (encounter_id, patient_id, doctor_id),
    CONSTRAINT UQ_encounters_patient UNIQUE (encounter_id, patient_id),
    CONSTRAINT FK_encounters_appointment_context FOREIGN KEY (appointment_id, patient_id, doctor_id) REFERENCES dbo.appointments(appointment_id, patient_id, doctor_id),
    CONSTRAINT FK_encounters_patient FOREIGN KEY (patient_id) REFERENCES dbo.patients(patient_id),
    CONSTRAINT FK_encounters_doctor FOREIGN KEY (doctor_id) REFERENCES dbo.doctors(doctor_id),
    CONSTRAINT CK_encounters_time CHECK (ended_at IS NULL OR ended_at >= started_at),
    CONSTRAINT CK_encounters_status CHECK (status IN ('in_progress', 'completed', 'cancelled')),
    CONSTRAINT CK_encounters_completed CHECK (status <> 'completed' OR ended_at IS NOT NULL AND diagnosis_summary IS NOT NULL AND LEN(LTRIM(RTRIM(diagnosis_summary))) > 0),
    CONSTRAINT CK_encounters_version CHECK (version_no > 0)
);
CREATE UNIQUE INDEX UX_encounters_appointment ON dbo.encounters(appointment_id) WHERE appointment_id IS NOT NULL;
CREATE INDEX IX_encounters_patient_started ON dbo.encounters(patient_id, started_at DESC) INCLUDE (doctor_id, status, deleted_at);
CREATE INDEX IX_encounters_doctor_started ON dbo.encounters(doctor_id, started_at) INCLUDE (status, deleted_at);

CREATE TABLE dbo.diagnoses (
    diagnosis_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_diagnoses_id DEFAULT NEWSEQUENTIALID(),
    encounter_id UNIQUEIDENTIFIER NOT NULL,
    code VARCHAR(30) NULL,
    name NVARCHAR(500) NOT NULL,
    is_primary BIT NOT NULL CONSTRAINT DF_diagnoses_primary DEFAULT 0,
    notes NVARCHAR(2000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_diagnoses_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_diagnoses_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_diagnoses PRIMARY KEY (diagnosis_id),
    CONSTRAINT FK_diagnoses_encounter FOREIGN KEY (encounter_id) REFERENCES dbo.encounters(encounter_id)
);
CREATE INDEX IX_diagnoses_encounter ON dbo.diagnoses(encounter_id);
CREATE UNIQUE INDEX UX_diagnoses_primary ON dbo.diagnoses(encounter_id) WHERE is_primary = 1 AND deleted_at IS NULL;

CREATE TABLE dbo.clinical_orders (
    order_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_clinical_orders_id DEFAULT NEWSEQUENTIALID(),
    encounter_id UNIQUEIDENTIFIER NOT NULL,
    ordered_by UNIQUEIDENTIFIER NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    name NVARCHAR(300) NOT NULL,
    instructions NVARCHAR(2000) NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_clinical_orders_status DEFAULT 'ordered',
    ordered_at DATETIME2(3) NOT NULL CONSTRAINT DF_clinical_orders_ordered DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_clinical_orders_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_clinical_orders PRIMARY KEY (order_id),
    CONSTRAINT FK_clinical_orders_encounter FOREIGN KEY (encounter_id) REFERENCES dbo.encounters(encounter_id),
    CONSTRAINT FK_clinical_orders_user FOREIGN KEY (ordered_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_clinical_orders_type CHECK (order_type IN ('laboratory', 'imaging', 'other')),
    CONSTRAINT CK_clinical_orders_status CHECK (status IN ('ordered', 'in_progress', 'completed', 'cancelled'))
);
CREATE INDEX IX_clinical_orders_encounter ON dbo.clinical_orders(encounter_id, status);
CREATE INDEX IX_clinical_orders_user ON dbo.clinical_orders(ordered_by);

CREATE TABLE dbo.clinical_results (
    result_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_clinical_results_id DEFAULT NEWSEQUENTIALID(),
    order_id UNIQUEIDENTIFIER NOT NULL,
    entered_by UNIQUEIDENTIFIER NOT NULL,
    result_text NVARCHAR(MAX) NULL,
    numeric_value DECIMAL(18,6) NULL,
    unit NVARCHAR(50) NULL,
    reference_range NVARCHAR(200) NULL,
    file_url NVARCHAR(1000) NULL,
    result_at DATETIME2(3) NOT NULL CONSTRAINT DF_clinical_results_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_clinical_results_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_clinical_results PRIMARY KEY (result_id),
    CONSTRAINT FK_clinical_results_order FOREIGN KEY (order_id) REFERENCES dbo.clinical_orders(order_id),
    CONSTRAINT FK_clinical_results_user FOREIGN KEY (entered_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_clinical_results_value CHECK (result_text IS NOT NULL OR numeric_value IS NOT NULL OR file_url IS NOT NULL)
);
CREATE INDEX IX_clinical_results_order ON dbo.clinical_results(order_id, result_at);
CREATE INDEX IX_clinical_results_user ON dbo.clinical_results(entered_by);

CREATE TABLE dbo.drugs (
    drug_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_drugs_id DEFAULT NEWSEQUENTIALID(),
    drug_code VARCHAR(30) NOT NULL,
    name NVARCHAR(250) NOT NULL,
    active_ingredient NVARCHAR(500) NULL,
    strength NVARCHAR(100) NULL,
    dosage_form NVARCHAR(100) NULL,
    unit NVARCHAR(50) NOT NULL,
    reorder_level DECIMAL(12,3) NOT NULL CONSTRAINT DF_drugs_reorder DEFAULT 0,
    sale_price DECIMAL(19,2) NOT NULL CONSTRAINT DF_drugs_price DEFAULT 0,
    is_active BIT NOT NULL CONSTRAINT DF_drugs_active DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_drugs_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_drugs_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_drugs PRIMARY KEY (drug_id),
    CONSTRAINT UQ_drugs_code UNIQUE (drug_code),
    CONSTRAINT CK_drugs_values CHECK (reorder_level >= 0 AND sale_price >= 0)
);
CREATE INDEX IX_drugs_name ON dbo.drugs(name) INCLUDE (drug_code, is_active) WHERE deleted_at IS NULL;

CREATE TABLE dbo.suppliers (
    supplier_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_suppliers_id DEFAULT NEWSEQUENTIALID(),
    supplier_code VARCHAR(30) NOT NULL,
    name NVARCHAR(250) NOT NULL,
    phone VARCHAR(20) NULL,
    email NVARCHAR(254) NULL,
    address NVARCHAR(500) NULL,
    is_active BIT NOT NULL CONSTRAINT DF_suppliers_active DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_suppliers_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_suppliers_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_suppliers PRIMARY KEY (supplier_id),
    CONSTRAINT UQ_suppliers_code UNIQUE (supplier_code)
);

CREATE TABLE dbo.prescriptions (
    prescription_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_prescriptions_id DEFAULT NEWSEQUENTIALID(),
    encounter_id UNIQUEIDENTIFIER NOT NULL,
    patient_id UNIQUEIDENTIFIER NOT NULL,
    doctor_id UNIQUEIDENTIFIER NOT NULL,
    issued_at DATETIME2(3) NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_prescriptions_status DEFAULT 'draft',
    notes NVARCHAR(2000) NULL,
    version_no INT NOT NULL CONSTRAINT DF_prescriptions_version DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_prescriptions_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_prescriptions_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_prescriptions PRIMARY KEY (prescription_id),
    CONSTRAINT FK_prescriptions_encounter_context FOREIGN KEY (encounter_id, patient_id, doctor_id) REFERENCES dbo.encounters(encounter_id, patient_id, doctor_id),
    CONSTRAINT FK_prescriptions_patient FOREIGN KEY (patient_id) REFERENCES dbo.patients(patient_id),
    CONSTRAINT FK_prescriptions_doctor FOREIGN KEY (doctor_id) REFERENCES dbo.doctors(doctor_id),
    CONSTRAINT CK_prescriptions_status CHECK (status IN ('draft', 'issued', 'dispensed', 'cancelled')),
    CONSTRAINT CK_prescriptions_issue CHECK (status NOT IN ('issued', 'dispensed') OR issued_at IS NOT NULL),
    CONSTRAINT CK_prescriptions_version CHECK (version_no > 0)
);
CREATE INDEX IX_prescriptions_encounter ON dbo.prescriptions(encounter_id);
CREATE INDEX IX_prescriptions_patient ON dbo.prescriptions(patient_id, created_at DESC);
CREATE INDEX IX_prescriptions_doctor ON dbo.prescriptions(doctor_id, status);

CREATE TABLE dbo.prescription_items (
    prescription_item_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_prescription_items_id DEFAULT NEWSEQUENTIALID(),
    prescription_id UNIQUEIDENTIFIER NOT NULL,
    drug_id UNIQUEIDENTIFIER NOT NULL,
    dosage NVARCHAR(200) NOT NULL,
    frequency NVARCHAR(200) NOT NULL,
    route NVARCHAR(100) NOT NULL,
    duration_days SMALLINT NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    instructions NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_prescription_items_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_prescription_items_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_prescription_items PRIMARY KEY (prescription_item_id),
    CONSTRAINT FK_prescription_items_prescription FOREIGN KEY (prescription_id) REFERENCES dbo.prescriptions(prescription_id),
    CONSTRAINT FK_prescription_items_drug FOREIGN KEY (drug_id) REFERENCES dbo.drugs(drug_id),
    CONSTRAINT CK_prescription_items_values CHECK (duration_days > 0 AND quantity > 0)
);
CREATE INDEX IX_prescription_items_prescription ON dbo.prescription_items(prescription_id);
CREATE INDEX IX_prescription_items_drug ON dbo.prescription_items(drug_id);

CREATE TABLE dbo.drug_batches (
    batch_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_drug_batches_id DEFAULT NEWSEQUENTIALID(),
    drug_id UNIQUEIDENTIFIER NOT NULL,
    supplier_id UNIQUEIDENTIFIER NOT NULL,
    batch_no NVARCHAR(80) NOT NULL,
    expiry_date DATE NOT NULL,
    quantity_on_hand DECIMAL(12,3) NOT NULL CONSTRAINT DF_drug_batches_quantity DEFAULT 0,
    purchase_price DECIMAL(19,2) NOT NULL,
    received_at DATETIME2(3) NOT NULL CONSTRAINT DF_drug_batches_received DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_drug_batches PRIMARY KEY (batch_id),
    CONSTRAINT UQ_drug_batches_drug_batch UNIQUE (drug_id, batch_no),
    CONSTRAINT FK_drug_batches_drug FOREIGN KEY (drug_id) REFERENCES dbo.drugs(drug_id),
    CONSTRAINT FK_drug_batches_supplier FOREIGN KEY (supplier_id) REFERENCES dbo.suppliers(supplier_id),
    CONSTRAINT CK_drug_batches_values CHECK (quantity_on_hand >= 0 AND purchase_price >= 0)
);
CREATE INDEX IX_drug_batches_fefo ON dbo.drug_batches(drug_id, expiry_date, received_at) INCLUDE (quantity_on_hand, batch_no);
CREATE INDEX IX_drug_batches_supplier ON dbo.drug_batches(supplier_id);

CREATE TABLE dbo.dispensations (
    dispensation_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_dispensations_id DEFAULT NEWSEQUENTIALID(),
    prescription_id UNIQUEIDENTIFIER NOT NULL,
    pharmacist_user_id UNIQUEIDENTIFIER NOT NULL,
    dispensed_at DATETIME2(3) NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_dispensations_status DEFAULT 'pending',
    notes NVARCHAR(2000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_dispensations_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_dispensations_updated DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_dispensations PRIMARY KEY (dispensation_id),
    CONSTRAINT UQ_dispensations_prescription UNIQUE (prescription_id),
    CONSTRAINT FK_dispensations_prescription FOREIGN KEY (prescription_id) REFERENCES dbo.prescriptions(prescription_id),
    CONSTRAINT FK_dispensations_pharmacist FOREIGN KEY (pharmacist_user_id) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_dispensations_status CHECK (status IN ('pending', 'completed', 'cancelled')),
    CONSTRAINT CK_dispensations_completed CHECK (status <> 'completed' OR dispensed_at IS NOT NULL)
);
CREATE INDEX IX_dispensations_pharmacist ON dbo.dispensations(pharmacist_user_id, dispensed_at);

CREATE TABLE dbo.dispensation_items (
    dispensation_item_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_dispensation_items_id DEFAULT NEWSEQUENTIALID(),
    dispensation_id UNIQUEIDENTIFIER NOT NULL,
    prescription_item_id UNIQUEIDENTIFIER NOT NULL,
    batch_id UNIQUEIDENTIFIER NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    CONSTRAINT PK_dispensation_items PRIMARY KEY (dispensation_item_id),
    CONSTRAINT UQ_dispensation_items_batch UNIQUE (dispensation_id, prescription_item_id, batch_id),
    CONSTRAINT FK_dispensation_items_dispensation FOREIGN KEY (dispensation_id) REFERENCES dbo.dispensations(dispensation_id),
    CONSTRAINT FK_dispensation_items_prescription_item FOREIGN KEY (prescription_item_id) REFERENCES dbo.prescription_items(prescription_item_id),
    CONSTRAINT FK_dispensation_items_batch FOREIGN KEY (batch_id) REFERENCES dbo.drug_batches(batch_id),
    CONSTRAINT CK_dispensation_items_quantity CHECK (quantity > 0)
);
CREATE INDEX IX_dispensation_items_prescription_item ON dbo.dispensation_items(prescription_item_id);
CREATE INDEX IX_dispensation_items_batch ON dbo.dispensation_items(batch_id);

CREATE TABLE dbo.inventory_transactions (
    inventory_txn_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_inventory_transactions_id DEFAULT NEWSEQUENTIALID(),
    batch_id UNIQUEIDENTIFIER NOT NULL,
    performed_by UNIQUEIDENTIFIER NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    reference_type VARCHAR(60) NULL,
    reference_id UNIQUEIDENTIFIER NULL,
    occurred_at DATETIME2(3) NOT NULL CONSTRAINT DF_inventory_transactions_at DEFAULT SYSUTCDATETIME(),
    notes NVARCHAR(2000) NULL,
    CONSTRAINT PK_inventory_transactions PRIMARY KEY (inventory_txn_id),
    CONSTRAINT FK_inventory_transactions_batch FOREIGN KEY (batch_id) REFERENCES dbo.drug_batches(batch_id),
    CONSTRAINT FK_inventory_transactions_user FOREIGN KEY (performed_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_inventory_transactions_type CHECK (transaction_type IN ('receipt', 'dispense', 'adjustment_in', 'adjustment_out', 'return_in', 'return_out')),
    CONSTRAINT CK_inventory_transactions_quantity CHECK (quantity > 0),
    CONSTRAINT CK_inventory_transactions_reference CHECK (reference_type IS NULL AND reference_id IS NULL OR reference_type IS NOT NULL AND reference_id IS NOT NULL),
    CONSTRAINT CK_inventory_transactions_reason CHECK (transaction_type NOT IN ('adjustment_in', 'adjustment_out') OR notes IS NOT NULL AND LEN(LTRIM(RTRIM(notes))) > 0)
);
CREATE INDEX IX_inventory_transactions_batch ON dbo.inventory_transactions(batch_id, occurred_at) INCLUDE (transaction_type, quantity);
CREATE INDEX IX_inventory_transactions_user ON dbo.inventory_transactions(performed_by, occurred_at);
CREATE INDEX IX_inventory_transactions_reference ON dbo.inventory_transactions(reference_type, reference_id);

CREATE TABLE dbo.services (
    service_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_services_id DEFAULT NEWSEQUENTIALID(),
    service_code VARCHAR(30) NOT NULL,
    name NVARCHAR(250) NOT NULL,
    unit_price DECIMAL(19,2) NOT NULL,
    is_active BIT NOT NULL CONSTRAINT DF_services_active DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_services_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_services_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_services PRIMARY KEY (service_id),
    CONSTRAINT UQ_services_code UNIQUE (service_code),
    CONSTRAINT CK_services_price CHECK (unit_price >= 0)
);

CREATE TABLE dbo.invoices (
    invoice_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_invoices_id DEFAULT NEWSEQUENTIALID(),
    invoice_no VARCHAR(40) NOT NULL,
    patient_id UNIQUEIDENTIFIER NOT NULL,
    encounter_id UNIQUEIDENTIFIER NULL,
    issued_by UNIQUEIDENTIFIER NOT NULL,
    issued_at DATETIME2(3) NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_invoices_status DEFAULT 'draft',
    subtotal DECIMAL(19,2) NOT NULL CONSTRAINT DF_invoices_subtotal DEFAULT 0,
    discount DECIMAL(19,2) NOT NULL CONSTRAINT DF_invoices_discount DEFAULT 0,
    total_amount AS CONVERT(DECIMAL(19,2), subtotal - discount) PERSISTED,
    paid_amount DECIMAL(19,2) NOT NULL CONSTRAINT DF_invoices_paid DEFAULT 0,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_invoices_created DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_invoices_updated DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_invoices PRIMARY KEY (invoice_id),
    CONSTRAINT UQ_invoices_number UNIQUE (invoice_no),
    CONSTRAINT FK_invoices_patient FOREIGN KEY (patient_id) REFERENCES dbo.patients(patient_id),
    CONSTRAINT FK_invoices_encounter_patient FOREIGN KEY (encounter_id, patient_id) REFERENCES dbo.encounters(encounter_id, patient_id),
    CONSTRAINT FK_invoices_user FOREIGN KEY (issued_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_invoices_status CHECK (status IN ('draft', 'issued', 'partially_paid', 'paid', 'cancelled')),
    CONSTRAINT CK_invoices_amounts CHECK (subtotal >= 0 AND discount >= 0 AND discount <= subtotal AND paid_amount >= 0 AND paid_amount <= subtotal - discount),
    CONSTRAINT CK_invoices_issued CHECK (status NOT IN ('issued', 'partially_paid', 'paid') OR issued_at IS NOT NULL),
    CONSTRAINT CK_invoices_balance CHECK (
        status IN ('draft', 'issued', 'cancelled') AND paid_amount = 0
        OR status = 'partially_paid' AND paid_amount > 0 AND paid_amount < subtotal - discount
        OR status = 'paid' AND paid_amount = subtotal - discount
    )
);
CREATE INDEX IX_invoices_patient ON dbo.invoices(patient_id, created_at DESC);
CREATE INDEX IX_invoices_encounter ON dbo.invoices(encounter_id) INCLUDE (status, total_amount, paid_amount);
CREATE INDEX IX_invoices_user ON dbo.invoices(issued_by);
CREATE INDEX IX_invoices_status_date ON dbo.invoices(status, issued_at);

CREATE TABLE dbo.invoice_items (
    invoice_item_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_invoice_items_id DEFAULT NEWSEQUENTIALID(),
    invoice_id UNIQUEIDENTIFIER NOT NULL,
    service_id UNIQUEIDENTIFIER NULL,
    drug_id UNIQUEIDENTIFIER NULL,
    item_type VARCHAR(20) NOT NULL,
    description NVARCHAR(500) NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    unit_price DECIMAL(19,2) NOT NULL,
    amount AS CONVERT(DECIMAL(19,2), ROUND(quantity * unit_price, 0)) PERSISTED,
    CONSTRAINT PK_invoice_items PRIMARY KEY (invoice_item_id),
    CONSTRAINT FK_invoice_items_invoice FOREIGN KEY (invoice_id) REFERENCES dbo.invoices(invoice_id),
    CONSTRAINT FK_invoice_items_service FOREIGN KEY (service_id) REFERENCES dbo.services(service_id),
    CONSTRAINT FK_invoice_items_drug FOREIGN KEY (drug_id) REFERENCES dbo.drugs(drug_id),
    CONSTRAINT CK_invoice_items_values CHECK (quantity > 0 AND unit_price >= 0),
    CONSTRAINT CK_invoice_items_source CHECK (
        item_type = 'service' AND service_id IS NOT NULL AND drug_id IS NULL
        OR item_type = 'drug' AND drug_id IS NOT NULL AND service_id IS NULL
    )
);
CREATE INDEX IX_invoice_items_invoice ON dbo.invoice_items(invoice_id) INCLUDE (amount);
CREATE INDEX IX_invoice_items_service ON dbo.invoice_items(service_id);
CREATE INDEX IX_invoice_items_drug ON dbo.invoice_items(drug_id);

CREATE TABLE dbo.payments (
    payment_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_payments_id DEFAULT NEWSEQUENTIALID(),
    invoice_id UNIQUEIDENTIFIER NOT NULL,
    received_by UNIQUEIDENTIFIER NOT NULL,
    payment_method VARCHAR(20) NOT NULL,
    amount DECIMAL(19,2) NOT NULL,
    paid_at DATETIME2(3) NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_payments_status DEFAULT 'pending',
    transaction_ref VARCHAR(100) NOT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_payments_created DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_payments PRIMARY KEY (payment_id),
    CONSTRAINT UQ_payments_transaction UNIQUE (transaction_ref),
    CONSTRAINT FK_payments_invoice FOREIGN KEY (invoice_id) REFERENCES dbo.invoices(invoice_id),
    CONSTRAINT FK_payments_user FOREIGN KEY (received_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_payments_method CHECK (payment_method IN ('cash', 'bank_transfer')),
    CONSTRAINT CK_payments_amount CHECK (amount > 0),
    CONSTRAINT CK_payments_status CHECK (status IN ('pending', 'succeeded', 'failed', 'cancelled')),
    CONSTRAINT CK_payments_succeeded CHECK (status <> 'succeeded' OR paid_at IS NOT NULL),
    CONSTRAINT CK_payments_reference CHECK (LEN(LTRIM(RTRIM(transaction_ref))) > 0)
);
CREATE INDEX IX_payments_invoice ON dbo.payments(invoice_id, status) INCLUDE (amount, paid_at);
CREATE INDEX IX_payments_revenue ON dbo.payments(paid_at, invoice_id) INCLUDE (amount) WHERE status = 'succeeded';
CREATE INDEX IX_payments_user ON dbo.payments(received_by);

CREATE TABLE dbo.notifications (
    notification_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_notifications_id DEFAULT NEWSEQUENTIALID(),
    user_id UNIQUEIDENTIFIER NULL,
    appointment_id UNIQUEIDENTIFIER NULL,
    channel VARCHAR(20) NOT NULL,
    type VARCHAR(60) NOT NULL,
    recipient NVARCHAR(254) NULL,
    subject NVARCHAR(300) NULL,
    content NVARCHAR(MAX) NOT NULL,
    status VARCHAR(20) NOT NULL CONSTRAINT DF_notifications_status DEFAULT 'pending',
    scheduled_at DATETIME2(3) NOT NULL CONSTRAINT DF_notifications_scheduled DEFAULT SYSUTCDATETIME(),
    sent_at DATETIME2(3) NULL,
    read_at DATETIME2(3) NULL,
    retry_count SMALLINT NOT NULL CONSTRAINT DF_notifications_retries DEFAULT 0,
    deduplication_key VARCHAR(200) NOT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_notifications_created DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT PK_notifications PRIMARY KEY (notification_id),
    CONSTRAINT UQ_notifications_deduplication UNIQUE (deduplication_key),
    CONSTRAINT FK_notifications_user FOREIGN KEY (user_id) REFERENCES dbo.users(user_id),
    CONSTRAINT FK_notifications_appointment FOREIGN KEY (appointment_id) REFERENCES dbo.appointments(appointment_id),
    CONSTRAINT CK_notifications_channel CHECK (channel IN ('email', 'sms', 'in_app')),
    CONSTRAINT CK_notifications_status CHECK (status IN ('pending', 'processing', 'sent', 'failed', 'cancelled')),
    CONSTRAINT CK_notifications_retries CHECK (retry_count BETWEEN 0 AND 10),
    CONSTRAINT CK_notifications_recipient CHECK (
        channel = 'in_app' AND user_id IS NOT NULL
        OR channel IN ('email', 'sms') AND recipient IS NOT NULL AND LEN(LTRIM(RTRIM(recipient))) > 0
    ),
    CONSTRAINT CK_notifications_sent CHECK (status <> 'sent' OR sent_at IS NOT NULL)
);
-- Nullable user_id + recipient lets reception notify patients without accounts,
-- matching SRS section 2.2. Recipient is a delivery snapshot, never a SQL secret.
CREATE INDEX IX_notifications_user ON dbo.notifications(user_id, created_at DESC) INCLUDE (read_at, status);
CREATE INDEX IX_notifications_queue ON dbo.notifications(status, scheduled_at) INCLUDE (retry_count, channel);
CREATE INDEX IX_notifications_appointment ON dbo.notifications(appointment_id);

CREATE TABLE dbo.audit_logs (
    audit_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_audit_logs_id DEFAULT NEWSEQUENTIALID(),
    actor_user_id UNIQUEIDENTIFIER NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id UNIQUEIDENTIFIER NULL,
    before_json NVARCHAR(MAX) NULL,
    after_json NVARCHAR(MAX) NULL,
    ip_address VARCHAR(45) NULL,
    user_agent NVARCHAR(512) NULL,
    request_id UNIQUEIDENTIFIER NULL,
    occurred_at DATETIME2(3) NOT NULL CONSTRAINT DF_audit_logs_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_audit_logs PRIMARY KEY (audit_id),
    CONSTRAINT FK_audit_logs_actor FOREIGN KEY (actor_user_id) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_audit_logs_before_json CHECK (before_json IS NULL OR ISJSON(before_json) = 1),
    CONSTRAINT CK_audit_logs_after_json CHECK (after_json IS NULL OR ISJSON(after_json) = 1)
);
CREATE INDEX IX_audit_logs_actor_time ON dbo.audit_logs(actor_user_id, occurred_at DESC);
CREATE INDEX IX_audit_logs_entity_time ON dbo.audit_logs(entity_type, entity_id, occurred_at DESC);
CREATE INDEX IX_audit_logs_request ON dbo.audit_logs(request_id) WHERE request_id IS NOT NULL;

CREATE TABLE dbo.record_versions (
    version_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_record_versions_id DEFAULT NEWSEQUENTIALID(),
    changed_by UNIQUEIDENTIFIER NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id UNIQUEIDENTIFIER NOT NULL,
    version_no INT NOT NULL,
    data_json NVARCHAR(MAX) NOT NULL,
    change_reason NVARCHAR(1000) NOT NULL,
    changed_at DATETIME2(3) NOT NULL CONSTRAINT DF_record_versions_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_record_versions PRIMARY KEY (version_id),
    CONSTRAINT UQ_record_versions_entity_version UNIQUE (entity_type, entity_id, version_no),
    CONSTRAINT FK_record_versions_user FOREIGN KEY (changed_by) REFERENCES dbo.users(user_id),
    CONSTRAINT CK_record_versions_version CHECK (version_no > 0),
    CONSTRAINT CK_record_versions_json CHECK (ISJSON(data_json) = 1),
    CONSTRAINT CK_record_versions_reason CHECK (LEN(LTRIM(RTRIM(change_reason))) > 0)
);
CREATE INDEX IX_record_versions_user ON dbo.record_versions(changed_by, changed_at DESC);

-- updated_at is set explicitly by repositories in the same write transaction.
-- ROWVERSION is managed by SQL Server and is used in UPDATE ... WHERE checks.
-- audit_logs, record_versions and inventory_transactions are append-only for
-- the runtime DB principal; migration/admin credentials must remain separate.
