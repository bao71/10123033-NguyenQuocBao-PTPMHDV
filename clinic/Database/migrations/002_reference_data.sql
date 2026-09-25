-- Reference data only: no staff accounts, passwords or real patient records.
-- Permissions name both the action and the record scope. The API must implement
-- *_self, *_assigned, *_billing and *_dispensing predicates explicitly; a grant
-- alone never authorizes access to every row. Admin receives no clinical edits.

INSERT INTO dbo.roles (role_id, code, name, description)
SELECT source.role_id, source.code, source.name, source.description
FROM (VALUES
    (CONVERT(UNIQUEIDENTIFIER, '10000000-0000-0000-0000-000000000001'), 'Admin', N'Quản trị viên', N'Quản lý tài khoản, phân quyền, danh mục dịch vụ, audit và báo cáo.'),
    (CONVERT(UNIQUEIDENTIFIER, '10000000-0000-0000-0000-000000000002'), 'Receptionist', N'Lễ tân', N'Hồ sơ hành chính, lịch hẹn, tiếp nhận, lập hóa đơn và thu phí.'),
    (CONVERT(UNIQUEIDENTIFIER, '10000000-0000-0000-0000-000000000003'), 'Doctor', N'Bác sĩ', N'Khám, cận lâm sàng, chẩn đoán và kê đơn theo ca được phân công.'),
    (CONVERT(UNIQUEIDENTIFIER, '10000000-0000-0000-0000-000000000004'), 'Pharmacist', N'Dược sĩ', N'Danh mục thuốc, nhà cung cấp, lô thuốc, tồn kho và cấp thuốc.'),
    (CONVERT(UNIQUEIDENTIFIER, '10000000-0000-0000-0000-000000000005'), 'Patient', N'Bệnh nhân', N'Lịch hẹn và thông tin được công bố thuộc hồ sơ của bản thân.')
) AS source(role_id, code, name, description)
WHERE NOT EXISTS (SELECT 1 FROM dbo.roles AS target WHERE target.code = source.code);

DECLARE @permission_seed TABLE (code VARCHAR(120) PRIMARY KEY, resource VARCHAR(60), action VARCHAR(60));
INSERT INTO @permission_seed (code, resource, action) VALUES
    ('accounts.read_self', 'accounts', 'read_self'),
    ('accounts.update_self', 'accounts', 'update_self'),
    ('accounts.change_password', 'accounts', 'change_password'),
    ('users.read', 'users', 'read'),
    ('users.create', 'users', 'create'),
    ('users.update', 'users', 'update'),
    ('users.deactivate', 'users', 'deactivate'),
    ('roles.read', 'roles', 'read'),
    ('roles.update', 'roles', 'update'),
    ('patients.read', 'patients', 'read'),
    ('patients.read_assigned', 'patients', 'read_assigned'),
    ('patients.read_self', 'patients', 'read_self'),
    ('patients.create', 'patients', 'create'),
    ('patients.update', 'patients', 'update'),
    ('patients.delete', 'patients', 'delete'),
    ('patients.import', 'patients', 'import'),
    ('patients.export', 'patients', 'export'),
    ('medical_histories.read_assigned', 'medical_histories', 'read_assigned'),
    ('medical_histories.write_assigned', 'medical_histories', 'write_assigned'),
    ('medical_histories.read_self', 'medical_histories', 'read_self'),
    ('doctors.read', 'doctors', 'read'),
    ('doctors.manage', 'doctors', 'manage'),
    ('doctor_schedules.read', 'doctor_schedules', 'read'),
    ('doctor_schedules.manage', 'doctor_schedules', 'manage'),
    ('appointments.read', 'appointments', 'read'),
    ('appointments.read_assigned', 'appointments', 'read_assigned'),
    ('appointments.read_self', 'appointments', 'read_self'),
    ('appointments.create', 'appointments', 'create'),
    ('appointments.create_self', 'appointments', 'create_self'),
    ('appointments.update', 'appointments', 'update'),
    ('appointments.update_self', 'appointments', 'update_self'),
    ('appointments.cancel', 'appointments', 'cancel'),
    ('appointments.cancel_self', 'appointments', 'cancel_self'),
    ('appointments.check_in', 'appointments', 'check_in'),
    ('appointments.export', 'appointments', 'export'),
    ('encounters.read_assigned', 'encounters', 'read_assigned'),
    ('encounters.read_self', 'encounters', 'read_self'),
    ('encounters.create_assigned', 'encounters', 'create_assigned'),
    ('encounters.update_assigned', 'encounters', 'update_assigned'),
    ('encounters.complete_assigned', 'encounters', 'complete_assigned'),
    ('encounters.amend_assigned', 'encounters', 'amend_assigned'),
    ('encounters.export_assigned', 'encounters', 'export_assigned'),
    ('clinical_orders.write_assigned', 'clinical_orders', 'write_assigned'),
    ('clinical_results.write_assigned', 'clinical_results', 'write_assigned'),
    ('clinical_results.read_self', 'clinical_results', 'read_self'),
    ('prescriptions.read_assigned', 'prescriptions', 'read_assigned'),
    ('prescriptions.read_self', 'prescriptions', 'read_self'),
    ('prescriptions.read_billing', 'prescriptions', 'read_billing'),
    ('prescriptions.read_dispensing', 'prescriptions', 'read_dispensing'),
    ('prescriptions.write_assigned', 'prescriptions', 'write_assigned'),
    ('prescriptions.issue_assigned', 'prescriptions', 'issue_assigned'),
    ('prescriptions.export_assigned', 'prescriptions', 'export_assigned'),
    ('prescriptions.export_self', 'prescriptions', 'export_self'),
    ('drugs.read', 'drugs', 'read'),
    ('drugs.create', 'drugs', 'create'),
    ('drugs.update', 'drugs', 'update'),
    ('drugs.delete', 'drugs', 'delete'),
    ('drugs.import', 'drugs', 'import'),
    ('drugs.export', 'drugs', 'export'),
    ('suppliers.read', 'suppliers', 'read'),
    ('suppliers.manage', 'suppliers', 'manage'),
    ('inventory.read', 'inventory', 'read'),
    ('inventory.receive', 'inventory', 'receive'),
    ('inventory.adjust', 'inventory', 'adjust'),
    ('inventory.export', 'inventory', 'export'),
    ('dispensations.read', 'dispensations', 'read'),
    ('dispensations.create', 'dispensations', 'create'),
    ('services.read', 'services', 'read'),
    ('services.manage', 'services', 'manage'),
    ('invoices.read', 'invoices', 'read'),
    ('invoices.read_assigned', 'invoices', 'read_assigned'),
    ('invoices.read_dispensing', 'invoices', 'read_dispensing'),
    ('invoices.read_self', 'invoices', 'read_self'),
    ('invoices.create', 'invoices', 'create'),
    ('invoices.update', 'invoices', 'update'),
    ('invoices.cancel', 'invoices', 'cancel'),
    ('invoices.export', 'invoices', 'export'),
    ('invoices.export_self', 'invoices', 'export_self'),
    ('payments.create', 'payments', 'create'),
    ('reports.doctor_revenue_read', 'reports', 'doctor_revenue_read'),
    ('reports.doctor_revenue_export', 'reports', 'doctor_revenue_export'),
    ('notifications.read_self', 'notifications', 'read_self'),
    ('notifications.mark_read_self', 'notifications', 'mark_read_self'),
    ('audit_logs.read', 'audit_logs', 'read'),
    ('audit_logs.export', 'audit_logs', 'export'),
    ('record_versions.read_assigned', 'record_versions', 'read_assigned');

INSERT INTO dbo.permissions (code, resource, action)
SELECT source.code, source.resource, source.action
FROM @permission_seed AS source
WHERE NOT EXISTS (SELECT 1 FROM dbo.permissions AS target WHERE target.code = source.code);

DECLARE @grants TABLE (role_code VARCHAR(40), permission_code VARCHAR(120), PRIMARY KEY (role_code, permission_code));
-- Shared self-account capabilities are listed against these exact five roles;
-- future roles receive no automatic grants from this migration.
INSERT INTO @grants (role_code, permission_code)
SELECT r.role_code, p.permission_code
FROM (VALUES ('Admin'), ('Receptionist'), ('Doctor'), ('Pharmacist'), ('Patient')) AS r(role_code)
CROSS JOIN (VALUES
    ('accounts.read_self'), ('accounts.update_self'), ('accounts.change_password'),
    ('notifications.read_self'), ('notifications.mark_read_self')
) AS p(permission_code);

INSERT INTO @grants (role_code, permission_code) VALUES
    ('Admin', 'users.read'),
    ('Admin', 'users.create'),
    ('Admin', 'users.update'),
    ('Admin', 'users.deactivate'),
    ('Admin', 'roles.read'),
    ('Admin', 'roles.update'),
    ('Admin', 'patients.read'),
    ('Admin', 'doctors.read'),
    ('Admin', 'doctors.manage'),
    ('Admin', 'doctor_schedules.read'),
    ('Admin', 'doctor_schedules.manage'),
    ('Admin', 'appointments.read'),
    ('Admin', 'drugs.read'),
    ('Admin', 'inventory.read'),
    ('Admin', 'services.read'),
    ('Admin', 'services.manage'),
    ('Admin', 'reports.doctor_revenue_read'),
    ('Admin', 'reports.doctor_revenue_export'),
    ('Admin', 'audit_logs.read'),
    ('Admin', 'audit_logs.export'),

    ('Receptionist', 'patients.read'),
    ('Receptionist', 'patients.create'),
    ('Receptionist', 'patients.update'),
    ('Receptionist', 'patients.delete'),
    ('Receptionist', 'patients.import'),
    ('Receptionist', 'patients.export'),
    ('Receptionist', 'doctors.read'),
    ('Receptionist', 'doctor_schedules.read'),
    ('Receptionist', 'doctor_schedules.manage'),
    ('Receptionist', 'appointments.read'),
    ('Receptionist', 'appointments.create'),
    ('Receptionist', 'appointments.update'),
    ('Receptionist', 'appointments.cancel'),
    ('Receptionist', 'appointments.check_in'),
    ('Receptionist', 'appointments.export'),
    ('Receptionist', 'prescriptions.read_billing'),
    ('Receptionist', 'services.read'),
    ('Receptionist', 'invoices.read'),
    ('Receptionist', 'invoices.create'),
    ('Receptionist', 'invoices.update'),
    ('Receptionist', 'invoices.cancel'),
    ('Receptionist', 'invoices.export'),
    ('Receptionist', 'payments.create'),

    ('Doctor', 'patients.read_assigned'),
    ('Doctor', 'medical_histories.read_assigned'),
    ('Doctor', 'medical_histories.write_assigned'),
    ('Doctor', 'doctors.read'),
    ('Doctor', 'doctor_schedules.read'),
    ('Doctor', 'appointments.read_assigned'),
    ('Doctor', 'encounters.read_assigned'),
    ('Doctor', 'encounters.create_assigned'),
    ('Doctor', 'encounters.update_assigned'),
    ('Doctor', 'encounters.complete_assigned'),
    ('Doctor', 'encounters.amend_assigned'),
    ('Doctor', 'encounters.export_assigned'),
    ('Doctor', 'clinical_orders.write_assigned'),
    ('Doctor', 'clinical_results.write_assigned'),
    ('Doctor', 'prescriptions.read_assigned'),
    ('Doctor', 'prescriptions.write_assigned'),
    ('Doctor', 'prescriptions.issue_assigned'),
    ('Doctor', 'prescriptions.export_assigned'),
    ('Doctor', 'drugs.read'),
    ('Doctor', 'services.read'),
    ('Doctor', 'invoices.read_assigned'),
    ('Doctor', 'record_versions.read_assigned'),

    ('Pharmacist', 'prescriptions.read_dispensing'),
    ('Pharmacist', 'drugs.read'),
    ('Pharmacist', 'drugs.create'),
    ('Pharmacist', 'drugs.update'),
    ('Pharmacist', 'drugs.delete'),
    ('Pharmacist', 'drugs.import'),
    ('Pharmacist', 'drugs.export'),
    ('Pharmacist', 'suppliers.read'),
    ('Pharmacist', 'suppliers.manage'),
    ('Pharmacist', 'inventory.read'),
    ('Pharmacist', 'inventory.receive'),
    ('Pharmacist', 'inventory.adjust'),
    ('Pharmacist', 'inventory.export'),
    ('Pharmacist', 'dispensations.read'),
    ('Pharmacist', 'dispensations.create'),
    ('Pharmacist', 'invoices.read_dispensing'),

    ('Patient', 'patients.read_self'),
    ('Patient', 'medical_histories.read_self'),
    ('Patient', 'doctors.read'),
    ('Patient', 'doctor_schedules.read'),
    ('Patient', 'appointments.read_self'),
    ('Patient', 'appointments.create_self'),
    ('Patient', 'appointments.update_self'),
    ('Patient', 'appointments.cancel_self'),
    ('Patient', 'encounters.read_self'),
    ('Patient', 'clinical_results.read_self'),
    ('Patient', 'prescriptions.read_self'),
    ('Patient', 'prescriptions.export_self'),
    ('Patient', 'services.read'),
    ('Patient', 'invoices.read_self'),
    ('Patient', 'invoices.export_self');

-- Fail loudly instead of silently dropping a misspelled permission/role grant.
IF EXISTS (
    SELECT 1 FROM @grants AS g
    LEFT JOIN dbo.roles AS r ON r.code = g.role_code
    LEFT JOIN dbo.permissions AS p ON p.code = g.permission_code
    WHERE r.role_id IS NULL OR p.permission_id IS NULL
)
    THROW 51002, 'Reference seed contains an unknown role or permission.', 1;

INSERT INTO dbo.role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM @grants AS g
JOIN dbo.roles AS r ON r.code = g.role_code
JOIN dbo.permissions AS p ON p.code = g.permission_code
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.role_permissions AS existing
    WHERE existing.role_id = r.role_id AND existing.permission_id = p.permission_id
);

-- Demonstration service prices only; the clinic can edit this catalog later.
INSERT INTO dbo.services (service_code, name, unit_price)
SELECT source.service_code, source.name, source.unit_price
FROM (VALUES
    ('CONSULTATION', N'Khám tổng quát', CONVERT(DECIMAL(19,2), 150000)),
    ('FOLLOW_UP', N'Khám tái khám', CONVERT(DECIMAL(19,2), 100000)),
    ('CBC', N'Xét nghiệm công thức máu', CONVERT(DECIMAL(19,2), 100000)),
    ('URINALYSIS', N'Xét nghiệm nước tiểu', CONVERT(DECIMAL(19,2), 60000)),
    ('ULTRASOUND', N'Siêu âm tổng quát', CONVERT(DECIMAL(19,2), 200000))
) AS source(service_code, name, unit_price)
WHERE NOT EXISTS (SELECT 1 FROM dbo.services AS target WHERE target.service_code = source.service_code);
