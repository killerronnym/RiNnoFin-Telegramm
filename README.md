# 🚀 RiNnoFin Telegramm - Das ultimative Jellyfin-Plugin

Das **RiNnoFin Telegramm Plugin** ist die ultimative Erweiterung für deinen Jellyfin Media-Server. Es verbindet deinen Jellyfin-Server nahtlos mit einem interaktiven Telegram-Bot, bietet ein professionelles Onboarding- und Einladungssystem und bringt vällig neue Funktionen in dein Heimkino – alles ganz ohne externe Drittanbieter-Tools!

![Dashboard UI](https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/rinnofin_plugin_cover.png)

---

## 🌟 Hauptfunktionen

### 1. 🛡️ Integriertes Onboarding & Einladungs-System
Als Administrator verwaltest du neue Benutzer direkt in deinem neuen Jellyfin Dashboard Tab.
*   **Einladungen (HTML E-Mail):** Der Admin versendet Einladungen per Klick an die E-Mail-Adressen von Freunden. 
*   **Profil-Cloning:** Wähle bei der Einladung direkt aus, von welchem bestehenden Nutzer die Berechtigungen und Ansichten geklont werden sollen.
*   **Self-Service-Setup (`invite.html`):** Der Nutzer klickt auf den Link und landet auf einer modernen Webseite, wo er sich seinen Wunschnamen und sein Passwort selbst aussucht. Das Konto wird automatisch auf dem Server angelegt.

### 2. 🔐 SSO & Telegram-Bot Verknüpfung
*   **SSO Login:** Nutzer können sich über einen schicken blauen "Mit Telegram anmelden"-Button auf der Jellyfin-Startseite einloggen.
*   **Chat-Verknüpfung:** Der Nutzer schreibt dem Bot `/verbinden` auf Telegram. Der Bot fragt interaktiv die E-Mail und das Passwort ab und verknüpft das Konto hochsicher mit dem Jellyfin-Account.

### 3. 🍿 Intelligenter Newsletter & Ankündigungen
*   **Newsletter:** Regelmäßige Zusammenfassungen über neue Filme, Serien und Episoden werden automatisch an die Nutzer verschickt – entweder per stylischer HTML-E-Mail, per Telegram-Nachricht oder beidem. Jeder Nutzer kann seine Vorlieben individuell abonnieren.
*   **Ankündigungs-Center:** Administratoren können direkt aus dem Jellyfin-Dashboard Ankündigungen, Systemmeldungen oder Umfragen an alle Nutzer via E-Mail/Telegram heraussenden. HTML-Vorlagen sind vollständig editierbar.

### 4. 🎛️ Professionelles Administrator-Dashboard
*   **Nutzerverwaltung:** Übersichtliche Tabelle mit allen Jellyfin-Nutzern. Administratoren können Passwörter zurücksetzen, Konten (de-)aktivieren, löschen oder Newsletter-Abonnements manuell anpassen.
*   **Live-Log:** Ein dediziertes Log-System direkt im Dashboard, das Einladungen, Telegram-Verknüpfungen und E-Mail-Fehler transparent aufzeichnet.
*   **Schutz-System:** Der Haupt-Administrator des Servers kann weder gelöscht noch deaktiviert werden.

### 5. 🤖 Interaktive Telegram-Kommandos
Nutzer können den Server direkt über den Chat steuern:
*   `/wunsch <Titel>` – Einen Wunsch (Film/Serie) beim Admin einreichen.
*   `/passwort` – Ein sicherer Link, um das Kennwort eigenständig zurückzusetzen.
*   `/rueckblick` – Einen wöchentlichen Rückblick der Mediathek anfordern.
*   `/newsletter` – Abonnements für E-Mails/Telegram verwalten.

---

## 🛠️ Installation via Repository (Empfohlen)

Die beste Methode, um immer automatisch die neuesten Updates zu erhalten!

1. Öffne dein Jellyfin und melde dich als **Administrator** an.
2. Gehe in dein **Dashboard** (Administrator-Einstellungen).
3. Scrolle auf der linken Seite nach unten und klicke auf **"Erweitert" -> "Plugins"**.
4. Wechsle oben auf den Reiter **"Repositories"** (Paketquellen).
5. Klicke auf das **"+" (Hinzufügen)**-Symbol und trage folgende Daten ein:
   *   **Name:** `RiNnoFin Telegramm`
   *   **Repository-URL:** `https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/manifest.json`
6. Klicke auf **Speichern** und wechsle in den Reiter **"Katalog"**.
7. Wähle *RiNnoFin Telegramm* (unter "Integration"), klicke auf die neueste Version und drücke **Installieren**.
8. **Starte deinen Jellyfin-Server einmal neu.**
9. Unter **Dashboard -> Plugins -> RiNnoFin Telegramm** kannst du nun deinen Telegram-Bot-Token und deine SMTP-Server-Daten eintragen!

---

## 💬 Alle Telegram-Befehle im Überblick

### Für alle Nutzer:
*   `/start` – Zeigt eine Begrüßung und die Liste aller verfügbaren Befehle.
*   `/verbinden` – Startet den sicheren, interaktiven Prozess zur Verknüpfung von Jellyfin und Telegram.
*   `/unlink` – Hebt die Verknüpfung der Accounts auf.
*   `/passwort` – Sendet dir einen privaten Link zum Ändern deines Passworts.
*   `/newsletter` – Öffnet das Menü, um Telegram- und E-Mail-Abonnements zu verwalten.
*   `/wunsch <Film/Serie>` – Reicht einen Medien-Wunsch beim Administrator ein.
*   `/rueckblick` – Ruft eine Liste kürzlich hinzugefügter Medien ab.
*   `/ping` – Ein kleiner Verbindungstest.

### Exklusiv für Administratoren (Bot-Admins):
*   `/userlist` – Listet alle Nutzer inklusive deren Verbindungs- und Abonnement-Status auf.
*   `/stats` – Zeigt Systeminformationen, Ressourcen und Medien-Statistiken des Jellyfin-Servers an.

---

## 💡 Systemvoraussetzungen
- Jellyfin Version **10.9.x** oder höher.
- Ein konfigurierter **SMTP-Server** (z. B. Gmail, Outlook oder ein eigener Mailserver) zum Versenden der HTML-E-Mails.
- Ein **Telegram Bot-Token** (kostenlos erstellbar über den [@BotFather](https://t.me/botfather) in Telegram).
