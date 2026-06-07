# Release-Prozess für RiNnoFin Telegramm

Dieses Dokument beschreibt Schritt für Schritt, wie eine neue Version des Jellyfin-Plugins kompiliert, verpackt, im Manifest registriert und auf GitHub veröffentlicht wird, damit Jellyfin sie als Update erkennt.

---

## 📋 Ablauf einer neuen Veröffentlichung

### 1. Versionsnummer anheben
Öffne die Datei `RiNnoFinTelegramm/Jellyfin.Plugin.RiNnoFinTelegramm.csproj` und erhöhe die Versionsnummern im `<PropertyGroup>`-Block (z. B. auf `1.0.1.7`):
```xml
<AssemblyVersion>1.0.1.7</AssemblyVersion>
<FileVersion>1.0.1.7</FileVersion>
<Version>1.0.1.7</Version>
```

### 2. Plugin im Release-Modus bauen
Führe folgenden Befehl im Ordner `RiNnoFinTelegramm` aus:
```powershell
dotnet build -c Release
```
*Hinweis: Der Build-Prozess führt automatisch das ILRepack-Merging aus und kopiert die zusammengeführte DLL in den Unterordner `bin/Release/net9.0/publish/`.*

### 3. DLL in den Release-Ordner kopieren
Kopiere die neu gebaute DLL in den übergeordneten Ordner `publish_release`:
```powershell
Copy-Item -Path "RiNnoFinTelegramm\bin\Release\net9.0\publish\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -Destination "publish_release\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -Force
```

### 4. ZIP-Archiv erstellen
Erstelle ein frisches ZIP-Archiv, das **ausschließlich** die `Jellyfin.Plugin.RiNnoFinTelegramm.dll` enthält:
```powershell
Remove-Item -Path "publish_release\RiNnoFinTelegramm.zip" -ErrorAction SilentlyContinue
Compress-Archive -Path "publish_release\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -DestinationPath "publish_release\RiNnoFinTelegramm.zip" -Force
```

### 5. MD5-Prüfsumme der ZIP-Datei berechnen
Berechne den MD5-Hash der neuen ZIP-Datei. Jellyfin benötigt diesen Wert zur Verifizierung des Downloads:
```powershell
Get-FileHash -Path "publish_release\RiNnoFinTelegramm.zip" -Algorithm MD5
```
*Notiere dir den ausgegebenen MD5-Hash (z. B. `81B130DA4F16E0D76EE857BC214748CE`).*

### 6. `manifest.json` aktualisieren
Öffne `manifest.json` im Hauptverzeichnis des Repositories und füge das neue Release-Objekt ganz oben in das `versions`-Array ein:
```json
    "versions": [
      {
        "version": "1.0.1.7",
        "changelog": "Deine Beschreibung der neuen Features oder Fixes.",
        "targetAbi": "10.9.0.0",
        "sourceUrl": "https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/publish_release/RiNnoFinTelegramm.zip",
        "checksum": "DEIN_BERECHNETER_MD5_HASH",
        "timestamp": "2026-06-07 19:55:00"
      },
      ...
```

### 7. Änderungen committen und auf GitHub pushen
Führe folgende Befehle aus, um die aktualisierten Quelldateien, die Zip-Datei und das Manifest auf GitHub hochzuladen:
```powershell
git add .
git commit -m "Bump to 1.0.1.7: [Kurze Beschreibung des Updates]"
git push origin master
```

### 8. Update in Jellyfin abrufen
1. Warte **5 Minuten**, da GitHub Raw-Dateien cacht.
2. Navigiere in Jellyfin zu **Dashboard** -> **Geplante Aufgaben**.
3. Klicke auf das Start-Symbol bei **„Plugins aktualisieren“**.
4. Gehe in den **Plugin-Katalog** – die neue Version steht zum Update bereit!
