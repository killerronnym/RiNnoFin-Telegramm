# 📖 RiNnoFin Telegramm – Was ist das und was kann es?

> **Für wen ist dieses Dokument?**  
> Dieses Dokument erklärt verständlich, wofür das Plugin ist, wie es funktioniert und was es alles kann – auch für Personen, die noch nie etwas mit dem Thema zu tun hatten.

---

## 🎯 Was ist RiNnoFin Telegramm?

**RiNnoFin Telegramm** ist ein selbst entwickeltes Plugin für **Jellyfin** – einem kostenlosen, selbst gehosteten Media-Server (ähnlich wie Netflix, nur für zu Hause).  

Das Plugin verbindet **Jellyfin** mit **Telegram** und ermöglicht es:
- Benutzer einfach einzuladen und zu verwalten
- Passwörter sicher per E-Mail zurückzusetzen
- Den Telegram-Bot als persönliche Schaltzentrale zu nutzen
- Benachrichtigungen über neue Filme und Serien zu versenden (Newsletter)

---

## 🔗 Mit was ist das Plugin verbunden?

Das Plugin verbindet **3 Systeme** miteinander:

| System | Was ist es? | Wozu wird es verwendet? |
|---|---|---|
| **Jellyfin** | Der Media-Server (läuft auf deinem eigenen Server/NAS) | Speichert alle Benutzer, Filme, Serien |
| **Telegram** | Der bekannte Messenger | Verwaltung, Benachrichtigungen, Account-Verknüpfung |
| **E-Mail (SMTP)** | Dein E-Mail-Server (z. B. Strato) | Einladungen, Passwort-Reset, Willkommensnachrichten |

---

## 👥 Wer benutzt das Plugin?

Es gibt **zwei Benutzergruppen**:

### 🛡️ Administrator (du / der Serverbetreiber)
- Verwaltet alle Nutzer über eine Weboberfläche in Jellyfin
- Kann Einladungen versenden, Accounts sperren/freischalten, löschen
- Hat Zugriff auf Server-Statistiken im Telegram-Bot
- Kann E-Mail-Vorlagen individuell anpassen

### 👤 Normaler Benutzer (deine Freunde / Familie / Mitglieder)
- Bekommt eine Einladung per E-Mail
- Erstellt sich selbst einen Account über einen sicheren Link
- Kann sein Passwort selbst zurücksetzen
- Kann sich mit Telegram verbinden für Benachrichtigungen

---

## 🚀 So funktioniert der Ablauf – Schritt für Schritt

### 📨 Schritt 1: Benutzer einladen

**Der Admin** schickt eine Einladung über:
- Die **Jellyfin-Admin-Oberfläche** (Plugin-Seite → "Benutzer hinzufügen")  
  **ODER**
- Den **Telegram-Bot** mit dem Befehl `/NeuerBenutzer`

Das System erstellt automatisch einen **einmaligen, sicheren Einladungslink** und schickt ihn per **E-Mail** an die angegebene Adresse.

---

### 📝 Schritt 2: Benutzer registriert sich

Der eingeladene Benutzer öffnet den Link in seinem Browser und sieht eine **Registrierungsseite** mit:
- **Benutzername** wählen
- **E-Mail** bestätigen (wird bereits vorausgefüllt aus der Einladung)
- **Passwort** festlegen (mit Sicherheitsanzeige: Schwach / Mittel / Gut / Sehr sicher)
- **Passwort wiederholen**
- ✅ Pflicht-Checkbox: **Nutzungsbedingungen akzeptieren**
- ☑️ Optional: **Newsletter abonnieren** (Benachrichtigungen über neue Inhalte)

Nach der Registrierung:
- Wird automatisch eine **Willkommens-E-Mail** versendet (mit Benutzername bestätigt)
- Erscheint ein **Button: "Jetzt mit Telegram verbinden"** für die direkte Bot-Verknüpfung

---

### 🔑 Schritt 3: Telegram-Konto verbinden

Ein Benutzer kann seinen Jellyfin-Account mit Telegram verknüpfen – auf **zwei Arten**:

**Weg A – Im Browser (SSO):**  
Klick auf "Im Browser verknüpfen" → Weiterleitung zur Telegram-Login-Seite

**Weg B – Im Chat mit dem Bot:**  
1. Benutzer schreibt `/verbinden` an den Bot
2. Bot fragt nach der **E-Mail-Adresse**
3. Bot fragt nach dem **Jellyfin-Passwort** (wird sofort aus Sicherheitsgründen gelöscht)
4. Bei Erfolg: Verknüpfung gespeichert ✅

---

### 🔒 Schritt 4: Passwort vergessen?

Der Benutzer geht auf die Passwort-vergessen-Seite und gibt ein:
- Seinen **Benutzernamen**
- Seine **E-Mail-Adresse**

Das System prüft ob beides übereinstimmt und schickt einen **Reset-Link per E-Mail**.  
Über den Link kann der Benutzer dann:
- Neues Passwort eingeben (mit Stärkenanzeige)
- Passwort bestätigen

Nach dem Reset bekommt der Benutzer eine **Bestätigungs-E-Mail** (Passwort wurde geändert).

---

## 🤖 Was kann der Telegram-Bot?

Der Bot reagiert auf **Befehle** (sogenannte "Commands") im Chat. Hier ist alles was der Bot kann:

### Befehle für alle Benutzer

| Befehl | Was macht er? |
|---|---|
| `/start` | Begrüßungsnachricht + Status der Verknüpfung + Buttons zum Verbinden |
| `/help` | Zeigt alle verfügbaren Befehle mit Erklärung |
| `/ping` | Prüft ob der Bot online ist + zeigt deinen Status (Benutzer / Admin) |
| `/verbinden` | Startet die Konto-Verknüpfung direkt im Chat (E-Mail + Passwort) |
| `/passwort` | Ändert dein Jellyfin-Passwort direkt über den Bot |
| `/newsletter` | Zeigt interaktives Menü für Newsletter-Einstellungen |
| `/abonnieren` | Abonniert den Newsletter (Benachrichtigungen über neue Inhalte) |
| `/deabonnieren` | Deaktiviert den Newsletter |

### Befehle nur für Administratoren

| Befehl | Was macht er? |
|---|---|
| `/status` | Zeigt Server-Statistiken: Jellyfin-Version, Laufzeit, RAM-Verbrauch, Festplattenauslastung |
| `/link` | Verknüpft eine Telegram-Gruppe mit dem Jellyfin-Server |
| `/unlink` | Entknüpft eine Telegram-Gruppe |
| `/userlist` | Zeigt alle verknüpften Benutzer (Whitelist) |
| `/NeuerBenutzer` | Sendet eine Einladung per E-Mail an eine neue Person |
| `/quiz` | Startet eine Quizfrage über Filme/Serien in der Gruppe |

---

## 📬 Welche E-Mails werden automatisch versendet?

Das Plugin versendet **automatisch** E-Mails in folgenden Situationen:

| Ereignis | E-Mail-Inhalt | Empfänger |
|---|---|---|
| **Einladung** | Einladungslink zum Erstellen des Accounts | Eingeladene Person |
| **Registrierung erfolgreich** | Willkommen + Benutzername + Login-Infos | Neuer Benutzer |
| **Passwort-Reset angefordert** | Reset-Link (gültig nur einmalig) | Benutzer |
| **Passwort geändert** | Bestätigung der Passwortänderung | Benutzer |
| **Account deaktiviert** | Benachrichtigung + optionaler Grund vom Admin | Benutzer |
| **Account reaktiviert** | Freischaltungsbenachrichtigung | Benutzer |
| **Account gelöscht** | Abschiedsbenachrichtigung + Grund | (Ehemaliger) Benutzer |

Alle E-Mail-Vorlagen sind **vollständig anpassbar** über die Jellyfin Plugin-Einstellungen.  
Der Benutzer wird immer **persönlich mit seinem Namen** angesprochen (z.B. "Hallo Tim, ...").

---

## 🛠️ Was kann der Administrator über die Weboberfläche tun?

In der **Jellyfin Plugin-Konfigurationsseite** (Tab: "Benutzerverwaltung") kann der Admin:

- 📋 **Alle Benutzer** mit Status, E-Mail und Telegram-Verknüpfung sehen
- ➕ **Neue Benutzer einladen** (Einladungslink per E-Mail)
- ✏️ **Benutzer bearbeiten** (E-Mail und Telegram-Username ändern)
- 🔴 **Benutzer deaktivieren** (mit Begründung → E-Mail wird versendet)
- 🟢 **Benutzer aktivieren** (Reaktivierungsmail wird versendet)
- 🔑 **Passwort-Reset** auslösen (sendet Reset-Link per E-Mail)
- 🗑️ **Benutzer löschen** (mit Begründung → Abschiedsmail wird versendet)

---

## ⚙️ Was kann der Administrator in den Einstellungen konfigurieren?

| Einstellung | Erklärung |
|---|---|
| **Bot-Token** | Der geheime Schlüssel für den Telegram-Bot (von @BotFather) |
| **Server-URL** | Die URL des Jellyfin-Servers (für Links in E-Mails) |
| **Admin-Telegram-Nutzer** | Welche Telegram-Nutzer Admin-Befehle ausführen dürfen |
| **SMTP-Server** | E-Mail-Versand-Einstellungen (Server, Port, Benutzername, Passwort) |
| **E-Mail-Vorlagen** | Alle Nachrichten vollständig individuell gestaltbar (HTML) |
| **Standard-Profil** | Neuen Benutzern werden automatisch die Rechte eines bestehenden Profil-Users übertragen |
| **Telegram-Gruppen** | Welche Telegram-Gruppen mit dem Server verknüpft sind |

---

## 🔒 Sicherheit – Was schützt das Plugin?

- 🔑 **Einmalige Tokens**: Einladungslinks und Reset-Links funktionieren nur ein einziges Mal
- 🔐 **Passwort-Hashing**: Passwörter werden niemals im Klartext gespeichert (Jellyfin PBKDF2)
- 🗑️ **Auto-Löschung**: Passwörter die im Telegram-Chat eingegeben werden, werden sofort nach dem Lesen gelöscht
- ✅ **E-Mail-Bestätigung**: Beim Passwort-Reset müssen Benutzername UND E-Mail übereinstimmen
- 🛡️ **Admin-Schutz**: Kritische Bot-Befehle sind nur für eingetragene Administratoren zugänglich
- 🔏 **Passwort-Stärke**: Neue Passwörter müssen mindestens 8 Zeichen haben und ein Sonderzeichen enthalten
- 📜 **Nutzungsbedingungen**: Jeder neue Benutzer muss die ToS akzeptieren (Pflicht-Checkbox)

---

## 🗺️ Systemübersicht (vereinfacht)

```
[Admin] ──────────────────────────────────┐
   │                                      │
   │ Einladung per E-Mail schicken         │ Bot-Befehle (/NeuerBenutzer, /status, ...)
   ▼                                      ▼
[SMTP E-Mail Server]              [Telegram-Bot]
   │                                      │
   │ E-Mail mit Einladungslink             │ Benachrichtigungen, Verwaltung
   ▼                                      ▼
[Neuer Benutzer]  ──── Registrierung ──► [Jellyfin Media-Server]
                         über Browser          │
                                               │ Filme, Serien, Musik
                                               ▼
                                       [Benutzer streamt Inhalte]
                                               │
                                               │ Newsletter (zukünftig)
                                               ▼
                                       [Telegram-Benachrichtigung]
```

---

## 📦 Technische Details (für Entwickler)

- **Sprache**: C# (.NET 9)
- **Zielplattform**: Jellyfin Media-Server Plugin-System
- **Telegram-Library**: Telegram.Bot v22.7.5
- **E-Mail**: SMTP über System.Net.Mail
- **Aktuelle Version**: 1.0.4.25
- **Repository**: https://github.com/killerronnym/RiNnoFin-Telegramm
- **Plugin-GUID**: `9e1d84f2-901d-44a6-ba92-7fcf1a5598ba`

---

## 📋 Zusammenfassung in einem Satz

> **RiNnoFin Telegramm** ist ein All-in-One-Verwaltungs-Plugin für private Jellyfin-Server, das Benutzereinladungen, E-Mail-Benachrichtigungen und einen Telegram-Bot zu einem einheitlichen System verbindet – damit du deinen eigenen "kleinen Netflix" professionell und einfach für Familie und Freunde betreiben kannst.
