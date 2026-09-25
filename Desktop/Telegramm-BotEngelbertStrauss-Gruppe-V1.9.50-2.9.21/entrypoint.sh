#!/bin/bash
# Updated: 2026-04-11 (Added Restore Logic)
set -e

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
    mv "$RESTORE_FILE" instance/app.db
    echo "Database restoration completed successfully!"
fi

# Initialisiere die Datenbank, falls nötig
echo "Initialisiere Datenbank..."
python scripts/init_db.py
python scripts/migrate_db.py

# Starte das Web-Dashboard im Hintergrund
echo "Starte Web-Dashboard..."
python web_dashboard/app.py &

# Warte kurz, damit das Dashboard hochfahren kann
sleep 5

# Starte die Bots
echo "Starte Bots..."

# ID Finder Bot
if [ -f "bots/id_finder_bot/id_finder_bot.py" ]; then
    echo "Starte ID Finder Bot..."
    python bots/id_finder_bot/id_finder_bot.py &
fi

# Invite Bot
if [ -f "bots/invite_bot/invite_bot.py" ]; then
    echo "Starte Invite Bot..."
    python bots/invite_bot/invite_bot.py &
fi

# Outfit Bot
if [ -f "bots/outfit_bot/outfit_bot.py" ]; then
    echo "Starte Outfit Bot..."
    python bots/outfit_bot/outfit_bot.py &
fi

# Quiz Bot
if [ -f "bots/quiz_bot/quiz_bot.py" ]; then
    echo "Starte Quiz Bot..."
    python bots/quiz_bot/quiz_bot.py &
fi

# TikTok Bot
if [ -f "bots/tiktok_bot/tiktok_bot.py" ]; then
    echo "Starte TikTok Bot..."
    python bots/tiktok_bot/tiktok_bot.py &
fi

# Umfrage Bot
if [ -f "bots/umfrage_bot/umfrage_bot.py" ]; then
    echo "Starte Umfrage Bot..."
    python bots/umfrage_bot/umfrage_bot.py &
fi

# Halte den Container am Leben, solange Prozesse laufen
wait
