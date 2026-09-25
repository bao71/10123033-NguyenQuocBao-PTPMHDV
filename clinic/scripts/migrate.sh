#!/usr/bin/env bash
set -Eeuo pipefail

: "${SQLCMDPASSWORD:?SQLCMDPASSWORD must be set}"
: "${SQLCMDAPPUSER:?SQLCMDAPPUSER must be set}"
: "${SQLCMDAPPPASSWORD:?SQLCMDAPPPASSWORD must be set}"
if [[ ! "$SQLCMDAPPUSER" =~ ^[A-Za-z_][A-Za-z0-9_]{0,127}$ ]]; then
    echo 'SQLCMDAPPUSER contains unsupported characters.' >&2
    exit 1
fi
if [[ ! "$SQLCMDAPPPASSWORD" =~ ^[A-Za-z0-9!]{20,128}$ ]]; then
    echo 'SQLCMDAPPPASSWORD must be 20-128 characters using letters, digits and !.' >&2
    exit 1
fi
sqlcmd=(/opt/mssql-tools18/bin/sqlcmd -S "${SQLCMDSERVER:-sqlserver}" -U "${SQLCMDUSER:-sa}" -C -b -r1 -l 30 -I -x -f 65001)
database=ClinicManagement

# The database name is deliberately fixed, never interpolated from user input.
"${sqlcmd[@]}" -d master -Q "SET NOCOUNT ON;
DECLARE @result int;
EXEC @result = sys.sp_getapplock @Resource=N'clinic-create-database', @LockMode='Exclusive', @LockOwner='Session', @LockTimeout=60000;
IF @result < 0 THROW 51000, 'Could not acquire database creation lock.', 1;
IF DB_ID(N'ClinicManagement') IS NULL
    EXEC(N'CREATE DATABASE [ClinicManagement] COLLATE Latin1_General_100_CI_AS_SC');"

"${sqlcmd[@]}" -d "$database" -Q "SET XACT_ABORT ON; SET NOCOUNT ON;
BEGIN TRANSACTION;
DECLARE @result int;
EXEC @result = sys.sp_getapplock @Resource=N'clinic-schema-migrations', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=60000;
IF @result < 0 THROW 51000, 'Could not acquire migration lock.', 1;
IF OBJECT_ID(N'dbo.schema_migrations', N'U') IS NULL
    CREATE TABLE dbo.schema_migrations (
        version nvarchar(200) NOT NULL CONSTRAINT PK_schema_migrations PRIMARY KEY,
        checksum char(64) NOT NULL,
        applied_at datetime2(3) NOT NULL CONSTRAINT DF_schema_migrations_applied DEFAULT SYSUTCDATETIME()
    );
COMMIT;"

shopt -s nullglob
files=(/workspace/Database/migrations/*.sql)
if ((${#files[@]} == 0)); then
    echo 'No migration files found.' >&2
    exit 1
fi

temporary_sql=$(mktemp)
login_sql=$(mktemp)
user_sql=$(mktemp)
chmod 600 "$temporary_sql" "$login_sql" "$user_sql"
trap 'rm -f -- "$temporary_sql" "$login_sql" "$user_sql"' EXIT
for file in "${files[@]}"; do
    version=$(basename "$file")
    if [[ ! "$version" =~ ^[0-9]{3}_[a-z0-9_]+\.sql$ ]]; then
        echo "Invalid migration filename: $version" >&2
        exit 1
    fi
    # Canonical LF hashing allows the same checkout on Windows and Linux.
    checksum=$(tr -d '\r' < "$file" | sha256sum)
    checksum=${checksum%% *}
    # GO would escape the transaction/IF batch. Migrations are ordinary T-SQL only.
    if grep -Eiq '^[[:space:]]*GO([[:space:]]|$)' "$file"; then
        echo "GO is not allowed inside migration $version." >&2
        exit 1
    fi
    {
        cat <<SQL
SET XACT_ABORT ON;
SET NOCOUNT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET ARITHABORT ON;
SET NUMERIC_ROUNDABORT OFF;
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @lock_result int;
    EXEC @lock_result = sys.sp_getapplock @Resource=N'clinic-schema-migrations', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=60000;
    IF @lock_result < 0 THROW 51000, 'Could not acquire migration lock.', 1;
    IF EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE version=N'$version' AND checksum <> '$checksum')
        THROW 51001, 'An applied migration has changed. Restore it and create a new migration.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE version=N'$version')
    BEGIN
        EXEC sys.sp_executesql N'
SQL
        # Compile only unapplied migrations, in a child scope caught by TRY/CATCH.
        # Escaping quotes preserves the exact SQL text inside the NVARCHAR literal.
        tr -d '\r' < "$file" | sed "s/'/''/g"
        cat <<SQL
';
        INSERT dbo.schema_migrations(version, checksum) VALUES (N'$version', '$checksum');
        PRINT N'Applied $version';
    END
    ELSE PRINT N'Already applied $version';
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
SQL
    } > "$temporary_sql"
    "${sqlcmd[@]}" -d "$database" -i "$temporary_sql"
done

cat > "$login_sql" <<SQL
SET NOCOUNT ON;
DECLARE @name sysname = N'$SQLCMDAPPUSER';
DECLARE @statement nvarchar(max);
IF SUSER_ID(@name) IS NULL
    SET @statement = N'CREATE LOGIN ' + QUOTENAME(@name) + N' WITH PASSWORD=N''$SQLCMDAPPPASSWORD'', CHECK_POLICY=ON, CHECK_EXPIRATION=OFF;';
ELSE
    SET @statement = N'ALTER LOGIN ' + QUOTENAME(@name) + N' WITH PASSWORD=N''$SQLCMDAPPPASSWORD'', CHECK_POLICY=ON, CHECK_EXPIRATION=OFF;';
EXEC sys.sp_executesql @statement;
SQL
"${sqlcmd[@]}" -d master -i "$login_sql"

cat > "$user_sql" <<SQL
SET NOCOUNT ON;
DECLARE @name sysname = N'$SQLCMDAPPUSER';
DECLARE @statement nvarchar(max);
IF DATABASE_PRINCIPAL_ID(@name) IS NULL
BEGIN
    SET @statement = N'CREATE USER ' + QUOTENAME(@name) + N' FOR LOGIN ' + QUOTENAME(@name) + N';';
    EXEC sys.sp_executesql @statement;
END;
IF NOT EXISTS (
    SELECT 1
    FROM sys.database_role_members drm
    JOIN sys.database_principals role_principal ON role_principal.principal_id = drm.role_principal_id
    JOIN sys.database_principals member_principal ON member_principal.principal_id = drm.member_principal_id
    WHERE role_principal.name = N'clinic_app_role' AND member_principal.name = @name
)
BEGIN
    SET @statement = N'ALTER ROLE clinic_app_role ADD MEMBER ' + QUOTENAME(@name) + N';';
    EXEC sys.sp_executesql @statement;
END;
SQL
"${sqlcmd[@]}" -d "$database" -i "$user_sql"
echo 'Migrations complete.'
