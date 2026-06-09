Ja, das sieht schon mal so cool aus# Anweisung für die KI: GitHub Release Prozess für RiNnoFin Telegramm

> **Hinweis für den Benutzer:** 
> Wenn du möchtest, dass ich eine neue Version auf GitHub hochlade, ziehe einfach diese Datei in den Chat oder schreibe mir: *"Bitte lade das Plugin auf GitHub hoch, basierend auf der Datei `github_release_anweisung.md`!"*

---

## 🤖 KI-Arbeitsablauf (Vollautomatischer Release)

Wenn der Benutzer dich auffordert, einen Release nach dieser Anleitung zu erstellen, **MUSST** du die folgenden Schritte **strikt nacheinander und vollautomatisch** ausführen (nutze dafür deine Terminal/Command-Tools und File-Editierungs-Tools):

### Schritt 1: Versionsnummer ermitteln und anheben
1. Lies die aktuelle Version aus der Datei `RiNnoFinTelegramm/Jellyfin.Plugin.RiNnoFinTelegramm.csproj` aus (z. B. `<Version>1.0.3.1</Version>`).
2. Erhöhe die Patch-Versionsnummer (die letzte Ziffer) um 1 (z.B. von `1.0.3.1` auf `1.0.3.2`).
3. Nutze dein Tool zur Dateibearbeitung, um in der `.csproj`-Datei die XML-Felder `<AssemblyVersion>`, `<FileVersion>` und `<Version>` auf die **neue Versionsnummer** zu aktualisieren.

### Schritt 2: Plugin kompilieren (Release-Build)
Führe den folgenden PowerShell-Befehl aus:
```powershell
cd "RiNnoFinTelegramm"
dotnet build -c Release
cd ..
```
*Prüfe mit deinem Status-Tool zwingend, ob der Build fehlerfrei (`Exit code: 0`) durchgelaufen ist, bevor du weitermachst!*

### Schritt 3: ZIP-Archiv für das Release erstellen
Die zusammengeführte `.dll` muss einzeln in eine ZIP-Datei gepackt werden. Führe im Root-Ordner (`c:\Users\Ronny M PC\Documents\Jellyfin Telegramm\RiNnoFin Telegramm`) folgende PowerShell-Befehle aus:
```powershell
Remove-Item -Path "publish_release\RiNnoFinTelegramm.zip" -ErrorAction SilentlyContinue
Copy-Item -Path "RiNnoFinTelegramm\bin\Release\net9.0\publish\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -Destination "publish_release\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -Force
Compress-Archive -Path "publish_release\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -DestinationPath "publish_release\RiNnoFinTelegramm.zip" -Force
```

### Schritt 4: MD5 Checksum generieren
Lass dir den MD5-Hash des gerade erstellten ZIP-Archivs berechnen:
```powershell
(Get-FileHash -Path "publish_release\RiNnoFinTelegramm.zip" -Algorithm MD5).Hash
```
*Speichere dir den zurückgegebenen MD5-Hash-String im Gedächtnis.*

### Schritt 5: Manifest.json aktualisieren
1. Öffne die Datei `manifest.json` im Root-Verzeichnis.
2. Füge einen **komplett neuen Eintrag** als allererstes Element oben in das `"versions"`-Array ein.
3. Der neue Eintrag muss exakt so formatiert sein:
```json
      {
        "version": "NEUE_VERSION",
        "changelog": "Erstelle selbständig eine kurze, treffende Zusammenfassung der Änderungen basierend auf unseren Chat-Verläufen.",
        "targetAbi": "10.9.0.0",
        "sourceUrl": "https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/publish_release/RiNnoFinTelegramm.zip",
        "checksum": "DEIN_BERECHNETER_MD5_HASH",
        "timestamp": "AKTUELLES_DATUM_UND_UHRZEIT_ALS_UTC (z.B. 2026-06-09 19:30:00)"
      },
```
*(Wichtig: Vergiss nicht das Komma nach der geschweiften Klammer, damit die JSON-Struktur erhalten bleibt).*

### Schritt 6: Auf GitHub pushen
Führe zum Schluss folgende Git-Befehle aus, um alle Änderungen live zu schalten:
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
