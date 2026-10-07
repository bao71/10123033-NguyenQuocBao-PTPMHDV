ALTER TABLE dbo.encounters ADD vital_signs_json NVARCHAR(1000) NOT NULL
    CONSTRAINT DF_encounters_vitals DEFAULT N'{}' WITH VALUES;
-- Compile the constraint after the new column exists (migration runs in one batch).
EXEC sys.sp_executesql N'ALTER TABLE dbo.encounters ADD CONSTRAINT CK_encounters_vitals_json
    CHECK (ISJSON(vital_signs_json) = 1);';
