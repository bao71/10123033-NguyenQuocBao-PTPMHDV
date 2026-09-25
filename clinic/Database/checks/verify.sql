SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @required_tables TABLE (table_name sysname PRIMARY KEY);
INSERT INTO @required_tables(table_name) VALUES
    (N'roles'), (N'permissions'), (N'role_permissions'), (N'users'),
    (N'refresh_tokens'), (N'password_reset_tokens'), (N'patients'),
    (N'doctors'), (N'doctor_schedules'), (N'appointments'),
    (N'medical_histories'), (N'encounters'), (N'diagnoses'),
    (N'clinical_orders'), (N'clinical_results'), (N'prescriptions'),
    (N'prescription_items'), (N'drugs'), (N'suppliers'), (N'drug_batches'),
    (N'dispensations'), (N'dispensation_items'), (N'inventory_transactions'),
    (N'services'), (N'invoices'), (N'invoice_items'), (N'payments'),
    (N'notifications'), (N'audit_logs'), (N'record_versions'),
    (N'schema_migrations');

IF EXISTS (
    SELECT 1 FROM @required_tables required
    WHERE OBJECT_ID(N'dbo.' + required.table_name, N'U') IS NULL
)
    THROW 51100, 'One or more required tables are missing.', 1;

IF (SELECT COUNT(*) FROM dbo.schema_migrations
    WHERE version IN (N'001_initial_schema.sql', N'002_reference_data.sql', N'003_runtime_security.sql')) <> 3
    THROW 51101, 'Expected migrations have not all been applied.', 1;

IF (SELECT COUNT(*) FROM dbo.roles
    WHERE code IN ('Admin', 'Receptionist', 'Doctor', 'Pharmacist', 'Patient')) <> 5
    THROW 51102, 'The five required roles are not seeded.', 1;

IF EXISTS (
    SELECT 1 FROM dbo.roles role_item
    WHERE NOT EXISTS (SELECT 1 FROM dbo.role_permissions grant_item WHERE grant_item.role_id = role_item.role_id)
)
    THROW 51103, 'At least one role has no permissions.', 1;

IF (SELECT COUNT(*) FROM dbo.services) < 5
    THROW 51104, 'Reference services are missing.', 1;

IF EXISTS (
    SELECT 1 FROM sys.foreign_keys WHERE is_disabled = 1 OR is_not_trusted = 1
)
    THROW 51105, 'A foreign key is disabled or untrusted.', 1;

IF EXISTS (
    SELECT 1 FROM sys.check_constraints WHERE is_disabled = 1 OR is_not_trusted = 1
)
    THROW 51106, 'A CHECK constraint is disabled or untrusted.', 1;

IF DATABASE_PRINCIPAL_ID(N'clinic_app_role') IS NULL
    THROW 51107, 'Runtime database role is missing.', 1;

SELECT
    DB_NAME() AS database_name,
    (SELECT COUNT(*) FROM sys.tables WHERE schema_id = SCHEMA_ID(N'dbo')) AS table_count,
    (SELECT COUNT(*) FROM sys.foreign_keys) AS foreign_key_count,
    (SELECT COUNT(*) FROM sys.check_constraints) AS check_constraint_count,
    (SELECT COUNT(*) FROM sys.indexes WHERE index_id > 0 AND is_hypothetical = 0) AS index_count,
    (SELECT COUNT(*) FROM dbo.permissions) AS permission_count,
    (SELECT COUNT(*) FROM dbo.role_permissions) AS role_permission_count;

PRINT N'PASS: database structure, reference data and constraints are valid.';
