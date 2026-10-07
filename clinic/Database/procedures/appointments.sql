-- Application transactions own the write lock until BLL commits the change and audit.
-- A single lock makes overlap checks safe across concurrent API workers for this clinic.
CREATE OR ALTER PROCEDURE dbo.clinic_doctor_list
    @page int, @page_size int, @search nvarchar(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @pattern nvarchar(210) = CASE WHEN @search IS NULL OR @search = '' THEN NULL
      ELSE N'%' + REPLACE(REPLACE(REPLACE(REPLACE(@search,N'\',N'\\'),
        N'%',N'\%'),N'_',N'\_'),N'[',N'\[') + N'%' END;
    SELECT d.doctor_id, d.doctor_code, u.username AS doctor_name, d.specialty INTO #doctors
    FROM dbo.doctors d JOIN dbo.users u ON u.user_id=d.user_id
    WHERE d.deleted_at IS NULL AND u.deleted_at IS NULL AND u.is_active=1
      AND (@pattern IS NULL OR d.doctor_code LIKE @pattern ESCAPE '\'
        OR u.username LIKE @pattern ESCAPE '\' OR d.specialty LIKE @pattern ESCAPE '\');
    SELECT COUNT_BIG(*) AS total FROM #doctors;
    SELECT * FROM #doctors ORDER BY doctor_name, doctor_id
    OFFSET (@page-1)*@page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_schedule_list
    @page int, @page_size int, @doctor_id uniqueidentifier = NULL,
    @start_at datetime2 = NULL, @end_at datetime2 = NULL, @status varchar(20) = NULL,
    @schedule_id uniqueidentifier = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT s.*, d.doctor_code, u.username AS doctor_name, d.specialty INTO #schedules
    FROM dbo.doctor_schedules s JOIN dbo.doctors d ON d.doctor_id=s.doctor_id
    JOIN dbo.users u ON u.user_id=d.user_id
    CROSS APPLY (SELECT
      DATEADD(MINUTE,DATEDIFF(MINUTE,CAST('00:00' AS time),s.start_time),
        CAST(s.work_date AS datetime2)) AS starts,
      DATEADD(MINUTE,DATEDIFF(MINUTE,CAST('00:00' AS time),s.end_time),
        CAST(s.work_date AS datetime2)) AS ends) range
    WHERE d.deleted_at IS NULL AND u.deleted_at IS NULL AND u.is_active=1
      AND (@doctor_id IS NULL OR s.doctor_id=@doctor_id)
      AND (@schedule_id IS NULL OR s.schedule_id=@schedule_id)
      AND (@status IS NULL OR s.status=@status)
      AND (@start_at IS NULL OR range.ends>@start_at)
      AND (@end_at IS NULL OR range.starts<@end_at);
    SELECT COUNT_BIG(*) AS total FROM #schedules;
    SELECT * FROM #schedules ORDER BY work_date,start_time,doctor_name,schedule_id
    OFFSET (@page-1)*@page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_schedule_write
    @action varchar(10), @schedule_id uniqueidentifier = NULL,
    @doctor_id uniqueidentifier = NULL, @start_at datetime2 = NULL, @end_at datetime2 = NULL,
    @slot_minutes smallint = 30, @expected_version binary(8) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @@TRANCOUNT=0 THROW 51310,'A transaction is required.',1;
    IF @action NOT IN ('create','cancel') THROW 51303,'Invalid schedule action.',1;
    DECLARE @lock_result int;
    EXEC @lock_result=sys.sp_getapplock @Resource=N'clinic-appointments-write',
      @LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=10000;
    IF @lock_result<0 THROW 51310,'Could not acquire appointment lock.',1;
    IF @action='cancel'
    BEGIN
      DECLARE @current_version binary(8), @current_status varchar(20);
      SELECT @current_version=row_version,@current_status=status
      FROM dbo.doctor_schedules WITH (UPDLOCK,HOLDLOCK) WHERE schedule_id=@schedule_id;
      IF @current_version IS NULL THROW 51301,'Schedule not found.',1;
      IF @expected_version IS NULL OR @expected_version<>@current_version
        THROW 51302,'Version conflict.',1;
      IF @current_status<>'active' THROW 51303,'Schedule is already cancelled.',1;
      IF EXISTS(SELECT 1 FROM dbo.appointments WHERE schedule_id=@schedule_id
        AND deleted_at IS NULL AND status IN ('booked','confirmed','checked_in','in_progress'))
        THROW 51312,'Schedule has active appointments.',1;
      UPDATE dbo.doctor_schedules SET status='cancelled',updated_at=SYSUTCDATETIME()
      WHERE schedule_id=@schedule_id;
    END
    ELSE
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM dbo.doctors d JOIN dbo.users u ON u.user_id=d.user_id
        WHERE d.doctor_id=@doctor_id AND d.deleted_at IS NULL
          AND u.deleted_at IS NULL AND u.is_active=1)
        THROW 51309,'Doctor is unavailable.',1;
      IF @start_at IS NULL OR @end_at IS NULL OR @end_at<=@start_at
        OR @end_at<=SYSUTCDATETIME() OR CAST(@start_at AS date)<>CAST(@end_at AS date)
        OR @slot_minutes NOT BETWEEN 5 AND 240
        OR DATEDIFF(MINUTE,@start_at,@end_at)<@slot_minutes
        OR DATEDIFF(MINUTE,@start_at,@end_at)%@slot_minutes<>0
        THROW 51304,'Invalid schedule time.',1;
      IF EXISTS(SELECT 1 FROM dbo.doctor_schedules WHERE doctor_id=@doctor_id
        AND work_date=CAST(@start_at AS date) AND status='active'
        AND start_time<CAST(@end_at AS time) AND end_time>CAST(@start_at AS time))
        THROW 51311,'Doctor schedules overlap.',1;
      -- Reuse an exactly matching cancelled range because the schema keeps its unique key.
      SELECT @schedule_id=schedule_id FROM dbo.doctor_schedules
      WHERE doctor_id=@doctor_id AND work_date=CAST(@start_at AS date)
        AND start_time=CAST(@start_at AS time) AND end_time=CAST(@end_at AS time)
        AND status='cancelled';
      IF @schedule_id IS NOT NULL
        UPDATE dbo.doctor_schedules SET status='active',slot_minutes=@slot_minutes,
          updated_at=SYSUTCDATETIME() WHERE schedule_id=@schedule_id;
      ELSE
      BEGIN
        DECLARE @created TABLE(id uniqueidentifier);
        INSERT dbo.doctor_schedules(doctor_id,work_date,start_time,end_time,slot_minutes)
        OUTPUT inserted.schedule_id INTO @created
        VALUES(@doctor_id,CAST(@start_at AS date),CAST(@start_at AS time),
          CAST(@end_at AS time),@slot_minutes);
        SELECT @schedule_id=id FROM @created;
      END;
    END;
    SELECT @schedule_id AS schedule_id;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_appointment_list
    @scope varchar(10), @user_id uniqueidentifier, @page int, @page_size int,
    @search nvarchar(100) = NULL, @doctor_id uniqueidentifier = NULL,
    @patient_id uniqueidentifier = NULL, @status varchar(20) = NULL,
    @start_at datetime2 = NULL, @end_at datetime2 = NULL,
    @sort_by varchar(20) = 'appointment_at', @sort_order varchar(4) = 'asc',
    @appointment_id uniqueidentifier = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @scope NOT IN ('all','self','assigned') THROW 51303,'Invalid appointment scope.',1;
    IF @sort_by NOT IN ('appointment_at','created_at','status')
      OR @sort_order NOT IN ('asc','desc') THROW 51303,'Invalid sort.',1;
    DECLARE @pattern nvarchar(210) = CASE WHEN @search IS NULL OR @search='' THEN NULL
      ELSE N'%' + REPLACE(REPLACE(REPLACE(REPLACE(@search,N'\',N'\\'),
        N'%',N'\%'),N'_',N'\_'),N'[',N'\[') + N'%' END;
    SELECT a.*, p.patient_code,p.full_name AS patient_name,d.doctor_code,
      u.username AS doctor_name,d.specialty,
      DATEADD(MINUTE,a.duration_minutes,a.appointment_at) AS ends_at INTO #appointments
    FROM dbo.appointments a JOIN dbo.patients p ON p.patient_id=a.patient_id
    JOIN dbo.doctors d ON d.doctor_id=a.doctor_id JOIN dbo.users u ON u.user_id=d.user_id
    WHERE a.deleted_at IS NULL AND p.deleted_at IS NULL
      AND (@scope='all' OR (@scope='self' AND p.user_id=@user_id)
        OR (@scope='assigned' AND d.user_id=@user_id AND d.deleted_at IS NULL))
      AND (@appointment_id IS NULL OR a.appointment_id=@appointment_id)
      AND (@doctor_id IS NULL OR a.doctor_id=@doctor_id)
      AND (@patient_id IS NULL OR a.patient_id=@patient_id)
      AND (@status IS NULL OR a.status=@status)
      AND (@start_at IS NULL OR a.appointment_at>=@start_at)
      AND (@end_at IS NULL OR a.appointment_at<@end_at)
      AND (@pattern IS NULL OR p.full_name LIKE @pattern ESCAPE '\'
        OR p.patient_code LIKE @pattern ESCAPE '\' OR d.doctor_code LIKE @pattern ESCAPE '\'
        OR u.username LIKE @pattern ESCAPE '\');
    SELECT COUNT_BIG(*) AS total FROM #appointments;
    SELECT * FROM #appointments ORDER BY
      CASE WHEN @sort_by='appointment_at' AND @sort_order='asc' THEN appointment_at END ASC,
      CASE WHEN @sort_by='appointment_at' AND @sort_order='desc' THEN appointment_at END DESC,
      CASE WHEN @sort_by='created_at' AND @sort_order='asc' THEN created_at END ASC,
      CASE WHEN @sort_by='created_at' AND @sort_order='desc' THEN created_at END DESC,
      CASE WHEN @sort_by='status' AND @sort_order='asc' THEN status END ASC,
      CASE WHEN @sort_by='status' AND @sort_order='desc' THEN status END DESC,appointment_id
    OFFSET (@page-1)*@page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_appointment_write
    @action varchar(10), @scope varchar(10), @actor_user_id uniqueidentifier,
    @appointment_id uniqueidentifier = NULL, @patient_id uniqueidentifier = NULL,
    @doctor_id uniqueidentifier = NULL, @schedule_id uniqueidentifier = NULL,
    @appointment_at datetime2 = NULL, @reason nvarchar(1000) = NULL,
    @expected_version binary(8) = NULL, @cancellation_reason nvarchar(1000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @@TRANCOUNT=0 THROW 51310,'A transaction is required.',1;
    IF @action NOT IN ('create','update','cancel') OR @scope NOT IN ('all','self')
      THROW 51303,'Invalid appointment operation.',1;
    DECLARE @lock_result int;
    EXEC @lock_result=sys.sp_getapplock @Resource=N'clinic-appointments-write',
      @LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=10000;
    IF @lock_result<0 THROW 51310,'Could not acquire appointment lock.',1;
    IF @action<>'create'
    BEGIN
      DECLARE @current_version binary(8),@current_status varchar(20),@current_at datetime2;
      SELECT @current_version=a.row_version,@current_status=a.status,
        @patient_id=a.patient_id,@current_at=a.appointment_at
      FROM dbo.appointments a WITH (UPDLOCK,HOLDLOCK)
      JOIN dbo.patients p ON p.patient_id=a.patient_id
      WHERE a.appointment_id=@appointment_id AND a.deleted_at IS NULL AND p.deleted_at IS NULL
        AND (@scope='all' OR p.user_id=@actor_user_id);
      IF @current_version IS NULL THROW 51301,'Appointment not found.',1;
      IF @expected_version IS NULL OR @expected_version<>@current_version
        THROW 51302,'Version conflict.',1;
      IF @current_status NOT IN ('booked','confirmed') OR @current_at<=SYSUTCDATETIME()
        OR EXISTS(SELECT 1 FROM dbo.encounters WHERE appointment_id=@appointment_id)
        THROW 51303,'Appointment cannot be changed in its current state.',1;
    END;
    IF @action='cancel'
    BEGIN
      IF @cancellation_reason IS NULL OR LEN(LTRIM(RTRIM(@cancellation_reason)))<2
        THROW 51303,'Cancellation reason is required.',1;
      UPDATE dbo.appointments SET status='cancelled',cancellation_reason=@cancellation_reason,
        updated_at=SYSUTCDATETIME() WHERE appointment_id=@appointment_id;
      SELECT @appointment_id AS appointment_id;
      RETURN;
    END;
    IF NOT EXISTS(SELECT 1 FROM dbo.patients WHERE patient_id=@patient_id AND deleted_at IS NULL
      AND (@scope='all' OR user_id=@actor_user_id)) THROW 51308,'Patient not found.',1;
    IF NOT EXISTS(SELECT 1 FROM dbo.doctors d JOIN dbo.users u ON u.user_id=d.user_id
      WHERE d.doctor_id=@doctor_id AND d.deleted_at IS NULL
        AND u.deleted_at IS NULL AND u.is_active=1) THROW 51309,'Doctor is unavailable.',1;
    IF @appointment_at IS NULL OR @appointment_at<=SYSUTCDATETIME()
      OR DATEPART(SECOND,@appointment_at)<>0 OR DATEPART(NANOSECOND,@appointment_at)<>0
      THROW 51304,'Appointment time must be in the future, at minute precision.',1;
    DECLARE @start_at datetime2,@end_at datetime2,@duration smallint;
    SELECT @start_at=DATEADD(MINUTE,DATEDIFF(MINUTE,CAST('00:00' AS time),start_time),
      CAST(work_date AS datetime2)),
      @end_at=DATEADD(MINUTE,DATEDIFF(MINUTE,CAST('00:00' AS time),end_time),
        CAST(work_date AS datetime2)),@duration=slot_minutes
    FROM dbo.doctor_schedules WHERE schedule_id=@schedule_id AND doctor_id=@doctor_id
      AND status='active';
    IF @start_at IS NULL OR @appointment_at<@start_at
      OR DATEADD(MINUTE,@duration,@appointment_at)>@end_at
      OR DATEDIFF(MINUTE,@start_at,@appointment_at)%@duration<>0
      THROW 51305,'Appointment is outside an available schedule slot.',1;
    DECLARE @appointment_end datetime2=DATEADD(MINUTE,@duration,@appointment_at);
    -- Strict interval comparison allows adjacent slots but rejects partial overlaps.
    IF EXISTS(SELECT 1 FROM dbo.appointments WHERE doctor_id=@doctor_id AND deleted_at IS NULL
      AND status NOT IN ('cancelled','no_show')
      AND (@appointment_id IS NULL OR appointment_id<>@appointment_id)
      AND appointment_at<@appointment_end
      AND DATEADD(MINUTE,duration_minutes,appointment_at)>@appointment_at)
      THROW 51306,'Doctor appointment overlaps.',1;
    IF EXISTS(SELECT 1 FROM dbo.appointments WHERE patient_id=@patient_id AND deleted_at IS NULL
      AND status NOT IN ('cancelled','no_show')
      AND (@appointment_id IS NULL OR appointment_id<>@appointment_id)
      AND appointment_at<@appointment_end
      AND DATEADD(MINUTE,duration_minutes,appointment_at)>@appointment_at)
      THROW 51307,'Patient appointment overlaps.',1;
    IF @action='create'
    BEGIN
      DECLARE @created TABLE(id uniqueidentifier);
      INSERT dbo.appointments(patient_id,doctor_id,schedule_id,created_by,
        appointment_at,duration_minutes,reason)
      OUTPUT inserted.appointment_id INTO @created
      VALUES(@patient_id,@doctor_id,@schedule_id,@actor_user_id,
        @appointment_at,@duration,@reason);
      SELECT @appointment_id=id FROM @created;
    END
    ELSE
      UPDATE dbo.appointments SET doctor_id=@doctor_id,schedule_id=@schedule_id,
        appointment_at=@appointment_at,duration_minutes=@duration,reason=@reason,
        updated_at=SYSUTCDATETIME() WHERE appointment_id=@appointment_id;
    SELECT @appointment_id AS appointment_id;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_appointment_slots
    @doctor_id uniqueidentifier,@start_at datetime2,@end_at datetime2,
    @patient_id uniqueidentifier = NULL,@exclude_appointment_id uniqueidentifier = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS(SELECT 1 FROM dbo.doctors d JOIN dbo.users u ON u.user_id=d.user_id
      WHERE d.doctor_id=@doctor_id AND d.deleted_at IS NULL
        AND u.deleted_at IS NULL AND u.is_active=1) THROW 51309,'Doctor is unavailable.',1;
    WITH numbers AS (SELECT 0 AS n UNION ALL SELECT n+1 FROM numbers WHERE n<287)
    SELECT s.schedule_id,t.starts AS appointment_at,t.ends AS ends_at,
      s.slot_minutes AS duration_minutes,
      CONVERT(bit,CASE WHEN t.starts<=SYSUTCDATETIME() OR EXISTS(
        SELECT 1 FROM dbo.appointments a WHERE a.deleted_at IS NULL
          AND a.status NOT IN ('cancelled','no_show')
          AND (@exclude_appointment_id IS NULL OR a.appointment_id<>@exclude_appointment_id)
          AND (a.doctor_id=@doctor_id OR a.patient_id=@patient_id)
          AND a.appointment_at<t.ends
          AND DATEADD(MINUTE,a.duration_minutes,a.appointment_at)>t.starts)
        THEN 0 ELSE 1 END) AS available
    FROM dbo.doctor_schedules s CROSS JOIN numbers
    CROSS APPLY(SELECT
      DATEADD(MINUTE,DATEDIFF(MINUTE,CAST('00:00' AS time),s.start_time),
        CAST(s.work_date AS datetime2)) AS starts,
      DATEADD(MINUTE,DATEDIFF(MINUTE,CAST('00:00' AS time),s.end_time),
        CAST(s.work_date AS datetime2)) AS ends) range
    CROSS APPLY(SELECT DATEADD(MINUTE,numbers.n*s.slot_minutes,range.starts) AS starts,
      DATEADD(MINUTE,(numbers.n+1)*s.slot_minutes,range.starts) AS ends) t
    WHERE s.doctor_id=@doctor_id AND s.status='active'
      AND t.starts>=@start_at AND t.starts<@end_at AND t.ends<=range.ends
    ORDER BY t.starts OPTION(MAXRECURSION 300);
END;
GO
