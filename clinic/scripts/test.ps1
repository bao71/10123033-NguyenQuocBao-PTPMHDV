[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$clinicRoot = Split-Path -Parent $PSScriptRoot
$ruff = Join-Path $clinicRoot 'backend\.venv\Scripts\ruff.exe'
if (-not (Test-Path -LiteralPath $ruff)) {
    throw 'Run "uv sync" in clinic/backend before executing the lint check.'
}

& $ruff check (Join-Path $clinicRoot 'backend')
if ($LASTEXITCODE -ne 0) { throw 'Ruff check failed.' }

Push-Location $clinicRoot
try {
    & docker compose up -d --build api
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the API test environment.' }
    & docker compose exec -T api python -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=40
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
} finally {
    Pop-Location
}
