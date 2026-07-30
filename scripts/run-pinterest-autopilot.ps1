$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"

$repository = Split-Path -Parent $PSScriptRoot
$marketingRoot = Split-Path -Parent $repository
$logDirectory = Join-Path $marketingRoot "data\autopilot_logs"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = Join-Path $logDirectory "pinterest_$timestamp.log"

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Set-Location -LiteralPath $repository

Write-Host ""
Write-Host "Leo Bergmann Pinterest-Autopilot" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host "Budget-Lock: 0 EUR"
Write-Host "Protokoll: $logFile"
Write-Host ""

try {
    python -c "import PIL" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Einmalige Installation der Bildbibliothek ..."
        python -m pip install -r (Join-Path $repository "requirements-autopilot.txt")
        if ($LASTEXITCODE -ne 0) {
            throw "Pillow konnte nicht installiert werden."
        }
    }

    & python (Join-Path $PSScriptRoot "pinterest_autopilot.py") 2>&1 |
        Tee-Object -FilePath $logFile
    if ($LASTEXITCODE -ne 0) {
        throw "Der Autopilot-Lauf ist fehlgeschlagen. Details stehen im Protokoll."
    }

    $dashboardUrl = "http://127.0.0.1:8765/"
    $dashboardHealthUrl = "http://127.0.0.1:8765/api/autopilot-status"
    $dashboardReady = $false
    try {
        $dashboardReady = (Invoke-WebRequest -Uri $dashboardHealthUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $dashboardReady = $false
    }
    if (-not $dashboardReady) {
        $env:PYTHONPATH = Join-Path $marketingRoot "src"
        Start-Process -FilePath "python.exe" `
            -ArgumentList @("-m", "kdp_marketing", "serve") `
            -WorkingDirectory $marketingRoot `
            -WindowStyle Hidden
        for ($attempt = 0; $attempt -lt 10 -and -not $dashboardReady; $attempt++) {
            Start-Sleep -Milliseconds 500
            try {
                $dashboardReady = (Invoke-WebRequest -Uri $dashboardHealthUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
            } catch {
                $dashboardReady = $false
            }
        }
    }
    if (-not $dashboardReady) {
        throw "Dashboard konnte auf Port 8765 nicht mit der aktuellen API gestartet werden."
    }
    Start-Process $dashboardUrl
    Write-Host ""
    Write-Host "Fertig. Das Dashboard wurde geoeffnet." -ForegroundColor Green
} catch {
    $_ | Out-String | Tee-Object -FilePath $logFile -Append | Write-Host -ForegroundColor Red
    Write-Host ""
    Write-Host "Der Lauf wurde sicher abgebrochen. Es wurden keine bezahlten Aktionen ausgefuehrt." -ForegroundColor Yellow
    Read-Host "Enter druecken, um das Fenster zu schliessen"
    exit 1
}