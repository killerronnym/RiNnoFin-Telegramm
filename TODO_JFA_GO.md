# TODO: JFA-Go Integration

## Aktueller Stand (07. Juni 2026)
- **Plugin Version:** 1.0.2.3
- **Konfiguration:** Felder für JFA-Go URL, Benutzername und Passwort wurden in das Jellyfin-Dashboard (Weboberfläche) integriert.
- **Befehl:** Ein interaktiver Befehl `/NeuerBenutzer` (oder `/NeuBenutzer`) wurde hinzugefügt.
- **Ablauf:** 
  1. Admin ruft `/NeuerBenutzer` auf.
  2. Bot fragt nach Benutzername (via Telegram Reply).
  3. Bot fragt nach E-Mail-Adresse.
  4. Bot versucht, sich per API bei JFA-Go einzuloggen und eine Einladung zu verschicken.

## Offene Probleme / Nächste Schritte für morgen
1. **API-Endpunkt Überprüfung (Login):**
   - Zuletzt trat beim Login-Versuch der Fehler `Status NotFound` auf (beim Endpunkt `/users/login`). 
   - Wir haben den Endpunkt in v1.0.2.3 auf `GET /token/login` mit *Basic Authentication* umgestellt. Morgen muss getestet werden, ob diese Login-Methode beim User funktioniert.
2. **API-Endpunkt Überprüfung (Invite):**
   - Falls der Login klappt, muss geprüft werden, ob der Endpunkt `POST /invites` die JSON-Payload (`{"email":"...", "label":"...", "profile":"Standard User", "send_to":"..."}`) korrekt verarbeitet und die E-Mail an den Nutzer rausschickt.
3. **Fehlerbehandlung:**
   - Falls JFA-Go andere Endpunkte für diese Version nutzt, müssen wir per Entwicklertools/Swagger (API-Dokumentation) des Nutzers den exakten Request auslesen.
4. **Feinschliff:**
   - E-Mail-Validierung hinzufügen, bevor der API-Call an JFA-Go abgesetzt wird.
   - Bessere Fehlerausgabe für den Fall, dass die JFA-Go Zugangsdaten falsch sind.
