CREATE OR ALTER PROCEDURE dbo.clinic_patient_list
    @scope varchar(10), @user_id uniqueidentifier, @page int, @page_size int,
    @search nvarchar(100) = NULL, @gender varchar(20) = NULL, @has_account bit = NULL,
    @sort_by varchar(30) = 'created_at', @sort_order varchar(4) = 'desc'
AS
BEGIN
    SET NOCOUNT ON;
    IF @scope NOT IN ('all', 'self', 'assigned') THROW 51202, 'Invalid patient scope.', 1;
    IF @sort_by NOT IN ('patient_code', 'full_name', 'date_of_birth', 'created_at')
        THROW 51203, 'Invalid patient sort column.', 1;
    IF @sort_order NOT IN ('asc', 'desc') THROW 51204, 'Invalid sort order.', 1;
    DECLARE @pattern nvarchar(210) = NULL;
    IF @search IS NOT NULL AND @search <> ''
        SET @pattern = N'%' + REPLACE(REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(@search)),
            N'\', N'\\'), N'%', N'\%'), N'_', N'\_'), N'[', N'\[') + N'%';
    SELECT p.patient_id INTO #matched
    FROM dbo.patients AS p
    WHERE p.deleted_at IS NULL
      AND (@scope = 'all' OR (@scope = 'self' AND p.user_id = @user_id)
        OR (@scope = 'assigned' AND EXISTS (
            SELECT 1 FROM dbo.doctors AS d WHERE d.user_id = @user_id AND d.deleted_at IS NULL
              AND (EXISTS (SELECT 1 FROM dbo.appointments AS a
                    WHERE a.doctor_id = d.doctor_id AND a.patient_id = p.patient_id
                      AND a.deleted_at IS NULL AND a.status <> 'cancelled')
                OR EXISTS (SELECT 1 FROM dbo.encounters AS e
                    WHERE e.doctor_id = d.doctor_id AND e.patient_id = p.patient_id
                      AND e.deleted_at IS NULL)))))
      AND (@pattern IS NULL OR p.patient_code LIKE @pattern ESCAPE '\'
        OR p.full_name LIKE @pattern ESCAPE '\' OR p.phone LIKE @pattern ESCAPE '\')
      AND (@gender IS NULL OR p.gender = @gender)
      AND (@has_account IS NULL OR (@has_account = 1 AND p.user_id IS NOT NULL)
        OR (@has_account = 0 AND p.user_id IS NULL));
    SELECT COUNT_BIG(*) AS total FROM #matched;
    SELECT p.patient_id, p.patient_code, p.full_name, p.date_of_birth, p.gender,
        p.phone, p.email, p.address, p.insurance_number,
        CONVERT(bit, CASE WHEN p.user_id IS NULL THEN 0 ELSE 1 END) AS has_account,
        p.created_at, p.updated_at, p.row_version
    FROM #matched AS m JOIN dbo.patients AS p ON p.patient_id = m.patient_id
    ORDER BY
        CASE WHEN @sort_by = 'patient_code' AND @sort_order = 'asc' THEN p.patient_code END ASC,
        CASE WHEN @sort_by = 'patient_code' AND @sort_order = 'desc' THEN p.patient_code END DESC,
        CASE WHEN @sort_by = 'full_name' AND @sort_order = 'asc' THEN p.full_name END ASC,
        CASE WHEN @sort_by = 'full_name' AND @sort_order = 'desc' THEN p.full_name END DESC,
        CASE WHEN @sort_by = 'date_of_birth' AND @sort_order = 'asc' THEN p.date_of_birth END ASC,
        CASE WHEN @sort_by = 'date_of_birth' AND @sort_order = 'desc' THEN p.date_of_birth END DESC,
        CASE WHEN @sort_by = 'created_at' AND @sort_order = 'asc' THEN p.created_at END ASC,
        CASE WHEN @sort_by = 'created_at' AND @sort_order = 'desc' THEN p.created_at END DESC,
        p.patient_id ASC
    OFFSET (@page - 1) * @page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_patient_get
    @patient_id uniqueidentifier, @scope varchar(10), @user_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    IF @scope NOT IN ('all', 'self', 'assigned') THROW 51202, 'Invalid patient scope.', 1;
    SELECT p.patient_id, p.patient_code, p.full_name, p.date_of_birth, p.gender,
        p.phone, p.email, p.address, p.insurance_number,
        CONVERT(bit, CASE WHEN p.user_id IS NULL THEN 0 ELSE 1 END) AS has_account,
        p.created_at, p.updated_at, p.row_version
    FROM dbo.patients AS p
    WHERE p.patient_id = @patient_id AND p.deleted_at IS NULL
      AND (@scope = 'all' OR (@scope = 'self' AND p.user_id = @user_id)
        OR (@scope = 'assigned' AND EXISTS (
            SELECT 1 FROM dbo.doctors AS d WHERE d.user_id = @user_id AND d.deleted_at IS NULL
              AND (EXISTS (SELECT 1 FROM dbo.appointments AS a
                    WHERE a.doctor_id = d.doctor_id AND a.patient_id = p.patient_id
                      AND a.deleted_at IS NULL AND a.status <> 'cancelled')
                OR EXISTS (SELECT 1 FROM dbo.encounters AS e
                    WHERE e.doctor_id = d.doctor_id AND e.patient_id = p.patient_id
                      AND e.deleted_at IS NULL)))));
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_patient_create
    @code varchar(30), @full_name nvarchar(200), @date_of_birth date, @gender varchar(20),
    @phone varchar(20), @email nvarchar(254), @address nvarchar(500), @insurance_number varchar(50)
AS
BEGIN
    SET NOCOUNT ON;
    INSERT dbo.patients(patient_code, full_name, date_of_birth, gender, phone, email,
        address, insurance_number) OUTPUT inserted.patient_id
    VALUES(@code, @full_name, @date_of_birth, @gender, @phone, @email,
        @address, @insurance_number);
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_patient_lock @patient_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT patient_id, patient_code, user_id, row_version
    FROM dbo.patients WITH (UPDLOCK, HOLDLOCK)
    WHERE patient_id = @patient_id AND deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_patient_update
    @patient_id uniqueidentifier, @full_name nvarchar(200), @date_of_birth date,
    @gender varchar(20), @phone varchar(20), @email nvarchar(254),
    @address nvarchar(500), @insurance_number varchar(50)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.patients SET full_name = @full_name, date_of_birth = @date_of_birth,
        gender = @gender, phone = @phone, email = @email, address = @address,
        insurance_number = @insurance_number, updated_at = SYSUTCDATETIME()
    WHERE patient_id = @patient_id AND deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_patient_delete
    @patient_id uniqueidentifier, @user_id uniqueidentifier = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.patients SET deleted_at = SYSUTCDATETIME(), updated_at = SYSUTCDATETIME()
    WHERE patient_id = @patient_id AND deleted_at IS NULL;
    IF @user_id IS NOT NULL
    BEGIN
        UPDATE dbo.users SET is_active = 0, auth_version = auth_version + 1,
            deleted_at = COALESCE(deleted_at, SYSUTCDATETIME()), updated_at = SYSUTCDATETIME()
        WHERE user_id = @user_id AND deleted_at IS NULL;
        UPDATE dbo.refresh_tokens SET revoked_at = SYSUTCDATETIME()
        WHERE user_id = @user_id AND revoked_at IS NULL;
    END;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_patient_has_active_care @patient_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT CONVERT(bit, CASE WHEN
        EXISTS (SELECT 1 FROM dbo.appointments WHERE patient_id = @patient_id
            AND deleted_at IS NULL AND status IN ('booked', 'confirmed', 'checked_in', 'in_progress'))
        OR EXISTS (SELECT 1 FROM dbo.encounters WHERE patient_id = @patient_id
            AND deleted_at IS NULL AND status = 'in_progress')
        THEN 1 ELSE 0 END) AS has_active_care;
END;
GO
