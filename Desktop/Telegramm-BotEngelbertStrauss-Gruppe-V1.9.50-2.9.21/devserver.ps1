# Bot Dashboard Startup Script with Auto-Restart (IMPROVED)
Write-Host "Bot Dashboard wird gestartet..." -ForegroundColor Cyan

while ($true) {
    # Check for pending database restoration
    $restore_file = "instance/app.db.restore_pending"
    if (Test-Path $restore_file) {
        Write-Host "--- DATABASE RESTORE PENDING DETECTED ---" -ForegroundColor Magenta
        
        # Give some time for old handles to clear
        Start-Sleep -Seconds 2
        
        Write-Host "Sichere aktuelle Datenbank..."
        if (Test-Path "instance/app.db") {
            try {
                Move-Item -Path "instance/app.db" -Destination "instance/app.db.bak_$(Get-Date -Format 'yyyyMMdd_HHmm')" -Force -ErrorAction Stop
            } catch {
                Write-Host "Warnung: Konnte app.db nicht sichern (evtl. in Benutzung). Versuche trotzdem Upload..." -ForegroundColor Yellow
            }
        }
        
        Write-Host "Installiere Backup..."
        $retryCount = 0
        $success = $false
        while (-not $success -and $retryCount -lt 10) {
            try {
                Move-Item -Path $restore_file -Destination "instance/app.db" -Force -ErrorAction Stop
                $success = $true
            } catch {
                $retryCount++
                Write-Host "Warte auf Dateifreigabe (Versuch $retryCount/10)..." -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            }
        }
        
        if ($success) {
            Write-Host "Restore erfolgreich abgeschlossen!" -ForegroundColor Green
        } else {
            Write-Host "FEHLER: Backup konnte nicht installiert werden (Datei gesperrt)." -ForegroundColor Red
            # Leave the restore_pending file for next try
        }
    }

    if (Test-Path ".venv\Scripts\Activate.ps1") {
        . .venv\Scripts\Activate.ps1
    }
    
    Write-Host "Starte Flask-Server auf Port 9003..." -ForegroundColor Green
    flask --app web_dashboard.app run --host=0.0.0.0 --port 9003 --debug
    
    Write-Host "Server wurde beendet. Neustart in 5 Sekunden..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
