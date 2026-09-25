# To-Do Liste - Telegramm Bot Projekt

---

## KRITISCH - Sofort erledigen

### invite_bot.py wiederherstellen
> Die Datei wurde durch einen Fehler beim Bearbeiten komplett geloescht und der pyc-Cache ebenfalls ueberschrieben.
> Der Bot startet aktuell NICHT vollstaendig.

Was fehlt: invite_bot.py (war ~3019 Zeilen, ~158 KB)

Optionen zur Wiederherstellung:
- [ ] Pruefen ob auf GitHub/Remote vorhanden -> `git remote -v`
- [ ] Pruefen ob auf anderem PC oder USB-Stick eine Kopie existiert
- [ ] Komplett neu schreiben (zeitaufwaendig, aber moeglich)

Bekannte Funktionen aus Bytecode-Analyse:
  fix_chat_id, is_user_blocked, detect_social_platform
  start, letsgo, datenschutz, notify_admin_ban_attempt
  handle_answer, next_question, handle_rules_confirmation
  post_profile, generate_profile_text, save_birthday_from_answers
  handle_whitelist_callback, handle_existing_member_callback
  handle_chat_member_router, handle_new_member, handle_member_left
  bearbeiten, show_edit_menu, handle_edit_callback, finalize_profile
  catch_all_pre, catch_all_post
  check_repost_triggers, check_auto_resume_pauses, check_fake_check_timeouts
  get_handlers, get_fallback_handlers, setup_jobs

---

## OFFEN - Personalisierte Einlade-Links

### Feature: Referral-/Einlade-Links (z.B. Nils-Link)

Ziel: Admins/User koennen Links erstellen wie:
  https://t.me/DeinBot?start=Nils

Wenn ein neuer User auf den Link klickt, wird im Steckbrief gespeichert:
  "Dieser Link wurde von Nils dem User gegeben."

Was bereits implementiert war (vor der Datei-Loeschung):
  [x] start()-Funktion liest context.args aus und speichert referred_by in InviteApplication.answers
  [x] generate_profile_text() zeigt "Dieser Link wurde von X gegeben." im Steckbrief

Was noch fehlt:
  [ ] Dashboard-Seite zum Erstellen/Verwalten von personalisierten Links
  [ ] Link-Generator im Web-Dashboard (z.B. unter Einstellungen)
  [ ] Statistik welcher Link wie oft genutzt wurde
  [ ] Anzeige im Steckbrief des Users wer ihn eingeladen hat

Relevante Dateien:
  bots/invite_bot/invite_bot.py      (muss zuerst wiederhergestellt werden!)
  web_dashboard/app/routes/dashboard.py
  web_dashboard/app/templates/bot_settings.html
  web_dashboard/app/models.py       (InviteApplication -> answers_json -> referred_by)

---

## OFFEN - Weitere Features

### Fake-Check und Blockieren rueckgaengig machen
  [ ] Wenn man in der Gruppe auf "Fake" drueckt -> Rueckgaengig-Button
  [ ] Wenn man "Blockieren" drueckt -> Entblocken-Moeglichkeit
  [ ] Bilder im Fake-Check erkennen (wird derzeit nicht erkannt)

### Steckbrief-Erinnerungen (Reminder)
  [ ] Timer einstellbar: nach X Stunden/Tagen eine Erinnerung senden
  [ ] Anzahl der Erinnerungen einstellbar
  [ ] Anzeige im Admin-Dashboard wenn User Steckbrief nicht ausgefuellt hat
  [ ] Notification in der Administratorgruppe

---

## ERLEDIGT (Referenz)

  [x] Grid-Layout in bot_settings.html repariert (2-Spalten-Layout)
  [x] Encoding-Fehler (Mojibake) in HTML-Templates behoben
  [x] Backend-Logik fuer Steckbrief-Erinnerungen in dashboard.py integriert
  [x] Steckbrief-Erinnerungen Tab in der Web-UI (Kachel-Design)

---
Zuletzt aktualisiert: 26.09.2026
