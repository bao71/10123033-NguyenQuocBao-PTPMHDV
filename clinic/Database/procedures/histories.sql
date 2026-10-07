-- Medical history and allergy entries. Access to the patient is checked in BLL
-- through the scoped patient lookup before these procedures are called.
CREATE OR ALTER PROCEDURE dbo.clinic_history_list
    @patient_id uniqueidentifier, @page int, @page_size int,
    @type varchar(30) = NULL, @is_active bit = NULL, @search nvarchar(100) = NULL,
    @sort_by varchar(20) = 'created_at', @sort_order varchar(4) = 'desc'
AS
BEGIN
    SET NOCOUNT ON;
    IF @sort_by NOT IN ('created_at', 'onset_date', 'name')
        THROW 51210, 'Invalid history sort column.', 1;
    IF @sort_order NOT IN ('asc', 'desc') THROW 51211, 'Invalid history sort order.', 1;
    DECLARE @pattern nvarchar(210) = CASE WHEN @search IS NULL OR @search = '' THEN NULL
        ELSE N'%' + REPLACE(REPLACE(REPLACE(REPLACE(@search, N'\', N'\\'),
            N'%', N'\%'), N'_', N'\_'), N'[', N'\[') + N'%' END;
    SELECT COUNT_BIG(*) AS total FROM dbo.medical_histories AS h
    WHERE h.patient_id = @patient_id AND h.deleted_at IS NULL
      AND (@type IS NULL OR h.type = @type)
      AND (@is_active IS NULL OR h.is_active = @is_active)
      AND (@pattern IS NULL OR h.name LIKE @pattern ESCAPE '\'
        OR h.description LIKE @pattern ESCAPE '\');
    SELECT h.history_id, h.patient_id, h.created_by, h.type, h.name, h.description,
        h.onset_date, h.is_active, h.version_no, h.created_at, h.updated_at, h.row_version
    FROM dbo.medical_histories AS h
    WHERE h.patient_id = @patient_id AND h.deleted_at IS NULL
      AND (@type IS NULL OR h.type = @type)
      AND (@is_active IS NULL OR h.is_active = @is_active)
      AND (@pattern IS NULL OR h.name LIKE @pattern ESCAPE '\'
        OR h.description LIKE @pattern ESCAPE '\')
    ORDER BY
      CASE WHEN @sort_by = 'created_at' AND @sort_order = 'asc' THEN h.created_at END ASC,
      CASE WHEN @sort_by = 'created_at' AND @sort_order = 'desc' THEN h.created_at END DESC,
      CASE WHEN @sort_by = 'onset_date' AND @sort_order = 'asc' THEN h.onset_date END ASC,
      CASE WHEN @sort_by = 'onset_date' AND @sort_order = 'desc' THEN h.onset_date END DESC,
      CASE WHEN @sort_by = 'name' AND @sort_order = 'asc' THEN h.name END ASC,
      CASE WHEN @sort_by = 'name' AND @sort_order = 'desc' THEN h.name END DESC,
      h.history_id ASC
    OFFSET (@page - 1) * @page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_history_get
    @patient_id uniqueidentifier, @history_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT h.history_id, h.patient_id, h.created_by, h.type, h.name, h.description,
        h.onset_date, h.is_active, h.version_no, h.created_at, h.updated_at, h.row_version
    FROM dbo.medical_histories AS h
    WHERE h.patient_id = @patient_id AND h.history_id = @history_id AND h.deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_history_lock
    @patient_id uniqueidentifier, @history_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SELECT h.history_id, h.row_version, h.version_no, h.type
    FROM dbo.medical_histories AS h WITH (UPDLOCK, HOLDLOCK)
    WHERE h.patient_id = @patient_id AND h.history_id = @history_id AND h.deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_history_create
    @patient_id uniqueidentifier, @created_by uniqueidentifier, @type varchar(30),
    @name nvarchar(200), @description nvarchar(max), @onset_date date, @is_active bit
AS
BEGIN
    SET NOCOUNT ON;
    INSERT dbo.medical_histories(patient_id, created_by, type, name, description,
        onset_date, is_active)
    OUTPUT inserted.history_id
    VALUES(@patient_id, @created_by, @type, @name, @description, @onset_date, @is_active);
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_history_update
    @patient_id uniqueidentifier, @history_id uniqueidentifier, @type varchar(30),
    @name nvarchar(200), @description nvarchar(max), @onset_date date, @is_active bit
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.medical_histories SET type = @type, name = @name,
        description = @description, onset_date = @onset_date, is_active = @is_active,
        version_no = version_no + 1, updated_at = SYSUTCDATETIME()
    WHERE patient_id = @patient_id AND history_id = @history_id AND deleted_at IS NULL;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_history_delete
    @patient_id uniqueidentifier, @history_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.medical_histories SET deleted_at = SYSUTCDATETIME(),
        updated_at = SYSUTCDATETIME(), version_no = version_no + 1
    WHERE patient_id = @patient_id AND history_id = @history_id AND deleted_at IS NULL;
END;
GO
