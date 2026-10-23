# ====================================================================
# ThaiOCR Worker - Windows Host Automated Deployment Script
# ====================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 1. Check Administrator Privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[!] Please run PowerShell as Administrator" -ForegroundColor Red
    Write-Host "    Elevating permissions automatically..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"") -Verb RunAs
    exit
}

Clear-Host
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "    ThaiOCR Windows Worker - Deployment & Security Setup            " -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# 2. Prompt for Ubuntu Server IP
$UbuntuIP = ""
while (-not $UbuntuIP) {
    $inputIP = Read-Host "Specify Ubuntu Server IP Address (e.g. 192.168.1.100)"
    if ($inputIP -match '^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$') {
        $UbuntuIP = $inputIP.Trim()
    } else {
        Write-Host " [!] Invalid IPv4 format. Please try again." -ForegroundColor Red
    }
}

# Detect local Windows IP for SAN
$LocalIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'vEthernet|Loopback' -and $_.IPAddress -notmatch '^169\.254\.' } | Select-Object -First 1).IPAddress
if (-not $LocalIP) { $LocalIP = "127.0.0.1" }
Write-Host "[i] Detected Windows Host IP: $LocalIP" -ForegroundColor Gray

# 3. Generate or Input Shared Secret Token
Write-Host ""
Write-Host "[1/5] Configuring Shared Secret Token (Level 2 Security)..." -ForegroundColor Green
$choiceToken = Read-Host "Auto-generate secure Secret Token? (Y/N) [Default: Y]"
if ($choiceToken -match '^[Nn]$') {
    $SecretToken = Read-Host "Enter your custom Secret Token"
} else {
    $bytes = New-Object byte[] 24
    (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
    $SecretToken = [Convert]::ToBase64String($bytes) -replace '[/+=]', ''
}
Write-Host " -> Secret Token: $SecretToken" -ForegroundColor Yellow

# 4. Check Python and Install Dependencies
Write-Host ""
Write-Host "[2/5] Checking Python environment and dependencies..." -ForegroundColor Green
$pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Host "[X] Python not found in PATH! Please install Python 3.10+ first." -ForegroundColor Red
    pause
    exit 1
}

$pyVer = & python.exe --version 2>&1
Write-Host " -> Python Version: $pyVer" -ForegroundColor Gray

Write-Host " -> Installing required packages (FastAPI, Uvicorn, Pillow, PyMuPDF, Cryptography)..." -ForegroundColor Gray
& python.exe -m pip install --upgrade pip --quiet
& python.exe -m pip install --no-cache-dir fastapi uvicorn pillow pymupdf cryptography requests --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Warning: Error occurred during package installation" -ForegroundColor Red
} else {
    Write-Host " -> Dependencies installed successfully." -ForegroundColor Green
}

# 5. Configure Windows Firewall (Permit IP)
Write-Host ""
Write-Host "[3/5] Configuring Windows Defender Firewall Permit-IP for Ubuntu ($UbuntuIP)..." -ForegroundColor Green

Remove-NetFirewallRule -DisplayName "ThaiOCR Worker*" -ErrorAction SilentlyContinue

New-NetFirewallRule -DisplayName "ThaiOCR Worker - Permit Ubuntu Only" `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort 8001 `
    -RemoteAddress @($UbuntuIP, "127.0.0.1", "::1") `
    -Description "Permit ThaiOCR Worker from Ubuntu Server ($UbuntuIP) exclusively" | Out-Null

Write-Host " -> Windows Firewall configured: Port 8001 allowed ONLY from $UbuntuIP and localhost." -ForegroundColor Green

# 6. Generate mTLS Certificates
Write-Host ""
Write-Host "[4/5] Generating mTLS 1.3 Certificates..." -ForegroundColor Green
$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Split-Path -Parent $ScriptDir
$CertsDir = Join-Path $ProjectRoot "certs"

$GenCertsPy = Join-Path $ScriptDir "generate_mtls_certs.py"
if (Test-Path $GenCertsPy) {
    & python.exe "$GenCertsPy" "$LocalIP" | Out-Null
    Write-Host " -> Certificates generated in $CertsDir" -ForegroundColor Green
} else {
    Write-Host " -> Skipped certificate generation (script not found)" -ForegroundColor Yellow
}

# 7. Create start_worker.bat
Write-Host ""
Write-Host "[5/5] Generating launcher start_worker.bat..." -ForegroundColor Green
$WorkerBat = Join-Path $ProjectRoot "start_worker.bat"

$BatLines = @(
    "@echo off",
    "title ThaiOCR Windows Worker Service",
    "cd /d `"%~dp0`"",
    "",
    "set `"ALLOWED_IPS=127.0.0.1,::1,localhost,$UbuntuIP`"",
    "set `"OCR_WORKER_SECRET_TOKEN=$SecretToken`"",
    "set `"WORKER_HOST=0.0.0.0`"",
    "set `"WORKER_PORT=8001`"",
    "",
    "echo ===================================================================",
    "echo     ThaiOCR Windows Worker - Running Securely",
    "echo ===================================================================",
    "echo  Permitted Ubuntu IP : $UbuntuIP",
    "echo  Listening Port      : 8001",
    "echo  Auth Token          : Activated",
    "echo ===================================================================",
    "echo.",
    "",
    "python ocr_worker.py",
    "pause"
)

[System.IO.File]::WriteAllLines($WorkerBat, $BatLines, [System.Text.Encoding]::ASCII)
Write-Host " -> Launcher created: $WorkerBat" -ForegroundColor Green

# 8. Output Summary for Ubuntu Server
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "              DEPLOYMENT COMPLETED SUCCESSFULLY                     " -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Add the following lines to .env on Ubuntu Server:" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "OCR_WORKER_URL=http://$LocalIP`:8001" -ForegroundColor White
Write-Host "OCR_WORKER_SECRET_TOKEN=$SecretToken" -ForegroundColor White
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""
Write-Host "For full mTLS mode:" -ForegroundColor Yellow
Write-Host "  1. Copy certs/ca.crt, certs/client.crt, certs/client.key to Ubuntu"
Write-Host "  2. In start_worker.bat, add SSL_KEYFILE, SSL_CERTFILE, SSL_CA_CERTS"
Write-Host "  3. In Ubuntu .env, set OCR_WORKER_URL=https://$LocalIP`:8001"
Write-Host ""

$startNow = Read-Host "Start OCR Worker service now? (Y/N) [Default: Y]"
if ($startNow -notmatch '^[Nn]$') {
    Start-Process cmd.exe -ArgumentList ("/c `"$WorkerBat`"")
    Write-Host "[OK] ThaiOCR Worker started in a new window on port 8001." -ForegroundColor Green
}

Write-Host ""
Write-Host "All done." -ForegroundColor Cyan
