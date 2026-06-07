# RiNnoFin Telegramm

**RiNnoFin Telegramm** ist ein leistungsstarkes, auf Deutsch lokalisiertes Integrations-Plugin für den **Jellyfin Media Server**. Es ermöglicht eine nahtlose Interaktion zwischen Jellyfin und Telegram, einschließlich Authentifizierung per Telegram SSO, interaktivem Passwort-Management im Chat, automatisierten Medien-Newslettern (für Filme, Serien und Musik) sowie einer umfassenden Rechteverwaltung für Gruppenchats.

---

## Hauptfeatures

*   **Telegram SSO (Single Sign-On)**: Benutzer können sich direkt via Telegram-Widget auf einer eigens gestalteten, glasmorphischen Jellyfin-Login-Seite authentifizieren.
*   **Eigenständige Passwortänderung**: Benutzer können ihr persönliches Jellyfin-Passwort direkt über den Telegram-Bot mittels `/passwort` ändern (nur im sicheren privaten Chat möglich).
*   **Multimedialer Newsletter**: Automatische Benachrichtigungen bei neu hinzugefügten Inhalten (Filme, Serien, Alben/Musik) inklusive Cover-Bildern und Direktlinks zum Jellyfin-Server.
*   **Gruppen-Ordnerberechtigungen**: Zuweisung von Jellyfin-Ordnerberechtigungen basierend auf der Telegram-Gruppenzugehörigkeit (Verknüpfung via `/link`).
*   **Media Requests**: Direktes Senden von Medienanfragen im Chat mit automatischem Abgleich und Löschung, sobald der Inhalt in Jellyfin eingepflegt wurde.

---

## Installation & Einrichtung

Es gibt zwei einfache Wege, das Plugin auf deinem Jellyfin-Server zu installieren:

### Methode A: Manuelle Installation (Direkter Upload)

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

### Methode B: Installation via Repository (Automatische Updates)

Du kannst dieses GitHub-Repository direkt als Update-Quelle in deinem Jellyfin-Server registrieren:

1. Kopiere den Link zur RAW-Ansicht der Manifest-Datei dieses Repositories:
   `https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/manifest.json`
2. Navigiere in deinem Jellyfin-Dashboard zu **Dashboard -> Plugins -> Repositories**.
3. Klicke auf das **"+"**-Symbol und trage folgende Werte ein:
   *   **Name:** `RiNnoFin Repository`
   *   **URL:** *(Füge den oben kopierten Link ein)*
4. Klicke auf **Speichern**.
5. Klicke nun oben auf den Reiter **Katalog** (Catalog). Dort siehst du das Plugin **RiNnoFin Telegramm** und kannst es mit einem einzigen Klick installieren und künftig updaten.

---

## Bot-Befehle

Der Bot unterscheidet automatisch zwischen privaten Chats und verknüpften Gruppenchats:

### Im privaten Chat (Benutzer-Optionen)
*   `/start` — Zeigt eine Begrüßung und die Liste aller verfügbaren Befehle.
*   `/passwort <neues_passwort>` — Ändert dein Jellyfin-Passwort (mind. 4 Zeichen).
*   `/abonnieren` — Aktiviert den Newsletter für Filme, Serien und Musik.
*   `/deabonnieren` — Deaktiviert den Newsletter.
*   `/newsletter` — Öffnet ein interaktives Menü für detaillierte Einstellungen.

### In verknüpften Gruppen (Nur für Administratoren)
*   `/link` — Verknüpft den Gruppenchat mit einer Jellyfin-Rechtegruppe.
*   `/unlink` — Hebt die Verknüpfung der Gruppe auf.
*   `/status` — Zeigt Systeminformationen und Ressourcen des Jellyfin-Servers.
*   `/userlist` — Listet verknüpfte Benutzer auf.
