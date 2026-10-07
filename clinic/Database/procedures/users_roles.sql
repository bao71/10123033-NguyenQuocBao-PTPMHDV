CREATE OR ALTER PROCEDURE dbo.clinic_user_create_staff
    @username nvarchar(100), @email nvarchar(254), @password_hash varchar(512),
    @phone varchar(20), @role varchar(40), @doctor_code varchar(30),
    @specialty nvarchar(200), @license_number nvarchar(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @created table (user_id uniqueidentifier);
    INSERT dbo.users(role_id, username, email, password_hash, phone)
        OUTPUT inserted.user_id INTO @created
        SELECT role_id, @username, @email, @password_hash, @phone
        FROM dbo.roles WHERE code = @role;
    DECLARE @user_id uniqueidentifier = (SELECT user_id FROM @created);
    IF @user_id IS NOT NULL AND @role = 'Doctor'
        INSERT dbo.doctors(user_id, doctor_code, specialty, license_number)
        VALUES(@user_id, @doctor_code, @specialty, @license_number);
    SELECT @user_id AS user_id WHERE @user_id IS NOT NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_user_lock @user_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT u.is_active, r.code AS role FROM dbo.users AS u WITH (UPDLOCK, HOLDLOCK)
    JOIN dbo.roles AS r ON r.role_id = u.role_id
    WHERE u.user_id = @user_id AND u.deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_user_set_status @user_id uniqueidentifier, @is_active bit
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.users SET is_active = @is_active, auth_version = auth_version + 1,
        updated_at = SYSUTCDATETIME()
    WHERE user_id = @user_id AND deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_user_list
    @page int, @page_size int, @search nvarchar(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @pattern nvarchar(204) = CASE WHEN @search IS NULL OR @search = '' THEN NULL
        ELSE N'%' + REPLACE(REPLACE(@search, N'%', N'[%]'), N'_', N'[_]') + N'%' END;
    SELECT COUNT_BIG(*) AS total FROM dbo.users AS u
    WHERE u.deleted_at IS NULL AND (@pattern IS NULL OR
        u.username LIKE @pattern OR u.email LIKE @pattern OR u.phone LIKE @pattern);
    SELECT u.user_id, u.username, u.email, u.phone, r.code AS role, u.is_active, u.created_at
    FROM dbo.users AS u JOIN dbo.roles AS r ON r.role_id = u.role_id
    WHERE u.deleted_at IS NULL AND (@pattern IS NULL OR
        u.username LIKE @pattern OR u.email LIKE @pattern OR u.phone LIKE @pattern)
    ORDER BY u.created_at DESC, u.user_id
    OFFSET (@page - 1) * @page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_role_list
AS
BEGIN
    SET NOCOUNT ON;
    SELECT code, name, description FROM dbo.roles ORDER BY name;
    SELECT code FROM dbo.permissions ORDER BY code;
    SELECT r.code AS role_code, p.code AS permission_code FROM dbo.role_permissions AS rp
    JOIN dbo.roles AS r ON r.role_id = rp.role_id
    JOIN dbo.permissions AS p ON p.permission_id = rp.permission_id ORDER BY p.code;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_role_lock @role_code varchar(40)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT role_id FROM dbo.roles WITH (UPDLOCK, HOLDLOCK) WHERE code = @role_code;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_role_permission_codes
AS
BEGIN
    SET NOCOUNT ON;
    SELECT code FROM dbo.permissions;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_role_granted_codes @role_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT p.code FROM dbo.role_permissions AS rp
    JOIN dbo.permissions AS p ON p.permission_id = rp.permission_id
    WHERE rp.role_id = @role_id ORDER BY p.code;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_role_replace_permissions
    @role_id uniqueidentifier, @permissions_json nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    IF ISJSON(@permissions_json) <> 1 THROW 51201, 'Invalid permissions JSON.', 1;
    DELETE FROM dbo.role_permissions WHERE role_id = @role_id;
    INSERT dbo.role_permissions(role_id, permission_id)
        SELECT @role_id, p.permission_id FROM OPENJSON(@permissions_json) AS item
        JOIN dbo.permissions AS p ON p.code = item.value;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_admin_create
    @username nvarchar(100), @email nvarchar(254), @password_hash varchar(512)
AS
BEGIN
    SET NOCOUNT ON;
    INSERT dbo.users(role_id, username, email, password_hash)
        OUTPUT inserted.user_id
        SELECT role_id, @username, @email, @password_hash FROM dbo.roles WHERE code = 'Admin';
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_health_ready
AS
BEGIN
    SET NOCOUNT ON;
    SELECT 1 AS ready;
END;
GO
