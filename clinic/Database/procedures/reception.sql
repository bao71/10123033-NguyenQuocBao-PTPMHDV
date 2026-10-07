CREATE OR ALTER PROCEDURE dbo.clinic_reception_list
    @start_at datetime2, @end_at datetime2, @page int, @page_size int,
    @search nvarchar(100) = NULL, @doctor_id uniqueidentifier = NULL,
    @status varchar(20) = NULL, @sort_order varchar(4) = 'asc'
AS
BEGIN
    SET NOCOUNT ON;
    IF @sort_order NOT IN ('asc','desc') THROW 51313,'Invalid sort order.',1;
    DECLARE @pattern nvarchar(210) = CASE WHEN @search IS NULL OR @search='' THEN NULL
      ELSE N'%' + REPLACE(REPLACE(REPLACE(REPLACE(@search,N'\',N'\\'),
        N'%',N'\%'),N'_',N'\_'),N'[',N'\[') + N'%' END;
    SELECT a.*,p.patient_code,p.full_name AS patient_name,d.doctor_code,
      u.username AS doctor_name,d.specialty,
      DATEADD(MINUTE,a.duration_minutes,a.appointment_at) AS ends_at INTO #reception
    FROM dbo.appointments a JOIN dbo.patients p ON p.patient_id=a.patient_id
    JOIN dbo.doctors d ON d.doctor_id=a.doctor_id JOIN dbo.users u ON u.user_id=d.user_id
    WHERE a.deleted_at IS NULL AND p.deleted_at IS NULL
      AND a.appointment_at>=@start_at AND a.appointment_at<@end_at
      AND (@doctor_id IS NULL OR a.doctor_id=@doctor_id)
      AND (@pattern IS NULL OR p.full_name LIKE @pattern ESCAPE '\'
        OR p.patient_code LIKE @pattern ESCAPE '\' OR d.doctor_code LIKE @pattern ESCAPE '\'
        OR u.username LIKE @pattern ESCAPE '\');
    -- Totals describe the selected day/doctor/search, irrespective of page or status.
    SELECT COUNT_BIG(*) AS total,
      COALESCE(SUM(CASE WHEN status='booked' THEN CAST(1 AS bigint) ELSE 0 END),0) AS booked,
      COALESCE(SUM(CASE WHEN status='confirmed' THEN CAST(1 AS bigint) ELSE 0 END),0) AS confirmed,
      COALESCE(SUM(CASE WHEN status='checked_in' THEN CAST(1 AS bigint) ELSE 0 END),0) AS checked_in,
      COALESCE(SUM(CASE WHEN status='in_progress' THEN CAST(1 AS bigint) ELSE 0 END),0) AS in_progress,
      COALESCE(SUM(CASE WHEN status='completed' THEN CAST(1 AS bigint) ELSE 0 END),0) AS completed,
      COALESCE(SUM(CASE WHEN status='cancelled' THEN CAST(1 AS bigint) ELSE 0 END),0) AS cancelled,
      COALESCE(SUM(CASE WHEN status='no_show' THEN CAST(1 AS bigint) ELSE 0 END),0) AS no_show FROM #reception;
    SELECT COUNT_BIG(*) AS total FROM #reception WHERE @status IS NULL OR status=@status;
    SELECT * FROM #reception WHERE @status IS NULL OR status=@status ORDER BY
      CASE WHEN @sort_order='asc' THEN appointment_at END ASC,
      CASE WHEN @sort_order='desc' THEN appointment_at END DESC,appointment_id
    OFFSET (@page-1)*@page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_appointment_receive
    @appointment_id uniqueidentifier, @target_status varchar(20), @expected_version binary(8)
AS
BEGIN
    SET NOCOUNT ON;
    IF @@TRANCOUNT=0 THROW 51310,'A transaction is required.',1;
    IF @target_status NOT IN ('confirmed','checked_in','no_show')
      THROW 51313,'Invalid reception action.',1;
    DECLARE @lock_result int;
    EXEC @lock_result=sys.sp_getapplock @Resource=N'clinic-appointments-write',
      @LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=10000;
    IF @lock_result<0 THROW 51310,'Could not acquire appointment lock.',1;
    DECLARE @current_version binary(8),@previous_status varchar(20),@appointment_at datetime2,
      @duration smallint,@doctor_id uniqueidentifier,@schedule_id uniqueidentifier,
      @now datetime2=SYSUTCDATETIME();
    SELECT @current_version=a.row_version,@previous_status=a.status,
      @appointment_at=a.appointment_at,@duration=a.duration_minutes,
      @doctor_id=a.doctor_id,@schedule_id=a.schedule_id
    FROM dbo.appointments a WITH(UPDLOCK,HOLDLOCK)
    JOIN dbo.patients p ON p.patient_id=a.patient_id
    WHERE a.appointment_id=@appointment_id AND a.deleted_at IS NULL AND p.deleted_at IS NULL;
    IF @current_version IS NULL THROW 51301,'Appointment not found.',1;
    IF @expected_version IS NULL OR @current_version<>@expected_version
      THROW 51302,'Version conflict.',1;
    IF @previous_status NOT IN ('booked','confirmed')
      OR (@target_status='confirmed' AND @previous_status<>'booked')
      OR EXISTS(SELECT 1 FROM dbo.encounters WHERE appointment_id=@appointment_id)
      THROW 51313,'Appointment cannot be received in its current state.',1;
    IF (@target_status='confirmed' AND @appointment_at<=@now)
      OR (@target_status='checked_in' AND
        CAST(DATEADD(HOUR,7,@appointment_at) AS date)<>CAST(DATEADD(HOUR,7,@now) AS date))
      OR (@target_status='no_show' AND DATEADD(MINUTE,@duration,@appointment_at)>@now)
      THROW 51314,'Reception action is outside its allowed time.',1;
    IF @target_status<>'no_show'
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM dbo.doctors d JOIN dbo.users u ON u.user_id=d.user_id
        WHERE d.doctor_id=@doctor_id AND d.deleted_at IS NULL
          AND u.deleted_at IS NULL AND u.is_active=1) THROW 51309,'Doctor is unavailable.',1;
      IF @schedule_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM dbo.doctor_schedules
        WHERE schedule_id=@schedule_id AND doctor_id=@doctor_id AND status='active')
        THROW 51305,'Schedule is unavailable.',1;
    END;
    UPDATE dbo.appointments SET status=@target_status,updated_at=@now
    WHERE appointment_id=@appointment_id;
    SELECT @appointment_id AS appointment_id,@previous_status AS previous_status;
END;
GO
