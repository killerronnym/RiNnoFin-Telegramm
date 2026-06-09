# 🎬 RiNnoFin Telegramm - Das ultimative Jellyfin-Plugin

Das **RiNnoFin Telegramm Plugin** ist die ultimative Erweiterung für deinen Jellyfin Media-Server. Es verbindet deinen Jellyfin-Server nahtlos mit einem interaktiven Telegram-Bot und bringt völlig neue, professionelle Funktionen in dein Heimkino – und das alles ganz ohne externe Drittanbieter-Tools wie JFA-Go!

---

## ✨ Was kann das Plugin?

### 📧 1. Autonome Benutzerverwaltung & E-Mail-System
Das Plugin besitzt einen eigenen, nativen E-Mail-Server (SMTP). Wenn du neue Freunde auf deinen Server einlädst, läuft das hochprofessionell ab:
*   **Einladungen via Telegram:** Als Admin gibst du im Chat einfach `/NeuBenutzer <E-Mail>` ein. Das Plugin generiert einen sicheren Token und schickt dem Nutzer eine wunderschön designte E-Mail mit einem Setup-Link.
*   **Self-Service-Setup (`invite.html`):** Der Nutzer klickt auf den Link und landet auf einer modernen Webseite, wo er sich seinen Wunschnamen und sein Passwort **selbst** aussuchen kann. Das Konto wird automatisch auf deinem Server angelegt.
*   **Passwort-Recovery:** Nutzer haben ihr Passwort vergessen? Kein Problem! Auf der Login-Seite gibt es jetzt einen "Passwort vergessen"-Button (`forgot.html`). Die Nutzer fordern einen Reset-Link per E-Mail an und können ihr Passwort auf `reset.html` völlig autark zurücksetzen. Kein Eingreifen des Admins nötig!

### 🔒 2. Single Sign-On (Telegram-Login)
Nutzer müssen sich nie wieder Passwörter merken. Dank der SSO-Integration erscheint auf der Jellyfin-Login-Seite ein schicker, blauer "Mit Telegram anmelden"-Button. Ein Klick, und der Nutzer ist eingeloggt!

### 🍿 3. Der intelligente Medien-Newsletter
Dein Telegram-Bot hält alle Nutzer auf dem Laufenden!
*   **Automatische Benachrichtigungen:** Sobald du neue Filme, Serienepisoden oder Musikalben hinzufügst, schickt der Bot eine Nachricht mit Cover, Inhaltsangabe (deutsch), Genre, Jahr und direkten Links zu IMDb/TMDb und Jellyfin.
*   **Personalisiert:** Jeder Nutzer kann über den Telegram-Befehl `/newsletter` per Knopfdruck selbst entscheiden, welche Bibliotheken er abonnieren möchte. 

### 🎮 4. Extras für den Telegram-Chat
*   **Passwort per Chat ändern:** Über den Befehl `/passwort <NeuesPasswort>` kann man sein Kennwort sogar direkt im Chat ändern.
*   **Quiz-Bot:** Langeweile? Der Befehl `/quiz` liest deine Jellyfin-Bibliothek aus und stellt den Nutzern lustige Quizfragen ("Aus welchem Jahr stammt dieser Film?" oder "Wer spielt hier mit?").
*   **Admin-Statistiken:** Als Admin kannst du per `/stats` sofort sehen, wie viele Medien und Benutzer du hast, oder per `/userlist` prüfen, welcher Telegram-Account mit welcher E-Mail verknüpft ist.

---

## 📦 Wie installiere ich das Plugin in meinem Jellyfin?

Es gibt zwei einfache Wege, das Plugin auf deinem Jellyfin-Server zu installieren:

### Methode A: Installation via Repository (Automatische Updates - Empfohlen)

Du kannst dieses GitHub-Repository direkt als Update-Quelle in deinem Jellyfin-Server registrieren. Das ist der empfohlene Weg, damit du neue Versionen immer per Knopfdruck installieren kannst.

1. Öffne dein Jellyfin und melde dich als **Administrator** an.
2. Gehe in dein **Dashboard** (Administrator-Einstellungen).
3. Scrolle auf der linken Seite ganz nach unten und klicke auf **"Erweitert" -> "Plugins"**.
4. Wechsle oben auf den Reiter **"Repositories"** (Paketquellen).
5. Klicke auf das **"+" (Hinzufügen)**-Symbol.
6. Trage folgende Daten ein:
   *   **Name:** `RiNnoFin Telegramm`
   *   **Repository-URL:** `https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/manifest.json`
7. Klicke auf **Speichern**.
8. Wechsle nun in den Reiter **"Katalog"**. Dort findest du das Plugin *RiNnoFin Telegramm* unter der Kategorie "Integration".
9. Klicke darauf, wähle die **neueste Version** und drücke auf **Installieren**.
10. **Starte deinen Jellyfin-Server einmal neu.**
11. Gehe zurück ins Dashboard -> Plugins. Klicke auf "RiNnoFin Telegramm" und trage dort unter den Einstellungen deinen **Telegram-Bot-Token** und deine **SMTP-E-Mail-Daten** ein. Speichern – fertig!

### Methode B: Manuelle Installation (Direkter Upload)

Dies ist die schnellste Methode, wenn du die Plugin-Datei manuell auf deinen Server hochladen möchtest:

1. **Ordner erstellen**:
   Navigiere in das Plugin-Verzeichnis deines Jellyfin-Servers:
   *   **Windows (Standard):** `C:\ProgramData\Jellyfin\Server\plugins\`
   *   **Linux/Docker:** Das entsprechende gemappte `/config/plugins/`-Volume.
   
   Erstelle dort einen neuen Unterordner mit dem genauen Namen:
   `RiNnoFinTelegramm`

2. **DLL einfügen**:
   Lade die Datei **`Jellyfin.Plugin.RiNnoFinTelegramm.dll`** aus dem Ordner `publish_release` dieses Repositories herunter und lege sie in den eben erstellten Ordner:
   `.../plugins/RiNnoFinTelegramm/Jellyfin.Plugin.RiNnoFinTelegramm.dll`

3. **Server-Neustart**:
   Starte deinen Jellyfin-Server neu. Das Plugin wird geladen und ist im Jellyfin-Dashboard unter **Plugins** aktiv.

---

## 🤖 Bot-Befehle im Überblick

### Im privaten Chat (Für alle Benutzer)
*   `/start` — Zeigt eine Begrüßung und die Liste aller verfügbaren Befehle.
*   `/ping` — Ein kleiner Verbindungstest (Bot antwortet mit "Pong! 🏓").
*   `/link` — Erzeugt einen Button für den Telegram-SSO-Login (Verknüpft Telegram mit Jellyfin).
*   `/unlink` — Hebt die Verknüpfung der Accounts auf.
*   `/passwort <neues_passwort>` — Ändert dein Jellyfin-Passwort direkt über den Chat.
*   `/newsletter` — Öffnet das interaktive Menü für die Benachrichtigungen.
*   `/quiz` — Startet das kleine Film/Serien-Ratespiel.

### Exklusiv für Administratoren
*   `/NeuBenutzer <E-Mail>` — Generiert eine Einladung und schickt sie an den neuen Nutzer.
*   `/userlist` — Listet verknüpfte Benutzer, IDs und registrierte E-Mail-Adressen auf.
*   `/stats` — Zeigt Systeminformationen, Ressourcen und Medien-Statistiken des Jellyfin-Servers an.
