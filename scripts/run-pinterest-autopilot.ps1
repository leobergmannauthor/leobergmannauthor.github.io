$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"

$repository = Split-Path -Parent $PSScriptRoot
$marketingRoot = Split-Path -Parent $repository
$logDirectory = Join-Path $marketingRoot "data\autopilot_logs"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = Join-Path $logDirectory "pinterest_all_books_$timestamp.log"

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Set-Location -LiteralPath $repository

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    Write-Host ""
    Write-Host $Label -ForegroundColor Cyan
    & $Command 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) { throw "$Label ist fehlgeschlagen." }
}

Write-Host ""
Write-Host "Leo Bergmann Pinterest-Autopilot - alle deutschen Rezeptbücher" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Budget-Lock: 0 EUR"
Write-Host "Cloud-Betrieb: 2 organische Pins/Tag, 30 Tage Vorlauf"
Write-Host "Protokoll: $logFile"

try {
    python -c "import PIL" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Checked "Bildbibliothek installieren" { python -m pip install -r (Join-Path $repository "requirements-autopilot.txt") }
    }

    $dirty = git status --porcelain
    if ($LASTEXITCODE -ne 0) { throw "Git-Status konnte nicht gelesen werden." }
    if ($dirty) {
        throw "Das Repository enthält ungespeicherte Änderungen. Der Autopilot überschreibt sie nicht."
    }

    Invoke-Checked "Aktuellen GitHub-Stand laden" { git pull --ff-only origin main }
    Invoke-Checked "Katalog und 2:3-Creatives inkrementell vorbereiten" { python (Join-Path $PSScriptRoot "prepare_german_pin_catalog.py") }
    Invoke-Checked "30-Tage-Warteschlange auffüllen" { python (Join-Path $PSScriptRoot "catalog_scheduler.py") }
    Invoke-Checked "Veröffentlichungshistorie synchronisieren" { python (Join-Path $repository "publication_history.py") sync }
    Invoke-Checked "Website und RSS bauen" { python (Join-Path $repository "build.py") }
    Invoke-Checked "Vollständige Tests einschließlich Dreijahres-Simulation" { python -m unittest discover -s (Join-Path $repository "tests") -v }

    git add -- content/recipes.json data/books.json data/pin_catalog.json data/scheduler_state.json data/publication_history.json docs
    if ($LASTEXITCODE -ne 0) { throw "Git-Dateien konnten nicht vorgemerkt werden." }
    git diff --cached --check
    if ($LASTEXITCODE -ne 0) { throw "Git-Diff-Prüfung ist fehlgeschlagen." }
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 1) {
        Invoke-Checked "Änderungen committen" { git commit -m "Maintain all-book Pinterest queue" }
        Invoke-Checked "Änderungen zu GitHub pushen" { git push origin main }
    } elseif ($LASTEXITCODE -ne 0) {
        throw "Git-Diff konnte nicht geprüft werden."
    } else {
        Write-Host "Keine Änderungen: Katalog und 30-Tage-Plan sind bereits aktuell." -ForegroundColor Green
    }

    $dashboardUrl = "http://127.0.0.1:8765/"
    $dashboardHealthUrl = "http://127.0.0.1:8765/api/autopilot-status"
    $dashboardReady = $false
    try { $dashboardReady = (Invoke-WebRequest -Uri $dashboardHealthUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
    if (-not $dashboardReady) {
        $env:PYTHONPATH = Join-Path $marketingRoot "src"
        Start-Process -FilePath "python.exe" -ArgumentList @("-m", "kdp_marketing", "serve") -WorkingDirectory $marketingRoot -WindowStyle Hidden
        for ($attempt = 0; $attempt -lt 10 -and -not $dashboardReady; $attempt++) {
            Start-Sleep -Milliseconds 500
            try { $dashboardReady = (Invoke-WebRequest -Uri $dashboardHealthUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
        }
    }
    if ($dashboardReady) { Start-Process $dashboardUrl }
    Write-Host ""
    Write-Host "Fertig. GitHub übernimmt den täglichen Betrieb; das Notebook darf aus sein." -ForegroundColor Green
} catch {
    $_ | Out-String | Tee-Object -FilePath $logFile -Append | Write-Host -ForegroundColor Red
    Write-Host ""
    Write-Host "Sicher abgebrochen. Keine bezahlte Aktion wurde ausgeführt." -ForegroundColor Yellow
    Read-Host "Enter drücken, um das Fenster zu schließen"
    exit 1
}
