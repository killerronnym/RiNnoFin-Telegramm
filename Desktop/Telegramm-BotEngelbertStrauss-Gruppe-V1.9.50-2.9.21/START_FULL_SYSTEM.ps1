# Bot System Startup Script - Startet Dashboard UND Master-Bot
Write-Host "--- Engelbert Strauss Bot System wird gestartet ---" -ForegroundColor Cyan

# 1. Pfade definieren
$ProjectRoot = $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $VenvPath)) {
    $VenvPath = Join-Path $ProjectRoot "venv\Scripts\Activate.ps1"
}

# 2. Virtual Environment aktivieren (falls vorhanden)
if (Test-Path $VenvPath) {
    Write-Host "Aktiviere Virtual Environment..." -ForegroundColor Gray
    . $VenvPath
} else {
    Write-Host "Warnung: .venv nicht gefunden. Nutze System-Python." -ForegroundColor Yellow
}

# 3. Das Dashboard starten (im Hintergrund oder neues Fenster)
Write-Host "Starte Web-Dashboard auf Port 9003..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass", "-NoExit", "-Command", "cd '$ProjectRoot'; & './devserver.ps1'" -WindowStyle Normal

# 4. Den Master-Bot starten
Write-Host "Starte Master-Bot (ID-Finder & alle Module)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass", "-NoExit", "-Command", "cd '$ProjectRoot'; if (Test-Path '.venv\Scripts\Activate.ps1') { . '.venv\Scripts\Activate.ps1' }; python bots/main_bot.py" -WindowStyle Normal

Write-Host "--- System wurde in separaten Fenstern gestartet ---" -ForegroundColor Cyan
Write-Host "Dashboard: http://localhost:9003" -ForegroundColor White
Write-Host "Beenden: Schließe einfach die PowerShell-Fenster." -ForegroundColor Gray
