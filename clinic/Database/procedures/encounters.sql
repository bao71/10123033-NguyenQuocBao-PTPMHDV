CREATE OR ALTER PROCEDURE dbo.clinic_encounter_list
    @scope varchar(10), @user_id uniqueidentifier, @page int, @page_size int,
    @search nvarchar(100) = NULL, @patient_id uniqueidentifier = NULL,
    @status varchar(20) = NULL, @start_at datetime2 = NULL, @end_at datetime2 = NULL,
    @sort_by varchar(20) = 'started_at', @sort_order varchar(4) = 'desc',
    @appointment_id uniqueidentifier = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @scope NOT IN ('assigned','self') OR @sort_by NOT IN ('started_at','updated_at','status')
      OR @sort_order NOT IN ('asc','desc') THROW 51403,'Invalid encounter query.',1;
    DECLARE @pattern nvarchar(210)=CASE WHEN @search IS NULL OR @search='' THEN NULL
      ELSE N'%' + REPLACE(REPLACE(REPLACE(REPLACE(@search,N'\',N'\\'),
        N'%',N'\%'),N'_',N'\_'),N'[',N'\[') + N'%' END;
    SELECT e.*,p.patient_code,p.full_name AS patient_name,d.doctor_code,
      u.username AS doctor_name,d.specialty INTO #encounters
    FROM dbo.encounters e JOIN dbo.patients p ON p.patient_id=e.patient_id
    JOIN dbo.doctors d ON d.doctor_id=e.doctor_id JOIN dbo.users u ON u.user_id=d.user_id
    WHERE e.deleted_at IS NULL AND p.deleted_at IS NULL
      AND ((@scope='assigned' AND d.user_id=@user_id AND d.deleted_at IS NULL)
        OR (@scope='self' AND p.user_id=@user_id AND e.status='completed'))
      AND (@patient_id IS NULL OR e.patient_id=@patient_id)
      AND (@appointment_id IS NULL OR e.appointment_id=@appointment_id)
      AND (@status IS NULL OR e.status=@status)
      AND (@start_at IS NULL OR e.started_at>=@start_at)
      AND (@end_at IS NULL OR e.started_at<@end_at)
      AND (@pattern IS NULL OR p.full_name LIKE @pattern ESCAPE '\'
        OR p.patient_code LIKE @pattern ESCAPE '\' OR e.diagnosis_summary LIKE @pattern ESCAPE '\');
    SELECT COUNT_BIG(*) AS total FROM #encounters;
    SELECT * FROM #encounters ORDER BY
      CASE WHEN @sort_by='started_at' AND @sort_order='asc' THEN started_at END ASC,
      CASE WHEN @sort_by='started_at' AND @sort_order='desc' THEN started_at END DESC,
      CASE WHEN @sort_by='updated_at' AND @sort_order='asc' THEN updated_at END ASC,
      CASE WHEN @sort_by='updated_at' AND @sort_order='desc' THEN updated_at END DESC,
      CASE WHEN @sort_by='status' AND @sort_order='asc' THEN status END ASC,
      CASE WHEN @sort_by='status' AND @sort_order='desc' THEN status END DESC,encounter_id
    OFFSET (@page-1)*@page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_encounter_get
    @scope varchar(10), @user_id uniqueidentifier, @encounter_id uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    IF @scope NOT IN ('assigned','self') THROW 51403,'Invalid encounter scope.',1;
    SELECT e.*,p.patient_code,p.full_name AS patient_name,d.doctor_code,
      u.username AS doctor_name,d.specialty INTO #encounter
    FROM dbo.encounters e JOIN dbo.patients p ON p.patient_id=e.patient_id
    JOIN dbo.doctors d ON d.doctor_id=e.doctor_id JOIN dbo.users u ON u.user_id=d.user_id
    WHERE e.encounter_id=@encounter_id AND e.deleted_at IS NULL AND p.deleted_at IS NULL
      AND ((@scope='assigned' AND d.user_id=@user_id AND d.deleted_at IS NULL)
        OR (@scope='self' AND p.user_id=@user_id AND e.status='completed'));
    SELECT * FROM #encounter;
    SELECT x.diagnosis_id,x.code,x.name,x.is_primary,x.notes,x.row_version
    FROM dbo.diagnoses x JOIN #encounter e ON e.encounter_id=x.encounter_id
    WHERE x.deleted_at IS NULL ORDER BY x.is_primary DESC,x.created_at,x.diagnosis_id;
    SELECT o.* FROM dbo.clinical_orders o JOIN #encounter e ON e.encounter_id=o.encounter_id
    WHERE o.deleted_at IS NULL ORDER BY o.ordered_at,o.order_id;
    SELECT r.* FROM dbo.clinical_results r JOIN dbo.clinical_orders o ON o.order_id=r.order_id
    JOIN #encounter e ON e.encounter_id=o.encounter_id
    WHERE r.deleted_at IS NULL AND o.deleted_at IS NULL ORDER BY r.result_at,r.result_id;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_encounter_snapshot
    @encounter_id uniqueidentifier, @actor_user_id uniqueidentifier, @reason nvarchar(1000)
AS
BEGIN
    SET NOCOUNT ON;
    IF @@TRANCOUNT=0 THROW 51410,'A transaction is required.',1;
    DECLARE @snapshot nvarchar(max),@version_no int;
    SELECT @version_no=version_no FROM dbo.encounters WHERE encounter_id=@encounter_id;
    SET @snapshot=(SELECT e.encounter_id,e.appointment_id,e.patient_id,e.doctor_id,
      e.started_at,e.ended_at,e.chief_complaint,e.clinical_notes,e.diagnosis_summary,
      e.treatment_plan,e.status,e.version_no,JSON_QUERY(e.vital_signs_json) AS vital_signs,
      JSON_QUERY((SELECT x.diagnosis_id,x.code,x.name,x.is_primary,x.notes
        FROM dbo.diagnoses x WHERE x.encounter_id=e.encounter_id AND x.deleted_at IS NULL
        ORDER BY x.is_primary DESC,x.created_at,x.diagnosis_id FOR JSON PATH)) AS diagnoses,
      JSON_QUERY((SELECT o.order_id,o.order_type,o.name,o.instructions,o.status,o.ordered_by,
        JSON_QUERY((SELECT r.result_id,r.result_text,r.numeric_value,r.unit,r.reference_range,
          r.file_url,r.result_at,r.entered_by FROM dbo.clinical_results r
          WHERE r.order_id=o.order_id AND r.deleted_at IS NULL
          ORDER BY r.result_at,r.result_id FOR JSON PATH)) AS results
        FROM dbo.clinical_orders o WHERE o.encounter_id=e.encounter_id AND o.deleted_at IS NULL
        ORDER BY o.ordered_at,o.order_id FOR JSON PATH)) AS clinical_orders
      FROM dbo.encounters e WHERE e.encounter_id=@encounter_id
      FOR JSON PATH,WITHOUT_ARRAY_WRAPPER);
    INSERT dbo.record_versions(changed_by,entity_type,entity_id,version_no,data_json,change_reason)
    VALUES(@actor_user_id,'encounters',@encounter_id,@version_no,@snapshot,@reason);
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_encounter_write
    @action varchar(30), @actor_user_id uniqueidentifier,
    @encounter_id uniqueidentifier = NULL, @appointment_id uniqueidentifier = NULL,
    @appointment_version binary(8) = NULL, @expected_version binary(8) = NULL,
    @chief_complaint nvarchar(2000) = NULL, @clinical_notes nvarchar(max) = NULL,
    @diagnosis_summary nvarchar(2000) = NULL, @treatment_plan nvarchar(max) = NULL,
    @vital_signs_json nvarchar(1000) = NULL, @diagnoses_json nvarchar(max) = NULL,
    @order_id uniqueidentifier = NULL, @order_version binary(8) = NULL,
    @order_type varchar(20) = NULL, @name nvarchar(300) = NULL,
    @instructions nvarchar(2000) = NULL, @order_status varchar(20) = NULL,
    @result_id uniqueidentifier = NULL, @result_version binary(8) = NULL,
    @result_text nvarchar(max) = NULL, @numeric_value decimal(18,6) = NULL,
    @unit nvarchar(50) = NULL, @reference_range nvarchar(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @@TRANCOUNT=0 THROW 51410,'A transaction is required.',1;
    IF @action NOT IN ('start','save','complete','order_create','order_update','order_cancel',
      'order_delete','result_create','result_update','result_delete')
      THROW 51403,'Invalid clinical action.',1;
    -- Share the reception/booking lock so appointment and encounter states cannot diverge.
    DECLARE @lock_result int;
    EXEC @lock_result=sys.sp_getapplock @Resource=N'clinic-appointments-write',
      @LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=10000;
    IF @lock_result<0 THROW 51410,'Could not acquire clinical lock.',1;
    DECLARE @now datetime2=SYSUTCDATETIME(),@current_version binary(8),@current_status varchar(20),
      @patient_id uniqueidentifier,@doctor_id uniqueidentifier;
    IF @action='start'
    BEGIN
      SELECT @current_version=a.row_version,@current_status=a.status,
        @patient_id=a.patient_id,@doctor_id=a.doctor_id
      FROM dbo.appointments a WITH(UPDLOCK,HOLDLOCK)
      JOIN dbo.doctors d ON d.doctor_id=a.doctor_id JOIN dbo.users u ON u.user_id=d.user_id
      JOIN dbo.patients p ON p.patient_id=a.patient_id
      WHERE a.appointment_id=@appointment_id AND a.deleted_at IS NULL AND p.deleted_at IS NULL
        AND d.user_id=@actor_user_id AND d.deleted_at IS NULL AND u.deleted_at IS NULL AND u.is_active=1;
      IF @current_version IS NULL THROW 51401,'Appointment is outside assigned scope.',1;
      IF @appointment_version IS NULL OR @current_version<>@appointment_version
        THROW 51402,'Appointment version conflict.',1;
      IF @current_status<>'checked_in' OR EXISTS(
        SELECT 1 FROM dbo.encounters WHERE appointment_id=@appointment_id)
        THROW 51404,'Appointment is not ready or already has an encounter.',1;
      DECLARE @created TABLE(id uniqueidentifier);
      INSERT dbo.encounters(appointment_id,patient_id,doctor_id,chief_complaint)
      OUTPUT inserted.encounter_id INTO @created
      VALUES(@appointment_id,@patient_id,@doctor_id,@chief_complaint);
      SELECT @encounter_id=id FROM @created;
      UPDATE dbo.appointments SET status='in_progress',updated_at=@now
      WHERE appointment_id=@appointment_id;
    END
    ELSE
    BEGIN
      SELECT @current_version=e.row_version,@current_status=e.status,@appointment_id=e.appointment_id
      FROM dbo.encounters e WITH(UPDLOCK,HOLDLOCK)
      JOIN dbo.doctors d ON d.doctor_id=e.doctor_id JOIN dbo.users u ON u.user_id=d.user_id
      JOIN dbo.patients p ON p.patient_id=e.patient_id
      WHERE e.encounter_id=@encounter_id AND e.deleted_at IS NULL AND p.deleted_at IS NULL
        AND d.user_id=@actor_user_id AND d.deleted_at IS NULL AND u.deleted_at IS NULL AND u.is_active=1;
      IF @current_version IS NULL THROW 51401,'Encounter is outside assigned scope.',1;
      IF @expected_version IS NULL OR @current_version<>@expected_version
        THROW 51402,'Encounter version conflict.',1;
      IF @current_status<>'in_progress' THROW 51403,'Encounter is locked.',1;
      IF @appointment_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM dbo.appointments
        WHERE appointment_id=@appointment_id AND deleted_at IS NULL AND status='in_progress')
        THROW 51403,'Linked appointment is not in progress.',1;
      IF @action='save'
      BEGIN
        IF ISJSON(@vital_signs_json)<>1 OR ISJSON(@diagnoses_json)<>1
          THROW 51403,'Invalid clinical JSON.',1;
        IF (SELECT COUNT(*) FROM OPENJSON(@diagnoses_json)
          WITH(is_primary bit '$.is_primary') WHERE is_primary=1)>1
          THROW 51405,'Only one primary diagnosis is allowed.',1;
        UPDATE dbo.encounters SET chief_complaint=@chief_complaint,clinical_notes=@clinical_notes,
          diagnosis_summary=@diagnosis_summary,treatment_plan=@treatment_plan,
          vital_signs_json=@vital_signs_json WHERE encounter_id=@encounter_id;
        -- Replacement removes old rows softly; previous snapshots retain their identities/content.
        UPDATE dbo.diagnoses SET deleted_at=@now,updated_at=@now
        WHERE encounter_id=@encounter_id AND deleted_at IS NULL;
        INSERT dbo.diagnoses(encounter_id,code,name,is_primary,notes)
        SELECT @encounter_id,code,name,is_primary,notes FROM OPENJSON(@diagnoses_json)
        WITH(code varchar(30) '$.code',name nvarchar(500) '$.name',
          is_primary bit '$.is_primary',notes nvarchar(2000) '$.notes');
      END
      ELSE IF @action='complete'
      BEGIN
        IF NOT EXISTS(SELECT 1 FROM dbo.encounters WHERE encounter_id=@encounter_id
          AND LEN(LTRIM(RTRIM(diagnosis_summary)))>0)
          OR NOT EXISTS(SELECT 1 FROM dbo.diagnoses WHERE encounter_id=@encounter_id
            AND deleted_at IS NULL AND is_primary=1)
          THROW 51405,'Completion requires a conclusion and primary diagnosis.',1;
        IF EXISTS(SELECT 1 FROM dbo.clinical_orders WHERE encounter_id=@encounter_id
          AND deleted_at IS NULL AND status IN ('ordered','in_progress'))
          THROW 51406,'Clinical orders still pending.',1;
        UPDATE dbo.encounters SET status='completed',ended_at=@now WHERE encounter_id=@encounter_id;
        UPDATE dbo.appointments SET status='completed',updated_at=@now
        WHERE appointment_id=@appointment_id;
      END
      ELSE
      BEGIN
        DECLARE @current_order_version binary(8),@current_order_status varchar(20);
        IF @action<>'order_create'
        BEGIN
          SELECT @current_order_version=row_version,@current_order_status=status
          FROM dbo.clinical_orders WITH(UPDLOCK,HOLDLOCK)
          WHERE order_id=@order_id AND encounter_id=@encounter_id AND deleted_at IS NULL;
          IF @current_order_version IS NULL THROW 51407,'Order not found in encounter.',1;
          IF @order_version IS NULL OR @current_order_version<>@order_version
            THROW 51402,'Clinical order version conflict.',1;
          IF @current_order_status='cancelled' THROW 51408,'Order is cancelled.',1;
        END;
        IF @action='order_create'
          INSERT dbo.clinical_orders(encounter_id,ordered_by,order_type,name,instructions)
          VALUES(@encounter_id,@actor_user_id,@order_type,@name,@instructions);
        ELSE IF @action IN ('order_update','order_cancel','order_delete')
        BEGIN
          IF EXISTS(SELECT 1 FROM dbo.clinical_results WHERE order_id=@order_id AND deleted_at IS NULL)
            THROW 51408,'Order already has results.',1;
          IF @action='order_update'
            UPDATE dbo.clinical_orders SET order_type=@order_type,name=@name,instructions=@instructions,
              status=@order_status,updated_at=@now WHERE order_id=@order_id;
          ELSE
            UPDATE dbo.clinical_orders SET status='cancelled',updated_at=@now,
              deleted_at=CASE WHEN @action='order_delete' THEN @now ELSE NULL END
            WHERE order_id=@order_id;
        END
        ELSE
        BEGIN
          IF @action<>'result_create'
          BEGIN
            DECLARE @current_result_version binary(8);
            SELECT @current_result_version=row_version FROM dbo.clinical_results WITH(UPDLOCK,HOLDLOCK)
            WHERE result_id=@result_id AND order_id=@order_id AND deleted_at IS NULL;
            IF @current_result_version IS NULL THROW 51409,'Result not found in order.',1;
            IF @result_version IS NULL OR @current_result_version<>@result_version
              THROW 51402,'Clinical result version conflict.',1;
          END;
          IF @action='result_create'
            INSERT dbo.clinical_results(order_id,entered_by,result_text,numeric_value,unit,reference_range)
            VALUES(@order_id,@actor_user_id,@result_text,@numeric_value,@unit,@reference_range);
          ELSE IF @action='result_update'
            UPDATE dbo.clinical_results SET entered_by=@actor_user_id,result_text=@result_text,
              numeric_value=@numeric_value,unit=@unit,reference_range=@reference_range,updated_at=@now
            WHERE result_id=@result_id;
          ELSE
            UPDATE dbo.clinical_results SET deleted_at=@now,updated_at=@now WHERE result_id=@result_id;
          UPDATE dbo.clinical_orders SET status=CASE WHEN EXISTS(SELECT 1 FROM dbo.clinical_results
            WHERE order_id=@order_id AND deleted_at IS NULL) THEN 'completed' ELSE 'ordered' END,
            updated_at=@now WHERE order_id=@order_id;
        END;
      END;
      UPDATE dbo.encounters SET version_no=version_no+1,updated_at=@now WHERE encounter_id=@encounter_id;
    END;
    EXEC dbo.clinic_encounter_snapshot @encounter_id,@actor_user_id,@action;
    SELECT @encounter_id AS encounter_id;
END;
GO
CREATE OR ALTER PROCEDURE dbo.clinic_encounter_versions
    @encounter_id uniqueidentifier,@user_id uniqueidentifier,@page int,@page_size int
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS(SELECT 1 FROM dbo.encounters e JOIN dbo.doctors d ON d.doctor_id=e.doctor_id
      JOIN dbo.patients p ON p.patient_id=e.patient_id
      WHERE e.encounter_id=@encounter_id AND e.deleted_at IS NULL AND p.deleted_at IS NULL
        AND d.user_id=@user_id AND d.deleted_at IS NULL)
      THROW 51401,'Encounter is outside assigned scope.',1;
    SELECT COUNT_BIG(*) AS total FROM dbo.record_versions
    WHERE entity_type='encounters' AND entity_id=@encounter_id;
    SELECT v.version_no,v.changed_by,u.username AS changed_by_name,v.change_reason,
      v.changed_at,v.data_json FROM dbo.record_versions v JOIN dbo.users u ON u.user_id=v.changed_by
    WHERE v.entity_type='encounters' AND v.entity_id=@encounter_id ORDER BY v.version_no DESC
    OFFSET (@page-1)*@page_size ROWS FETCH NEXT @page_size ROWS ONLY;
END;
GO
