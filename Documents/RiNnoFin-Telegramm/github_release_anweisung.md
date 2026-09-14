# Anweisung für die KI: GitHub Release Prozess für RiNnoFin Telegramm

> **Hinweis für den Benutzer:**
> Wenn du möchtest, dass ich eine neue Version auf GitHub hochlade, ziehe einfach diese Datei in den Chat oder schreibe mir: *"Bitte lade das Plugin auf GitHub hoch, basierend auf der Datei `github_release_anweisung.md`!"*
>
> Diese Datei ist eine kompakte, KI-taugliche Zusammenfassung von `RELEASING.md`. Falls beide Dokumente sich widersprechen sollten, gilt `RELEASING.md` als Quelle der Wahrheit.

---

## 🤖 KI-Arbeitsablauf (Vollautomatischer Release)

Das Repository liegt unter `C:\Users\Ronny M PC\Documents\RiNnoFin-Telegramm`. **Alle Befehle unten laufen in diesem Root-Verzeichnis**, außer wo explizit ein `cd` angegeben ist – nach `cd RiNnoFinTelegramm` immer mit `cd ..` wieder zurück ins Root wechseln, bevor mit `publish_release` weitergemacht wird.

Wenn der Benutzer dich auffordert, einen Release nach dieser Anleitung zu erstellen, **MUSST** du die folgenden Schritte **strikt nacheinander und vollautomatisch** ausführen (nutze dafür deine Terminal/Command-Tools und File-Editierungs-Tools):

### Schritt 1: Versionsnummer ermitteln und anheben
1. Lies die aktuelle Version aus `RiNnoFinTelegramm/Jellyfin.Plugin.RiNnoFinTelegramm.csproj` aus (Feld `<Version>`).
2. Erhöhe die Patch-Versionsnummer (die letzte Ziffer) um 1 (z. B. von `1.0.4.55` auf `1.0.4.56`).
3. Aktualisiere in der `.csproj`-Datei **alle drei** Felder `<AssemblyVersion>`, `<FileVersion>` und `<Version>` auf die neue Versionsnummer – sie müssen immer identisch sein.

### Schritt 2: Plugin kompilieren (Release-Build)
```powershell
cd RiNnoFinTelegramm
dotnet build -c Release
cd ..
```
*Prüfe mit deinem Status-Tool zwingend, ob der Build fehlerfrei (`Exit code: 0`) durchgelaufen ist, bevor du weitermachst!*

### Schritt 3: Versioniertes ZIP-Archiv erstellen
Führe **im Root-Ordner** aus (nicht in `RiNnoFinTelegramm`!):
```powershell
Compress-Archive -Path "RiNnoFinTelegramm\bin\Release\net9.0\publish\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -DestinationPath "publish_release\RiNnoFinTelegramm_NEUE_VERSION.zip" -Force
```
Ersetze `NEUE_VERSION` durch die neue Versionsnummer aus Schritt 1 (z. B. `RiNnoFinTelegramm_1.0.4.56.zip`).

**Wichtig:** Verwende immer einen neuen, versionierten Dateinamen – niemals eine bestehende ZIP-Datei überschreiben. Sonst zeigen ältere `manifest.json`-Einträge irgendwann auf eine Datei, deren Inhalt nicht mehr zu ihrer gespeicherten Prüfsumme passt, und diese Versionen lassen sich dann nicht mehr installieren.

### Schritt 4: MD5-Checksum generieren
```powershell
(Get-FileHash -Path "publish_release\RiNnoFinTelegramm_NEUE_VERSION.zip" -Algorithm MD5).Hash
```
Speichere den zurückgegebenen MD5-Hash (kleingeschrieben) für den nächsten Schritt.

### Schritt 5: `manifest.json` aktualisieren
1. Öffne `manifest.json` im Root-Verzeichnis.
2. Füge einen **komplett neuen Eintrag** als allererstes Element oben in das `"versions"`-Array ein, mit `sourceUrl`, der auf die in Schritt 3 erzeugte **versionierte** ZIP zeigt:
```json
      {
        "version": "NEUE_VERSION",
        "changelog": "Erstelle selbständig eine kurze, treffende Zusammenfassung der Änderungen basierend auf unseren Chat-Verläufen.",
        "targetAbi": "10.9.0.0",
        "sourceUrl": "https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/publish_release/RiNnoFinTelegramm_NEUE_VERSION.zip",
        "checksum": "DEIN_BERECHNETER_MD5_HASH",
        "timestamp": "AKTUELLES_DATUM_UND_UHRZEIT_ALS_UTC (z.B. 2026-06-09 19:30:00)"
      },
```
*(Wichtig: Vergiss nicht das Komma nach der geschweiften Klammer, damit die JSON-Struktur erhalten bleibt.)*

### Schritt 6: Auf GitHub pushen
```powershell
git add .
git commit -m "Release v[NEUE_VERSION]: [Kurzes Stichwort zum Update]"
git push
```

### Schritt 7: Abschlussbericht
Melde dich beim Benutzer im Chat mit einer kurzen Bestätigung:
- Nenne die neu hochgeladene Versionsnummer.
- Liste die Neuerungen (den Changelog) kurz auf.
- Bestätige, dass der `git push` erfolgreich war und das Jellyfin-Dashboard das Update nun erkennt.
