-- Runtime application principal receives data access but no schema ownership.
-- The login/user itself is provisioned after migrations from local .env secrets.
CREATE ROLE clinic_app_role AUTHORIZATION dbo;

GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO clinic_app_role;

-- These ledgers are append-only for the application. Administrators and the
-- migration principal retain maintenance access outside normal API requests.
DENY UPDATE, DELETE ON dbo.audit_logs TO clinic_app_role;
DENY UPDATE, DELETE ON dbo.record_versions TO clinic_app_role;
DENY UPDATE, DELETE ON dbo.inventory_transactions TO clinic_app_role;
DENY INSERT, UPDATE, DELETE ON dbo.schema_migrations TO clinic_app_role;
