# Changelog

Alle signifikanten Änderungen an diesem Projekt werden hier dokumentiert.

## [1.9.70] - 2026-04-17

### ✨ Neu
- **Topic 24h Cleanup System**: Nachrichten in spezifischen Topics können nun automatisch nach x Stunden gelöscht werden.
- **Transparente Verwaltung**: Neues Dashboard-Feld zur Verwaltung mehrerer Cleanup-Topics gleichzeitig.
- **Integrierter Schutz**: Bot-Nachrichten werden niemals gelöscht; Admin-Nachrichten können optional geschützt werden.

## [1.9.65] - 2026-04-17

### ✨ Neu
- **GitHub Integration UI**: Update-Einstellungen (Token, Repo) können nun direkt über das "Software Update" Fenster auf der Startseite vorgenommen werden.
- **System-Management**: Zentrale Speicherung von System-Config in der Datenbank statt nur in der .env-Datei.

## [1.9.52] - 2026-04-17

### ✨ Neu
- **Admin-Button "Erneut abschicken"**: Auch neue Mitglieder haben nun nach der Freischaltung die Schaltfläche im Admin-Kanal, um den Steckbrief manuell erneut zu posten.

### 🛠️ Fixes & Verbesserungen
- **Dynamische Ablehnung bei Updates**: Bestehende Nutzer erhalten nun bei einer Ablehnung ihres Updates ebenfalls die Nachricht aus dem Dashboard (statt eines Standardtexts).
- **Indentation Fix**: Ein kleiner Einrückungsfehler in der Konfigurationsdatei wurde behoben.

## [1.9.50] - 2026-04-17

### ✨ Neu
- **Private Update Support**: Unterstützung für Software-Updates aus privaten GitHub-Repositories via Personal Access Token (PAT).
- **Admin-Profil-Links**: In Whitelist-Anfragen wird nun direkt ein klickbarer Link zum Telegram-Profil des Nutzers angezeigt, damit Admins Einreicher sofort prüfen können.
- **Custom Notifications**: Whitelist-Ablehnungsnachrichten, "Warten auf Freischaltung"-Meldungen und Erfolgsmeldungen können nun direkt im Dashboard angepasst werden.

### 🛠️ Fixes & Verbesserungen
- **BadRequest Fix**: Absturz des Invite-Bots bei leeren Ablehnungsnachrichten behoben.
- **Timeout Protection**: Zeitlimit für Avatar-Downloads im ID-Finder auf 45 Sekunden erhöht, um Netzwerkfehler zu vermeiden.
- **UI Optimierung**: Dashboard-Anpassungen für eine bessere Verwaltung der automatischen Nachrichten.

## [1.9.6] - 2026-03-01

### 🛠️ Fixes & Verbesserungen
- **Geburtstags-Bot UI**: Ein Bug wurde behoben, durch den der "Hinzufügen"-Button nicht funktionierte (invalid DOM structure im Table).
- **Telegram Bot**: Ein Parse-Fehler für Markdown wurde behoben, der dazu führte, dass der Bot nicht auf `/gb` bzw. `/geburtstag` reagierte.

## [1.9.5] - 2026-03-01

### 🛠️ Fixes & Verbesserungen
- **Version Bump**: Kleine Anpassung der Versionsnummer auf 1.9.5 nach erfolgreichem Hotfix für das Datenbank-Update-Skript.

## [1.9.4] - 2026-03-01

### 🛠️ Fixes & Verbesserungen
- **Geburtstags-Bot UI Fixes**: Ein universelles Datenbank-Update-Skript (`update_db.py`) für MySQL/MariaDB bereitgestellt, um einen 500 Internal Server Error Fehler im Dashboard aufgrund fehlender Jahres-Spalten abzufangen.

## [1.9.3] - 2026-03-01

### 🛠️ Fixes & Verbesserungen
- **Token Handling**: Vorbereitungen und Dashboard-Fixes für den Umgang mit leeren Tokens in der SQLite-Datenbank.
- **Diagnostics**: Neue Diagnoseskripte für Datenbank-Checks hinzugefügt.

## [1.9.2] - 2026-03-01

### ✨ Neu
- **Datenbank Backup**: Administratoren können nun direkt über das Dashboard eine Sicherungskopie der `app.db` herunterladen. Dies dient zur lokalen Sicherung und zur Vorbeugung von Datenverlust bei Docker-Updates.

## [1.9.1] - 2026-03-01

### 🛠️ Behobene Fehler (Fixes)
- **Auto-Updater Docker Fix**: Der Auto-Updater behält beim Entpacken des ZIP-Archivs nun die ausführbaren Datei-Rechte (`chmod +x`) für `docker-entrypoint.sh` bei. Dies verhindert Abstürze beim Docker-Neustart (`permission denied`).

## [1.9.0] - 2026-03-01

### ✨ Neu
- **Geburtstags-Bot**: Gruppenmitglieder können ihren Geburtstag über `/gb DD MM` oder `/geburtstag DD.MM.` eintragen. Der Bot gratuliert automatisch zur konfigurierten Zeit (z.B. um 00:01). Inklusive Dashboard-Integration zur Verwaltung der Geburtstage, Texte und Uhrzeiten.

## [1.8.13] - 2026-02-28

### 🛠️ Behobene Fehler (Fixes)
- **Dashboard**: Jinja2 Template-Syntax-Fehler beim Aufruf des Profanity-Filters behoben (`endblock`).

## [1.8.11] - 2026-02-28

### ✨ Neu
- **Beleidigungsmanagement (Profanity Filter)**: Eine neue Blacklist für verbotene Wörter inklusive Google-Profanity Imports und automatischer Verwarnung.

## [1.0.0] - 2026-02-24

### ✨ Neu
- **Automatisches Software-Update**: Hintergrund-Task (APScheduler) prüft alle 6 Stunden auf neue Releases.
- **Auto-Installation**: Dashboard kann Updates jetzt selbstständig herunterladen und installieren (inkl. Windows-Auto-Restart Loop).
- **MySQL Migration**: Vollständige Unterstützung für MariaDB/MySQL inklusive Migrations-Skript (`migrate_to_mysql.py`).
- **Live-Moderation v2**: Komplett überarbeitetes Dashboard zur Echtzeit-Überwachung von Gruppen.

### 🛠️ Behobene Fehler (Fixes)
- **Conflict Error**: Automatischer Cleanup von PID-Dateien und Geister-Prozessen bei Bot-Start.
- **SQL Syntax**: Kompatibilitätsprobleme mit `EXTRACT(DOW)` unter MariaDB behoben.
- **UTF-8 Encoding**: Abstürze auf Windows-Systemen durch Unicode-Fehler in den Logs behoben.
- **Token Migration**: Fehlerhafte Token-Zuweisung nach DB-Migration korrigiert.

### ⚙️ Geändert
- **Startup**: `devserver.ps1` nutzt nun eine Endlosschleife, um nach Updates automatisch neu zu starten.
- **Shared Utils**: Zentralisiertes Environment-Loading für alle Bot-Subprozesse verbessert.

---
*Status: Stable Release*
