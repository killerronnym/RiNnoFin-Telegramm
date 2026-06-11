# 📋 RiNnoFin Telegramm – To-Do Liste

> Stand: v1.0.4.32 – zuletzt aktualisiert: 11.06.2026

---

## 🔴 KRITISCH
(Alle kritischen Bugs wurden behoben! 🎉)

## 🟠 WICHTIG – E-Mail Templates
(Alle E-Mail-bezogenen Anforderungen wurden umgesetzt! ✉️)

## 🟡 UI / DASHBOARD
- 🔲 **Ankündigungs-Panel:** Vorschau der E-Mail im Browser anzeigen, bevor gesendet wird
- 🔲 **Template-Auswahl:** Dropdown für verschiedene Vorlagen (Ankündigung, Willkommen, Neuheiten, etc.)

## 🔵 QUALITÄT / LOGGING
- 🔲 **Fehlerlogs verbessern:** Ausführlichere Protokollierung im Jellyfin-Log, inkl. Zeitstempel, Methodenname und Ursache
- 🔲 **Logging-Tab im Dashboard:** Mehr Details anzeigen (Typ, Quelle, Nachricht)

---

## ✅ ERLEDIGT
<details open>
<summary>Klicken um kürzlich erledigte Aufgaben anzuzeigen</summary>

- ✅ **Telegram-Status:** Das Dashboard zeigt nun korrekt an, ob ein User mit Telegram verknüpft ist, selbst wenn der Telegram-Benutzername noch nicht bekannt ist.
- ✅ **Benutzerliste:** E-Mail-Adressen werden in der User-Tabelle nun korrekt aus den UserLinks geladen und angezeigt.

- ✅ **Registrierung:** Bestätigungs-E-Mail enthält nun den Benutzernamen und eine Anleitung zum Einloggen.
- ✅ **Newsletter-E-Mail:** Richtiger Bibliotheks-Ordner (z.B. „Netflix Serien") wird nun korrekt ermittelt, nicht mehr "root".
- ✅ **Newsletter-E-Mail:** Titelbilder / Cover-Bilder der Medien werden in den HTML E-Mails eingebunden.
- ✅ **Ankündigung:** Variablen `{serverName}`, `{username}`, `{platformLink}` und `{message}` werden beim Senden nun korrekt aufgelöst.
- ✅ **Admin-Schutz:** Jellyfin-Administratoren dürfen NICHT gelöscht oder deaktiviert werden (Backend & Frontend abgesichert)
- ✅ **resetpassword-Fehler:** "Ressource nicht gefunden: 'resetpassword'" Route im PublicController behoben
- ✅ **Telegram-Verknüpfung:** SSO-Login repariert – Verknüpfung über jellyfinuserid für eingeloggte User im Browser hinzugefügt
- ✅ **E-Mail Templates:** Premium-HTML-Template als Standard für Ankündigungen und Newsletter hinterlegt
- ✅ **E-Mail Dashboard:** Alle E-Mail Templates im Plugin-Dashboard editierbar gemacht (Willkommen, Einladung, Account gelöscht, Neue Filme, Neue Serien etc.)
- ✅ **Benutzer namentlich ansprechen:** `{username}` Platzhalter in allen Templates sichergestellt
- ✅ Multi-Kanal Ankündigung (E-Mail + Telegram Checkboxen)
- ✅ Bot-Administrator Rechte-Schalter im Benutzer-Bearbeiten-Dialog
- ✅ HTTP 403 Fehler in der Benutzerliste (GetUsers) behoben (v1.0.4.32)
- ✅ Browser-Cache-Problem mit JS-Versionen gelöst
- ✅ UTC-Timestamp-Problem im Manifest behoben (v1.0.4.30)

*(Ältere erledigte Features befinden sich in der internen Projekthistorie)*
</details>
