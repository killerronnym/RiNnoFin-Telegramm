# Release Notes v2.9.5
**Datum:** 19. Mai 2026

Diese Version führt eine vollständige, sichere **Moderator-Rolle** im System ein. Sie sperrt und verbirgt alle administrativen Cockpit-Bereiche, Module und API-Funktionen für Moderatoren und stellt gleichzeitig sicher, dass das System durch automatische Schema-Heilung fehlerfrei und ohne manuelle Datenbankschritte aktualisiert werden kann.

---

## 🚀 Neue Funktionen & Änderungen

### 1. 🛡️ Moderator-Rolle & Zugriffsschutz
* **Modul-Sperren (Seitenleiste & Cockpit-Kacheln):**
  * **Kritische Logs** (Ausgeblendet & `@admin_required` geschützt)
  * **Minecraft Server Status** (Ausgeblendet & `@admin_required` geschützt)
  * **Steckbrief Zentrale** (Ausgeblendet & `@admin_required` geschützt)
  * **Geburtstags-Bot** (Ausgeblendet & `@admin_required` geschützt)
  * **Einladungs-Bot** (Ausgeblendet & `@admin_required` geschützt)
* **ID-Finder Cockpit Einschränkungen:**
  * Die Schnellzugriffs-Schaltflächen für das **Admin Panel** und die **Moderation Einstellungen** werden für Moderatoren komplett ausgeblendet und sind nicht mehr anwählbar.
  * Backend-seitiger Schutz aller zugehörigen Administrator-Routen.

### 2. ⚡ Security- & API-Fehlerbehebungen
* **Flash-Meldungen auf der Übersicht behoben:**
  * Wenn ein Moderator auf die Startseite kam, wurden im Hintergrund automatische Prüfungen für System-Updates und GitHub-Einstellungen durchgeführt (`/api/system/settings`). Da diese Admin-Rechte erfordern, wurde zuvor eine Fehlermeldung in der Session gespeichert. Das führte dazu, dass der Moderator beim Navigieren fälschlicherweise die Meldung *"Zugriff verweigert. Diese Aktion erfordert Admin-Rechte."* auf der Übersicht sah.
  * **Lösung:** Das Update-JavaScript wird für Moderatoren nun gar nicht erst gerendert und geladen. Zusätzlich brechen die Backend-Dekoratoren bei API-Aufrufen direkt mit einem sauberen `403 Forbidden` ab, ohne irreführende Flash-Meldungen in die Session zu schreiben.

### 3. ⚙️ Automatische Schema-Heilung
* **Selbstheilendes Datenbankschema:**
  * Beim Start des Dashboards prüft das System selbstständig, ob neue Spalten (wie `role` oder `permissions_json` in der User-Tabelle) in der Datenbank fehlen. Falls ja, werden diese über ein automatisiertes `ALTER TABLE` hinzugefügt.
  * **Wichtig:** Keine manuellen Migrationsschritte für Datenbanken erforderlich! Das Update kann einfach eingespielt werden und funktioniert sofort.

---

## 📋 Standard GitHub Release Workflow
Um das Update auf der Synology NAS (Docker-Deployment) einzuspielen, wird folgender standardisierter Ablauf genutzt:

1. **Versionsnummer prüfen:** Die Datei `version.json` wurde bereits auf Version `2.9.5` aktualisiert.
2. **Commit & Push:**
   ```powershell
   git add .
   git commit -m "VERSION [v2.9.5]: Moderator role implementation & security fixes"
   git push origin main
   ```
3. **GitHub Release erstellen:**
   * Ein neues Release auf GitHub erstellen mit dem Tag `v2.9.5` und dem Titel `Version v2.9.5`.
   * Diese Release-Notes als Beschreibung einfügen.
4. **Verifizierung:**
   * Das Dashboard aufrufen und auf "Nach Updates scannen" klicken, um sicherzustellen, dass die neue Version vom Updater-Skript erkannt wird.
