[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$clinicRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $clinicRoot '.env'))) {
    throw 'Run clinic/scripts/setup.ps1 first.'
}
Push-Location $clinicRoot
try {
    & docker compose --profile tools run --rm db-check
    if ($LASTEXITCODE -ne 0) {
        throw "Database verification failed (exit $LASTEXITCODE)."
    }

    # Capture resolved configuration without printing credentials. Verify the same
    # host TCP route that the VS Code MSSQL extension will use on Windows.
    $resolvedJson = & docker compose config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Could not resolve Docker Compose configuration.' }
    $resolved = ($resolvedJson -join "`n") | ConvertFrom-Json
    Add-Type -AssemblyName System.Data
    $connectionOptions = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
    $connectionOptions['Data Source'] = '127.0.0.1,' + $resolved.services.sqlserver.ports[0].published
    $connectionOptions['Initial Catalog'] = 'ClinicManagement'
    $connectionOptions['User ID'] = 'sa'
    $connectionOptions['Password'] = $resolved.services.sqlserver.environment.MSSQL_SA_PASSWORD
    $connectionOptions['Encrypt'] = $true
    $connectionOptions['TrustServerCertificate'] = $true
    $connectionOptions['Connect Timeout'] = 15
    $connection = New-Object System.Data.SqlClient.SqlConnection($connectionOptions.ConnectionString)
    try {
        $connection.Open()
        $query = $connection.CreateCommand()
        try {
            $query.CommandText = 'SELECT DB_NAME();'
            if ($query.ExecuteScalar() -ne 'ClinicManagement') {
                throw 'The host connection reached an unexpected database.'
            }
        } finally { $query.Dispose() }
        Write-Host 'PASS: SQL Server is reachable from Windows through the VS Code connection address.'
    } finally {
        $connection.Dispose()
        $connectionOptions.Clear()
        $resolved = $null
        $resolvedJson = $null
    }
} finally {
    Pop-Location
}
