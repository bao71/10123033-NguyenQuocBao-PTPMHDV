[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$clinicRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'setup.ps1')

Push-Location $clinicRoot
try {
    & docker compose up -d --build api
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the API container.' }
    $ready = $false
    foreach ($attempt in 1..30) {
        try {
            $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/ready' -TimeoutSec 3
            if ($response.status -eq 'ok') { $ready = $true; break }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ready) { throw 'API did not become ready within 60 seconds.' }
    Write-Host 'API ready: http://127.0.0.1:8000'
    Write-Host 'Swagger:   http://127.0.0.1:8000/docs'
} finally {
    Pop-Location
}
