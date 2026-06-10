# ✅ RiNnoFin Telegramm – To-Do Liste

> Zuletzt aktualisiert: 10.06.2026  
> Legende: ✅ Fertig | 🔄 In Arbeit | 🔲 Noch zu tun | 💡 Idee / Zukunft

---

## ✅ Bereits erledigt

- ✅ Benutzer einladen per E-Mail (Admin-Panel + Telegram `/NeuerBenutzer`)
- ✅ Registrierungsseite mit Passwort-Stärkenanzeige
- ✅ Passwort-Reset per E-Mail (Benutzername + E-Mail müssen übereinstimmen) 
- ✅ Willkommens-E-Mail nach Registrierung (persönlich mit Benutzername)
- ✅ Bestätigungs-E-Mail nach Passwortänderung
- ✅ Account deaktivieren / aktivieren mit E-Mail-Benachrichtigung + Grund
- ✅ Account löschen mit E-Mail-Benachrichtigung + Grund
- ✅ Telegram-Bot: `/start`, `/ping`, `/help`, `/passwort`, `/status`, `/link`, `/unlink`, `/userlist`, `/quiz`, `/abonnieren`, `/deabonnieren`, `/newsletter`
- ✅ Telegram-Konto verknüpfen via Browser (SSO)
- ✅ Telegram-Konto verknüpfen direkt im Chat (`/verbinden` → E-Mail → Passwort)
- ✅ ToS-Checkbox (Nutzungsbedingungen) auf Registrierungsseite (Pflichtfeld)
- ✅ Newsletter-Checkbox auf Registrierungsseite (optional, wird in DB gespeichert)
- ✅ „Jetzt mit Telegram verbinden"-Button auf Erfolgsseite nach Registrierung
- ✅ Benutzer bearbeiten: E-Mail und Telegram-Username ändern (Admin-Panel)
- ✅ Admin-Panel: „Aktivieren"- und „Deaktivieren"-Buttons getrennt
- ✅ Plugin Erklärungsdokument (PLUGIN_ERKLAERUNG.md)

---

## 🔲 Priorität 1 – Nächste Schritte (Kern-Features)

### 🖥️ Weboberfläche / Registrierungsseite
- ✅ **Logo / Bild austauschbar machen** – Im Admin-Panel ein eigenes Logo hochladen, das dann auf allen Seiten (invite, reset, login) erscheint statt dem Standard-Bild
- ✅ **E-Mail-Betreff pro Vorlage anpassen** – Für jede E-Mail-Art (Einladung, Willkommen, Passwort-Reset, Passwort geändert, Deaktiviert, Aktiviert, Gelöscht) einen eigenen, editierbaren Betreff im Admin-Panel hinterlegen können

### 👤 Benutzerverwaltung (Admin-Panel)
- ✅ **Ablaufdatum für Accounts** – Admin kann pro User ein Ablaufdatum setzen
  - User bekommt X Tage vorher eine automatische E-Mail: *„Dein Account läuft in X Tagen ab – bitte wende dich an einen Administrator"*
  - Account wird nach Ablauf automatisch deaktiviert
  - Benachrichtigung auch per Telegram an den User (falls verknüpft)
- ✅ **Ankündigungsnachrichten an einzelne oder mehrere User**
  - Admin klickt auf einen oder mehrere User → Button „Ankündigung senden"
  - Felder: Betreff, HTML-Nachricht (mit `{username}`, `{email}` etc. als Platzhalter)
  - Versand per **E-Mail (HTML)** + **Telegram-Nachricht** gleichzeitig
  - Funktioniert für einzelne User oder als Mehrfachauswahl (Checkbox pro User)
- ✅ **Gruppen-Ankündigung** – Nachricht direkt in die verknüpfte Telegram-Gruppe posten (mit optionalem Inhalt aus dem Admin-Panel)

### 🤖 Telegram-Bot überprüfen & verbessern
- ✅ **Vollständiger Bot-Test** – Alle Befehle auf Funktion prüfen:
  - `/start` – Willkommen, Status, Buttons (Browser / Chat verknüpfen)
  - `/verbinden` – E-Mail → Passwort → Verknüpfung
  - `/passwort` – Passwort ändern
  - `/newsletter`, `/abonnieren`, `/deabonnieren`
  - Admin-Befehle wirklich nur für Admins zugänglich?
- ✅ **Newsletter automatisch in Gruppe posten** – Wenn ein neuer Film oder eine neue Serie in Jellyfin erscheint, wird automatisch eine Nachricht in die verknüpfte Telegram-Gruppe gepostet (für Newsletter-Abonnenten)
- ✅ **Bot-Nachrichten überarbeiten** – Alle Bot-Texte überprüfen, schöner und professioneller formulieren

---

## 🔲 Priorität 2 – Erweiterungen

### 📊 Automatische Berichte & Statistiken
- ✅ **Monatliche Server-Charts** – Bot postet am Monatsende automatisch: *„Top 3 der beliebtesten Filme/Serien diesen Monat"* in die Telegram-Gruppe
- ✅ **Persönlicher Wochenrückblick** – Jeden Freitag bekommt jeder User eine Telegram-Nachricht oder HTML-E-Mail: *„Das hast du diese Woche verpasst: 3 neue Folgen von Serie X ..."*

### 🎬 Film-/Serien-Wunschsystem
- ✅ **`/wunsch [Filmname]`** – User kann einen Film- oder Serienwunsch einschicken
  - Bot sucht automatisch über TMDB-API (zeigt Bild + Titel)
  - Admin bekommt Push-Nachricht mit Buttons: `✅ Genehmigen` / `❌ Ablehnen`
  - User bekommt Benachrichtigung wenn Wunsch genehmigt oder abgelehnt wurde

### 🔒 Sicherheit & Gast-Zugänge
- ✅ **Temporäre Gast-Accounts** – Einladungen mit automatischem Ablaufdatum (z. B. „Zugang nur für 7 Tage")
- ✅ **2FA via Telegram** – Bei Login von einem neuen Gerät schickt der Bot eine Autorisierungs-Anfrage. Ohne Autorisierung wird die Wiedergabe blockiert.

### 🖥️ Server-Überwachung / Alarme
- ✅ **Uptime-Alarm** – Bot schickt Admin eine Warnung wenn Jellyfin-Server abstürzt oder nicht mehr erreichbar ist (als genereller Server-Alarm implementiert)
- ✅ **Festplatten-Alarm** – Warnung wenn Festplatte zu mehr als 95% voll ist
- ✅ **Transcoding-Warnung** – Hinweis wenn zu viele User gleichzeitig transkodieren (CPU-Überlastung)

---

## 💡 Ideen für später (kein fixes Datum)


- 💡 **Custom Telegram-Sticker-Set** – Kleine RiNnoFin-Sticker für den Bot (z. B. „Server läuft", „Filmwunsch eingegangen")
- 💡 **Plugin-Seite im Jellyfin-Design** – Komplettes visuelles Redesign der Admin-Konfigurations-Seite

---

## 📋 Reihenfolge Empfehlung

```
1. Logo austauschbar machen
2. E-Mail-Betreff anpassbar
3. Ablaufdatum für Accounts + Benachrichtigung
4. Ankündigungsnachrichten (einzeln + Gruppe)
5. Bot vollständig testen + Texte überarbeiten
6. Newsletter automatisch in Gruppe posten
7. Monatliche Charts + Wochenrückblick
8. Wunschsystem (/wunsch)
9. 2FA via Telegram
10. Server-Alarme
```
