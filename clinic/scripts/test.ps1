[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$clinicRoot = Split-Path -Parent $PSScriptRoot

Push-Location $clinicRoot
try {
    & docker compose up -d --build api
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the API test environment.' }
    & docker compose exec -T api ruff check API BLL DAL Model Core CLI Tests
    if ($LASTEXITCODE -ne 0) { throw 'Ruff check failed.' }
    & docker compose exec -T api python -m pytest -q --cov=API --cov=BLL --cov=DAL --cov=Model --cov=Core --cov=CLI --cov-report=term-missing --cov-fail-under=40
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
} finally {
    Pop-Location
}
