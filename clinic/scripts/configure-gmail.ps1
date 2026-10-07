[CmdletBinding()]
param([string]$Email)

$ErrorActionPreference = 'Stop'
$clinicRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $clinicRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    throw 'Run scripts/setup.ps1 first to prepare clinic/.env.'
}
if (-not $Email) { $Email = Read-Host 'Gmail sender address' }
$Email = $Email.Trim()
if ($Email -notmatch '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$') {
    throw 'Enter a valid Gmail or Google Workspace email address.'
}

Write-Host 'Enable Google 2-Step Verification and create an App Password at https://myaccount.google.com/apppasswords'
$securePassword = Read-Host 'Google App Password (hidden; not your Google login password)' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $appPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $appPassword = $appPassword -replace '\s', ''
    if ($appPassword -notmatch '^[A-Za-z0-9]{16}$') {
        throw 'A Google App Password must contain 16 characters (spaces are removed automatically).'
    }
    $content = [IO.File]::ReadAllText($envPath)
    $smtpValues = [ordered]@{
        SMTP_HOST = 'smtp.gmail.com'
        SMTP_PORT = '587'
        SMTP_FROM = $Email
        SMTP_USERNAME = $Email
        SMTP_PASSWORD = $appPassword
        SMTP_STARTTLS = 'true'
        SMTP_TIMEOUT_SECONDS = '30'
    }
    foreach ($key in $smtpValues.Keys) {
        $pattern = '(?m)^' + [regex]::Escape($key) + '=[^\r\n]*'
        $line = $key + '=' + $smtpValues[$key]
        if ([regex]::IsMatch($content, $pattern)) {
            $content = [regex]::Replace($content, $pattern, $line)
        } else {
            $content = $content.TrimEnd() + "`r`n" + $line + "`r`n"
        }
    }
    [IO.File]::WriteAllText($envPath, $content.TrimEnd() + "`r`n", (New-Object System.Text.UTF8Encoding($false)))
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    $securePassword.Dispose()
    $appPassword = $null
    $content = $null
    $smtpValues = $null
}
Write-Host 'Gmail SMTP saved in clinic/.env. The App Password is not printed.'
Write-Host 'From clinic/, run: docker compose up -d --build api'
Write-Host 'Then run: docker compose exec -T api python -m CLI.test_email --recipient your-address@gmail.com'
