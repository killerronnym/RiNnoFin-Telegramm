#!/bin/bash
# Updated: 2026-04-11 (Added Restore Logic)

set -e

echo "--- Starting Bot Engine v2 Entrypoint ---"
export BOT_PROCESS=1

# Navigieren zum App-Verzeichnis
cd /app

# Prüfen auf neue Abhängigkeiten
if [ -f "requirements.txt" ]; then
    echo "Checking for dependency updates..."
    pip install --no-cache-dir -r requirements.txt
fi

# PRÜFEN AUF AUSSTEHENDE WIEDERHERSTELLUNG (Backup-Restore)
RESTORE_FILE="instance/app.db.restore_pending"
if [ -f "$RESTORE_FILE" ]; then
    echo "--- !!! DATABASE RESTORE PENDING DETECTED !!! ---"
    
    # Backup der alten DB
    if [ -f "instance/app.db" ]; then
        BACKUP_NAME="instance/app.db.bak_$(date +%Y%m%d_%H%M%S)"
        echo "Backing up current database to $BACKUP_NAME..."
        cp instance/app.db "$BACKUP_NAME"
    fi
    
    echo "Installing new backup..."
    # Wir nutzen 'mv' zum Überschreiben.
    mv "$RESTORE_FILE" instance/app.db
    echo "Database restoration completed successfully!"
fi

echo "Starting Gunicorn Flask server and Master-Bot..."
# Wir stellen sicher, dass die Datenbank (falls konfiguriert) bereit ist.
python3 -c "
try:
    from web_dashboard.app import create_app, db
    app = create_app()
    with app.app_context():
        db.create_all()
    print('Database initialized.')
except Exception as e:
    print('Initial DB query failed (Missing config?). Continuing to Web Setup Wizard...')
" || echo "Initial DB setup deferred."

# Master-Bot im Hintergrund starten
echo "Launching Master-Bot in background..."
python bots/main_bot.py &
BOT_PID=$!
mkdir -p logs
echo $BOT_PID > logs/main_bot.pid

# Dashboard im Vordergrund (bindet an Port 9003)
echo "Launching Gunicorn on port 9003..."
gunicorn --bind 0.0.0.0:9003 --workers 2 --timeout 120 --access-logfile - --error-logfile - "web_dashboard.app:create_app()" &
WEB_PID=$!

# Trap: Wenn der Container gestoppt wird, beenden wir beide Prozesse sauber
cleanup() {
    echo "Stopping processes..."
    kill $BOT_PID $WEB_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "Monitoring Gunicorn (PID: $WEB_PID)..."
wait $WEB_PID

# Falls Gunicorn stoppt, reißen wir den Bot mit in den Abgrund und beenden alles.
kill $BOT_PID 2>/dev/null || true
exit 0
