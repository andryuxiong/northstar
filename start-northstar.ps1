param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
$logDir = Join-Path $backend "data\logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "Starting Northstar personal intelligence..." -ForegroundColor Cyan

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating the private Python environment (first run only)..."
    python -m venv (Join-Path $backend ".venv")
}

Write-Host "Checking backend packages..."
& $venvPython -m pip install --disable-pip-version-check --quiet -r (Join-Path $backend "requirements.txt")

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing frontend packages (first run only)..."
    Push-Location $frontend
    try { npm install } finally { Pop-Location }
}

# The development servers do not automatically reload backend Python modules.
# Restart only listeners that look like this Northstar project; refuse to stop
# an unrelated process that happens to own one of the expected ports.
foreach ($port in 8000, 5173) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { continue }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    $commandLine = [string]$process.CommandLine
    $isNorthstar = $commandLine -like "*$root*" -or
        ($port -eq 8000 -and $commandLine -match "uvicorn\s+app\.main:app") -or
        ($port -eq 5173 -and $commandLine -match "vite(?:\.js)?")
    if (-not $isNorthstar) {
        throw "Port $port is already used by an unrelated process (PID $($listener.OwningProcess)). Stop it or change the Northstar port."
    }
    Write-Host "Restarting the existing Northstar service on port $port..."
    Stop-Process -Id $listener.OwningProcess -Force
}

$stopDeadline = (Get-Date).AddSeconds(8)
do {
    Start-Sleep -Milliseconds 150
    $remainingListener = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in 8000, 5173 } |
        Select-Object -First 1
} until (-not $remainingListener -or (Get-Date) -gt $stopDeadline)
if ($remainingListener) {
    throw "An existing Northstar service did not stop cleanly. Run stop-northstar.ps1 and try again."
}

$apiListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $apiListener) {
    Start-Process -FilePath $venvPython `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $backend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "api.log") `
        -RedirectStandardError (Join-Path $logDir "api-error.log") | Out-Null
}

$uiListener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $uiListener) {
    Start-Process -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory $frontend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "ui.log") `
        -RedirectStandardError (Join-Path $logDir "ui-error.log") | Out-Null
}

$deadline = (Get-Date).AddSeconds(30)
do {
    Start-Sleep -Milliseconds 350
    try {
        $apiReady = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/snapshots/health" -TimeoutSec 2).StatusCode -eq 200
        $uiReady = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:5173" -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $apiReady = $false
        $uiReady = $false
    }
} until (($apiReady -and $uiReady) -or (Get-Date) -gt $deadline)

if (-not ($apiReady -and $uiReady)) {
    throw "Northstar did not become ready. Check backend\data\logs for details."
}

Write-Host "Northstar is ready at http://127.0.0.1:5173" -ForegroundColor Green
if (-not $NoBrowser) {
    $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (Test-Path $chrome) {
        Start-Process -FilePath $chrome -ArgumentList @("--new-window", "http://127.0.0.1:5173")
    } else {
        Start-Process "http://127.0.0.1:5173"
    }
}
