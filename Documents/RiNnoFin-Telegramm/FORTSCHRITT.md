# RiNnoFin Telegramm - Projektfortschritt & Changelog

Hier ist die umfassende Dokumentation aller Funktionen, Systeme und Fixes, die wir im Rahmen der Entwicklung (insbesondere in den letzten Sitzungen) für das **RiNnoFin Telegramm** Jellyfin-Plugin erarbeitet haben.

---

## 1. 👥 Benutzerverwaltung & Dashboard (Frontend)
- **Komplett neues Dashboard-Design:** Modernes, tab-basiertes UI mit Glassmorphism-Effekten, klaren Farben und intuitiver Navigation (integriert in Jellyfins native Konfigurationsseite).
- **Asynchrone Benutzerliste:** Live-Abruf aller Benutzer inkl. Telegram-Verknüpfungsstatus, E-Mail-Adresse und letztem Zugriff (ohne die Seite neu laden zu müssen).
- **Einladungs-System (Onboarding):** Admins können neue Nutzer per E-Mail einladen. Ein Klick auf den Einladungs-Link führt den Nutzer zu einer interaktiven HTML-Registrierungsseite, auf der er sich sein Passwort aussucht.
- **Berechtigungen Klonen:** Beim Einladen eines neuen Nutzers kann ein "Referenz-Benutzer" (Profil) ausgewählt werden, dessen Jellyfin-Rechte 1:1 kopiert werden.
- **Massenaktionen:** Accounts können direkt aus der Tabelle heraus mit einem Klick aktiviert, deaktiviert oder komplett gelöscht werden.
- **Passwort-Reset:** Admins können einen Passwort-Reset-Link für jeden User generieren und per E-Mail versenden.

## 2. ⏳ Account-Ablauf-System (Expiration)
- **Ablaufdatum konfigurierbar:** Beim Einladen oder Bearbeiten eines Users kann eine Gültigkeit in Tagen festgelegt werden (optional).
- **Live-Countdown:** Im Dashboard wird das Ablaufdatum farblich hervorgehoben (z.B. "Noch 5 Tage" in Grün, "Läuft heute ab" in Gelb, "Abgelaufen" in Rot).
- **Automatisierte Background-Tasks:** Der `UserExpirationTask` prüft täglich im Hintergrund:
  - Sendet eine Vorwarnungs-E-Mail (z.B. 7 Tage vorher).
  - Deaktiviert oder löscht den Account automatisch am Stichtag.
  - Sendet eine finale Benachrichtigungs-E-Mail über die Deaktivierung/Löschung.
- **Definierte Begründungen:** Für das Deaktivieren/Löschen können im Dashboard Vorlagen hinterlegt werden (z.B. "Nicht bezahlt", "Sicherheitsbedenken"), die in der Benachrichtigungs-E-Mail auftauchen.

## 3. 📧 E-Mail- & Benachrichtigungssystem
- **SMTP-Integration:** Vollständige Konfigurationsmöglichkeit für SMTP-Server, Port, TLS, Benutzername und Passwort direkt im Jellyfin-Dashboard.
- **Benutzerdefinierte HTML-Vorlagen:** Admins können die HTML-Vorlagen für "Willkommen/Einladung", "Passwort vergessen", "Passwort Reset Bestätigung" und "Account-Deaktivierung" in Echtzeit im Dashboard editieren.
- **Live-Variablen:** Platzhalter wie `{username}`, `{appName}`, `{resetUrl}` werden dynamisch ersetzt.

## 4. 🤖 Telegram-Integration & SSO
- **Telegram Native Login:** Das Plugin nutzt das offizielle Telegram-Widget für sicheres, passwortloses Login (Single Sign-On).
- **Bot-Kommunikation:** Ein verbundener Telegram-Bot reagiert auf Befehle wie `/start`, `/ping`, `/help` und sendet Alerts an definierte Administratoren.
- **Newsletter-Support:** Nutzer können sich (zukünftig) über den Bot für Newsletter (Musik, Serien, Filme) an- und abmelden.
- **Notfall-Benachrichtigungen:** Der Bot kann Meldungen über Server-Status oder ablaufende Accounts direkt in eine Administrator-Gruppe pushen.

## 5. 🛠️ Stabilität, Caching & Notfall-Systeme (Heute gelöst)
- **Cache-Busting:** Eine hochentwickelte Versionierung (`RiNnoFinTelegramm_v10453.js`) wurde eingeführt, die den Browser **zwingt**, nach Updates immer die neueste UI zu laden (löst das "Aufhängen" der Seite).
- **Javascript-Sicherheitsnetz (`try-catch`):** Das Frontend wurde so gehärtet, dass kaputte Datensätze (z.B. ungültige Datumsformate wie `0001-01-01`) abgefangen werden. Anstatt abzustürzen, zeigt die UI nun saubere Fehler an.
- **Doppelte E-Mails verhindert:** Buttons werden während des asynchronen Ladevorgangs hard-deaktiviert.
- **Notfall-Logs (Neu):** Sollte das Jellyfin-Dashboard jemals komplett ausfallen, können die systeminternen Plugin-Logs jederzeit direkt über den Browser-Link `http://[IP]:8096/api/RiNnoFinConfig/ViewLogs` ausgelesen werden – **ohne** Admin-Sitzung.

---

### Aktueller Meilenstein-Status
- Version: **v1.0.4.53**
- Stabilitäts-Level: **Produktionsnah (RC - Release Candidate)**
- Fokus für die kommenden Schritte: Telegram-Integration für den Newsletter-Versand vervollständigen und Feinschliff des Bots.

---

## 6. 📝 To-Do Liste (Anstehende Aufgaben)
Folgende Kernfunktionen werden als Nächstes umgesetzt, um das Plugin zu komplettieren:

1. ~~**Einladungen erneut senden Button:** Ein einfacher Button in der Benutzerliste ("Einladung erneut senden"), falls ein Nutzer seine initiale Einladungs-E-Mail gelöscht, nicht erhalten oder der Link abgelaufen ist.~~ (Erledigt)
2. ~~**Klares E-Mail-Log im Dashboard:** Ein eigener Reiter im Administrations-Panel, der übersichtlich auflistet, welche E-Mails verschickt wurden und ob sie erfolgreich beim Nutzer ankamen (Zustellstatus).~~ (Erledigt)
3. ~~**Self-Service Webportal für Nutzer:** Eine eigenständige Web-Oberfläche für die normalen Nutzer (getrennt vom Admin-Dashboard und Telegram). Hier kann der Nutzer selbstständig seine E-Mail-Adresse verwalten, Newsletter-Abonnements steuern und sein Telegram-Konto verknüpfen.~~ (Erledigt)
4. ~~**Optimierter Medien-Newsletter (E-Mail):**~~ (Erledigt)
   ~~- **Sammel-E-Mails (Digest):** Filme und Serien werden gebündelt in **einer einzigen** E-Mail zusammengefasst, anstatt getrennt verschickt zu werden.~~
   ~~- **Einstellbares Intervall:** Der Admin kann einstellen, wie oft die E-Mail verschickt wird (Täglich, Wöchentlich, Zweimal pro Woche, Monatlich).~~
   ~~- **Schöne Cover & Infos:** Jedes Medium bekommt ein hochauflösendes Titelbild, den Filmtitel und eine Beschreibung (Handlung).~~
   ~~- **Serien-Details:** Bei Serien wird zusätzlich angezeigt, wie viele neue Episoden/Staffeln verfügbar sind.~~
   ~~- **Echte Bibliotheks-Namen:** Anzeige der echten Jellyfin-Bibliothek (z.B. "Netflix", "Disney") anstelle der rohen Server-Dateipfade.~~
   ~~- **Direkt-Abspielen-Button:** Ein schicker Button unter jedem Film/jeder Serie, mit dem der Nutzer sofort in Jellyfin landet und den Stream starten kann.~~

---

## 7. 🤖 Telegram-Integration: Status & To-Do Liste

Damit der Bot als echter, professioneller Assistent agiert, haben wir folgenden Status und Fahrplan:

### ✅ Was bereits funktioniert (Erledigt)
- **Single Sign-On (SSO):** Sicheres, passwortloses Einloggen in Jellyfin über das native Telegram-Widget.
- **Basis-Befehle:** Der Bot reagiert auf `/start`, `/ping` und `/help` und gibt je nach Account (Admin vs. Nutzer) angepasste Antworten.
- **Gruppen-Integration:** Test-Benachrichtigungen können aus dem Dashboard direkt in eine definierte Telegram-Admin-Gruppe gesendet werden.

### 📝 Was noch fehlt (Telegram To-Do Liste)
1. **Newsletter-System (Push-Benachrichtigungen):**
   - Nutzer können über den Bot Kategorien abonnieren (Filme, Serien).
   - Der Bot sendet automatisiert ansprechend formatierte Nachrichten (inkl. Filmposter und Link), sobald neue Medien zu Jellyfin hinzugefügt werden.
2. **Medien-Wünsche (Request-System):**
   - Nutzer können per Befehl (z.B. `/wunsch Deadpool 3`) Medien anfragen.
   - Der Bot sendet diese Anfrage in die Admin-Gruppe mit interaktiven **[Annehmen]** / **[Ablehnen]** Buttons.
   - Der Nutzer wird automatisch über die Entscheidung benachrichtigt.
3. **Interaktive Klick-Menüs:**
   - Ersetzen der reinen Text-Befehle durch dauerhafte, grafische Menü-Buttons (Inline Keyboards) im Chat, um die Bedienung kinderleicht zu machen.
4. **Passwort-Reset via Bot:**
   - Ein Klick-Button im Bot, der dem Nutzer sofort einen sicheren Passwort-Reset-Link generiert und zuschickt, als Alternative zur E-Mail.
5. **Ablauf-Warnungen per Chat:**
   - Automatischer Versand der "Account läuft ab"-Warnungen direkt als Telegram-Nachricht an den Nutzer (ergänzend zur E-Mail).
