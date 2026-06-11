# RiNnoFin Telegramm & E-Mail Plugin - Dokumentation
*Stand: v1.0.4.33*

Dieses Dokument bietet einen vollständigen Überblick über die Funktionen, den Registrierungsprozess und die Hintergrundprozesse des RiNnoFin Jellyfin Plugins.

---

## 1. Registrierung & Onboarding-Prozess

Das Plugin bietet ein modernes Einladungs- und Registrierungssystem, das es dem Server-Administrator ermöglicht, neue Nutzer sicher einzuladen.

1. **Einladung:** Der Admin generiert im Jellyfin Dashboard unter "RiNnoFin Telegramm -> E-Mail Einstellungen" eine Einladung (über das Brief-Symbol) an die E-Mail-Adresse des neuen Nutzers. Optional kann direkt ein "Kopier-Profil" gewählt werden (z.B. damit der Nutzer die gleichen Freigaben wie Profil XY hat).
2. **E-Mail Versand:** Der Nutzer erhält eine HTML-formatierte E-Mail mit einem eindeutigen, zeitlich begrenzten Einladungs-Link.
3. **Konto-Erstellung:** Klickt der Nutzer auf den Link, gelangt er zu einer Registrierungsseite (`/sso/Telegram/invite`). Dort wählt er sich einen Benutzernamen und ein sicheres Passwort.
4. **Konto-Erstellung in Jellyfin:** Das Plugin erstellt den Jellyfin-Account, klont bei Bedarf die Rechte des Vorlage-Profils und speichert die E-Mail-Adresse im System (`TelegramUserLinks`).
5. **Willkommens-Mail:** Im Anschluss bekommt der neue Nutzer automatisch eine "Willkommens-E-Mail" mit seinem gewählten Benutzernamen und dem direkten Link zum Server-Login.

---

## 2. Telegram Bot & Konto-Verknüpfung (SSO)

Das Plugin stellt eine nahtlose Verbindung zwischen Telegram und Jellyfin her.

### 2.1 Verknüpfungsprozess
1. Der Nutzer startet den Bot in Telegram (`/start`) oder klickt im Bot-Menü auf "Verbinden".
2. Der Bot antwortet mit einem **personalisierten SSO-Link** (Single Sign-On). Dieser Link enthält einen sicheren Token und den Parameter `?action=link`.
3. Klickt der Nutzer den Link an, öffnet sich der Browser.
    - **Ist der Nutzer bereits im Browser bei Jellyfin eingeloggt**, erkennt das Plugin dies automatisch anhand der Session (via `jellyfinuserid`) und verknüpft das Telegram-Konto sofort und unsichtbar mit dem Jellyfin-Account.
    - **Ist der Nutzer nicht eingeloggt**, erscheint kurz die Login-Maske. Nach erfolgreichem Login wird die Verknüpfung im Hintergrund hergestellt.
4. Der Bot schickt sofort eine Bestätigung ("Erfolgreich verknüpft!").

### 2.2 Bot-Kommandos
Nutzer (und Administratoren) haben in Telegram verschiedene Befehle zur Verfügung:
- `/start` - Startet den Bot und erklärt die grundlegenden Funktionen.
- `/verbinden` - Generiert den SSO-Link zur Kontoverknüpfung.
- `/unlink` - Hebt die Verknüpfung zwischen Telegram und dem Jellyfin-Konto wieder auf.
- `/passwort` - Sendet einen sicheren Link, um das Jellyfin-Passwort zurückzusetzen.
- `/newsletter` - Erlaubt dem Nutzer, die Benachrichtigungen an-/abzuschalten.
- `/wunsch` - Ermöglicht es, einen Film- oder Serienwunsch an den Admin zu senden.
- `/rueckblick` - Schickt manuell den Wochenrückblick für die aktuelle Woche ab.
- `/ping` - Verbindungstest, um zu prüfen, ob der Bot noch aktiv ist.

**Für Administratoren:**
- `/userlist` - Zeigt eine Liste aller Jellyfin-Nutzer, deren Status (Aktiv/Gesperrt) und ihre Telegram-Namen.
- `/stats` - Zeigt Server-Statistiken (CPU, RAM, aktiver Stream-Count etc.).
- Administratoren (Bot-Admins) erhalten außerdem Benachrichtigungen bei neuen Logins oder fehlerhaften Anmeldeversuchen.

---

## 3. Benachrichtigungen (E-Mail & Telegram)

Das Benachrichtigungssystem ist in zwei Ebenen unterteilt: **Live-Benachrichtigungen** (über Telegram) und **gebündelte Newsletter** (über E-Mail).

### 3.1 Live-Benachrichtigungen (Telegram)
Sobald neue Inhalte zum Server hinzugefügt werden, reagiert das System fast in Echtzeit:
- **Filme:** Werden sofort und einzeln mit Titelbild, Ordner und Beschreibung an Telegram gesendet.
- **Serien / Episoden:** Das Plugin bündelt neu hinzugefügte Episoden einer Serie kurz (30 Sekunden). Danach wird *eine* Nachricht (z.B. "Staffel 1 - Episode 1 bis 10") verschickt, um Spam zu vermeiden.

### 3.2 Gebündelte E-Mail Newsletter (Live-Batch)
Damit E-Mail-Postfächer nicht mit Einzel-Mails bei größeren Uploads geflutet werden, nutzt das Plugin hier Hintergrund-Tasks:
- Der Task **"RiNnoFin E-Mail Newsletter (Live-Batch)"** läuft standardmäßig alle 2 Stunden im Hintergrund.
- Er sammelt alle neu hinzugefügten Filme und Serien, die seit seinem letzten Lauf dazu kamen.
- Er schickt anschließend **eine** strukturierte HTML-Mail mit allen Filmen ("Neue Filme") und **eine** mit allen Serien ("Neue Serien") an die E-Mail-Nutzer. Die Vorlagen für diese Mails lassen sich im Dashboard bearbeiten.

### 3.3 Der Wochenrückblick (Weekly Digest)
Jeden Freitag läuft zusätzlich der Task **"Wochenrückblick"**. Dieser aggregiert alle neuen Inhalte der gesamten letzten 7 Tage und schickt sie sowohl als Telegram-Nachricht als auch als hübsch formatierte E-Mail-Zusammenfassung an alle Abonnenten, um das Wochenende einzuläuten.

---

## 4. Admin-Sicherheit & Account-Management

- **Sicherheit:** Jellyfin-Administratoren können über das Plugin-Dashboard weder deaktiviert noch gelöscht werden (Hard-Restriction im Backend). Das verhindert fatale Fehlbedienungen.
- **Passwort-Reset:** Nutzer, die ihr Passwort vergessen haben, können entweder auf der Login-Seite auf "Passwort vergessen" klicken oder den Bot fragen (`/passwort`). In beiden Fällen wird ein sicherer Token generiert und via E-Mail/Telegram verschickt.
- **Templates:** Sämtliche Benachrichtigungen (Willkommen, Account gelöscht, Account deaktiviert, Passwort-Reset, Ankündigungen) sind in einer hochmodernen, einheitlichen HTML-Vorlage verpackt und können im Dashboard zu 100 % individuell angepasst werden. Das System ersetzt automatisch Platzhalter wie `{username}`, `{serverName}` oder `{platformLink}`.
