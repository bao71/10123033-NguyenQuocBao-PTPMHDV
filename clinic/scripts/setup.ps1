[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$clinicRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $clinicRoot '.env'

function New-RandomHex {
    param([int]$ByteCount = 32)
    $bytes = New-Object byte[] $ByteCount
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

function Invoke-DockerChecked {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed (exit $LASTEXITCODE). See the error above."
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install Docker Desktop with the WSL2 backend and Linux containers first.'
}

if (-not (Test-Path -LiteralPath $envPath)) {
    # Hex avoids .env interpolation and quoting issues; prefixes meet SQL policy.
    $password = 'Cl!9' + (New-RandomHex)
    $appPassword = 'Ap!9' + (New-RandomHex)
    $jwtSecret = New-RandomHex
    $template = [IO.File]::ReadAllText((Join-Path $clinicRoot '.env.example'))
    $content = $template.Replace('CHANGE_ME_WITH_A_UNIQUE_STRONG_PASSWORD', $password)
    $content = $content.Replace('CHANGE_ME_WITH_ANOTHER_UNIQUE_STRONG_PASSWORD', $appPassword)
    $content = $content.Replace('CHANGE_ME_WITH_A_RANDOM_64_CHARACTER_HEX_SECRET', $jwtSecret)
    [IO.File]::WriteAllText($envPath, $content, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'Created clinic/.env with random database and JWT secrets. Secrets are not printed.'
}

$configuration = [IO.File]::ReadAllText($envPath)
if ($configuration -notmatch '(?m)^MSSQL_APP_USER=') {
    $configuration += "`r`nMSSQL_APP_USER=clinic_app"
}
if ($configuration -notmatch '(?m)^MSSQL_APP_PASSWORD=') {
    $configuration += "`r`nMSSQL_APP_PASSWORD=Ap!9$(New-RandomHex)"
}
if ($configuration -notmatch '(?m)^APP_SECRET_KEY=') {
    $configuration += "`r`nAPP_SECRET_KEY=$(New-RandomHex)"
}
if ($configuration -notmatch '(?m)^APP_ENV=') {
    $configuration += "`r`nAPP_ENV=development"
}
if ($configuration -notmatch '(?m)^APP_CORS_ORIGINS=') {
    $configuration += "`r`nAPP_CORS_ORIGINS=http://localhost:4200,http://127.0.0.1:4200"
}
[IO.File]::WriteAllText($envPath, $configuration.Trim() + "`r`n", (New-Object System.Text.UTF8Encoding($false)))

if ($configuration -match 'CHANGE_ME_WITH_') {
    throw 'Replace every CHANGE_ME value in clinic/.env before starting.'
}

Push-Location $clinicRoot
try {
    Invoke-DockerChecked -DockerArgs @('info', '--format', '{{.OSType}}')
    Invoke-DockerChecked -DockerArgs @('compose', 'config', '--quiet')
    Invoke-DockerChecked -DockerArgs @('compose', 'up', '-d', '--wait', '--wait-timeout', '240', 'sqlserver')
    Invoke-DockerChecked -DockerArgs @('compose', 'run', '--rm', 'db-init')
    & (Join-Path $PSScriptRoot 'check.ps1')
    Write-Host 'Database ready: ClinicManagement. See clinic/README.md for VS Code connection settings.'
} finally {
    Pop-Location
}
