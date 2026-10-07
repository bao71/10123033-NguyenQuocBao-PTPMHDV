-- Authentication and audit procedures. Each batch is idempotent for redeployment.
CREATE OR ALTER PROCEDURE dbo.clinic_auth_find_by_login @login nvarchar(254)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP (1) u.user_id, u.username, u.email, u.phone, u.password_hash, u.auth_version,
        r.code AS role, u.is_active, u.created_at,
        CONVERT(bit, CASE WHEN u.locked_until > SYSUTCDATETIME() THEN 1 ELSE 0 END) AS is_locked,
        p.patient_id, p.patient_code, p.full_name
    FROM dbo.users AS u
    JOIN dbo.roles AS r ON r.role_id = u.role_id
    LEFT JOIN dbo.patients AS p ON p.user_id = u.user_id AND p.deleted_at IS NULL
    WHERE u.deleted_at IS NULL AND (u.username = @login OR u.email = @login);
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_find_by_id @user_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT u.user_id, u.username, u.email, u.phone, u.password_hash, u.auth_version,
        r.code AS role, u.is_active, u.created_at,
        CONVERT(bit, CASE WHEN u.locked_until > SYSUTCDATETIME() THEN 1 ELSE 0 END) AS is_locked,
        p.patient_id, p.patient_code, p.full_name
    FROM dbo.users AS u
    JOIN dbo.roles AS r ON r.role_id = u.role_id
    LEFT JOIN dbo.patients AS p ON p.user_id = u.user_id AND p.deleted_at IS NULL
    WHERE u.user_id = @user_id AND u.deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_permissions @user_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT p.code FROM dbo.users AS u
    JOIN dbo.role_permissions AS rp ON rp.role_id = u.role_id
    JOIN dbo.permissions AS p ON p.permission_id = rp.permission_id
    WHERE u.user_id = @user_id AND u.deleted_at IS NULL AND u.is_active = 1
    ORDER BY p.code;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_duplicate
    @username nvarchar(100), @email nvarchar(254), @phone varchar(20) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP (1) CASE WHEN username = @username THEN 'username'
        WHEN email = @email THEN 'email'
        WHEN @phone IS NOT NULL AND phone = @phone THEN 'phone' END AS duplicate_field
    FROM dbo.users
    WHERE deleted_at IS NULL AND
        (username = @username OR email = @email OR (@phone IS NOT NULL AND phone = @phone));
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_create_patient
    @username nvarchar(100), @email nvarchar(254), @phone varchar(20),
    @password_hash varchar(512), @full_name nvarchar(200), @date_of_birth date,
    @gender varchar(20), @patient_code varchar(30)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @role_id uniqueidentifier = (SELECT role_id FROM dbo.roles WHERE code = 'Patient');
    IF @role_id IS NULL THROW 51200, 'Patient role is not configured.', 1;
    DECLARE @created_user table (user_id uniqueidentifier);
    INSERT dbo.users(role_id, username, email, password_hash, phone)
        OUTPUT inserted.user_id INTO @created_user
        VALUES(@role_id, @username, @email, @password_hash, @phone);
    DECLARE @user_id uniqueidentifier = (SELECT user_id FROM @created_user);
    DECLARE @created_patient table (patient_id uniqueidentifier);
    INSERT dbo.patients(user_id, patient_code, full_name, date_of_birth, gender, phone, email)
        OUTPUT inserted.patient_id INTO @created_patient
        VALUES(@user_id, @patient_code, @full_name, @date_of_birth, @gender, @phone, @email);
    SELECT @user_id AS user_id, patient_id FROM @created_patient;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_failed_login
    @user_id uniqueidentifier, @max_failures int, @lock_minutes int
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.users SET failed_login_count = failed_login_count + 1,
        locked_until = CASE WHEN failed_login_count + 1 >= @max_failures
            THEN DATEADD(MINUTE, @lock_minutes, SYSUTCDATETIME()) ELSE locked_until END,
        updated_at = SYSUTCDATETIME() WHERE user_id = @user_id;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_successful_login @user_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.users SET failed_login_count = 0, locked_until = NULL,
        updated_at = SYSUTCDATETIME() WHERE user_id = @user_id;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_insert_refresh
    @user_id uniqueidentifier, @token_hash char(64), @expires_at datetime2(3)
AS
BEGIN
    SET NOCOUNT ON;
    INSERT dbo.refresh_tokens(user_id, token_hash, expires_at)
        VALUES(@user_id, @token_hash, @expires_at);
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_lock_refresh @token_hash char(64)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT t.user_id FROM dbo.refresh_tokens AS t WITH (UPDLOCK, HOLDLOCK)
    JOIN dbo.users AS u ON u.user_id = t.user_id
    WHERE t.token_hash = @token_hash AND t.revoked_at IS NULL
        AND t.expires_at > SYSUTCDATETIME() AND u.is_active = 1 AND u.deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_revoke_refresh
    @token_hash char(64), @user_id uniqueidentifier = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.refresh_tokens SET revoked_at = COALESCE(revoked_at, SYSUTCDATETIME())
    WHERE token_hash = @token_hash AND revoked_at IS NULL
        AND (@user_id IS NULL OR user_id = @user_id);
    SELECT CONVERT(bit, CASE WHEN @@ROWCOUNT > 0 THEN 1 ELSE 0 END) AS revoked;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_revoke_all_refresh @user_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.refresh_tokens SET revoked_at = COALESCE(revoked_at, SYSUTCDATETIME())
    WHERE user_id = @user_id AND revoked_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_invalidate_resets @user_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.password_reset_tokens SET used_at = SYSUTCDATETIME()
    WHERE user_id = @user_id AND used_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_insert_reset
    @user_id uniqueidentifier, @token_hash char(64), @expires_at datetime2(3)
AS
BEGIN
    SET NOCOUNT ON;
    INSERT dbo.password_reset_tokens(user_id, token_hash, expires_at)
        VALUES(@user_id, @token_hash, @expires_at);
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_lock_reset @token_hash char(64)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT t.user_id FROM dbo.password_reset_tokens AS t WITH (UPDLOCK, HOLDLOCK)
    JOIN dbo.users AS u ON u.user_id = t.user_id
    WHERE t.token_hash = @token_hash AND t.used_at IS NULL
        AND t.expires_at > SYSUTCDATETIME() AND u.is_active = 1 AND u.deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_auth_update_password
    @user_id uniqueidentifier, @password_hash varchar(512)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.users SET password_hash = @password_hash, auth_version = auth_version + 1,
        failed_login_count = 0, locked_until = NULL, updated_at = SYSUTCDATETIME()
    WHERE user_id = @user_id AND is_active = 1 AND deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_audit_insert
    @actor_user_id uniqueidentifier, @action varchar(120), @entity_type varchar(120),
    @entity_id uniqueidentifier, @after_json nvarchar(max), @ip_address varchar(45),
    @user_agent nvarchar(512), @request_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    INSERT dbo.audit_logs(actor_user_id, action, entity_type, entity_id, after_json,
        ip_address, user_agent, request_id)
    VALUES(@actor_user_id, @action, @entity_type, @entity_id, @after_json,
        @ip_address, @user_agent, @request_id);
END;
GO
