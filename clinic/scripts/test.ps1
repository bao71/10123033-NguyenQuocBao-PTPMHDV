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
    # Integration fixtures send password-reset emails to fake addresses and
    # inspect MailHog. Keep them isolated from a user's Gmail configuration.
    & docker compose exec -T -e SMTP_HOST=mailhog -e SMTP_PORT=1025 -e SMTP_FROM=clinic@example.local -e SMTP_STARTTLS=false -e SMTP_USERNAME= -e SMTP_PASSWORD= api python -m pytest -q --cov=API --cov=BLL --cov=DAL --cov=Model --cov=Core --cov=CLI --cov-report=term-missing --cov-fail-under=40
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
} finally {
    Pop-Location
}
