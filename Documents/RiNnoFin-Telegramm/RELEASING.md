# Release-Prozess für RiNnoFin Telegramm

Dieses Dokument beschreibt Schritt für Schritt, wie eine neue Version des Jellyfin-Plugins kompiliert, verpackt, im Manifest registriert und auf GitHub veröffentlicht wird, damit Jellyfin sie als Update erkennt.

> **Wichtig:** Alle Befehle unten werden im **Root-Verzeichnis des Repositories** ausgeführt (dort, wo auch `manifest.json` und `publish_release/` liegen), außer wenn explizit ein `cd` angegeben ist. Nach einem `cd RiNnoFinTelegramm` unbedingt wieder mit `cd ..` zurück ins Root wechseln, bevor die `publish_release`-Befehle laufen – sonst landet die ZIP versehentlich in `RiNnoFinTelegramm\publish_release` statt im Root-`publish_release`.
>
> **Wichtig 2:** Jede Version bekommt ihre **eigene, versionierte ZIP-Datei** (`RiNnoFinTelegramm_<VERSION>.zip`). Niemals denselben Dateinamen für mehrere Releases wiederverwenden – sonst zeigt der `sourceUrl` mehrerer `manifest.json`-Einträge irgendwann auf dieselbe (inzwischen überschriebene) Datei und die Prüfsumme älterer Versionen stimmt nicht mehr, wodurch sich diese nicht mehr installieren lassen.

---

## 📋 Ablauf einer neuen Veröffentlichung

### 1. Versionsnummer anheben
Öffne `RiNnoFinTelegramm/Jellyfin.Plugin.RiNnoFinTelegramm.csproj` und erhöhe **alle drei** Versionsfelder im `<PropertyGroup>`-Block auf denselben Wert (z. B. auf `1.0.4.56`):
```xml
<AssemblyVersion>1.0.4.56</AssemblyVersion>
<FileVersion>1.0.4.56</FileVersion>
<Version>1.0.4.56</Version>
```

### 2. Plugin im Release-Modus bauen
Führe im Ordner `RiNnoFinTelegramm` aus:
```powershell
cd RiNnoFinTelegramm
dotnet build -c Release
cd ..
```
*Hinweis: Der Build-Prozess führt automatisch das ILRepack-Merging aus und kopiert die zusammengeführte DLL nach `RiNnoFinTelegramm\bin\Release\net9.0\publish\`.*

### 3. ZIP-Archiv erstellen (im Root-Verzeichnis!)
Erstelle ein frisches, **versioniertes** ZIP-Archiv, das ausschließlich die `Jellyfin.Plugin.RiNnoFinTelegramm.dll` enthält:
```powershell
Compress-Archive -Path "RiNnoFinTelegramm\bin\Release\net9.0\publish\Jellyfin.Plugin.RiNnoFinTelegramm.dll" -DestinationPath "publish_release\RiNnoFinTelegramm_1.0.4.56.zip" -Force
```

### 4. MD5-Prüfsumme der ZIP-Datei berechnen
```powershell
Get-FileHash -Path "publish_release\RiNnoFinTelegramm_1.0.4.56.zip" -Algorithm MD5
```
*Notiere dir den ausgegebenen MD5-Hash (klein geschrieben, z. B. `81b130da4f16e0d76ee857bc214748ce`).*

### 5. `manifest.json` aktualisieren
Öffne `manifest.json` im Hauptverzeichnis und füge das neue Release-Objekt ganz oben in das `versions`-Array ein:
```json
    "versions": [
      {
        "version": "1.0.4.56",
        "changelog": "Deine Beschreibung der neuen Features oder Fixes.",
        "targetAbi": "10.9.0.0",
        "sourceUrl": "https://raw.githubusercontent.com/killerronnym/RiNnoFin-Telegramm/master/publish_release/RiNnoFinTelegramm_1.0.4.56.zip",
        "checksum": "DEIN_BERECHNETER_MD5_HASH",
        "timestamp": "2026-06-07 19:55:00"
      },
      ...
```
Der `sourceUrl` verweist auf die **versionierte** ZIP aus Schritt 3 – nicht auf einen wiederverwendeten Dateinamen.

Optional: Ist die `versions`-Liste sehr lang geworden, dürfen alte Einträge entfernt werden – dann aber auch die zugehörige, nicht mehr referenzierte ZIP aus `publish_release/` löschen, damit keine Datei-Leichen liegen bleiben.

### 6. Änderungen committen und auf GitHub pushen
```powershell
git add .
git commit -m "Release v1.0.4.56: [Kurze Beschreibung des Updates]"
git push origin master
```

### 7. Update in Jellyfin abrufen
1. Warte **5 Minuten**, da GitHub Raw-Dateien cacht.
2. Navigiere in Jellyfin zu **Dashboard** -> **Geplante Aufgaben**.
3. Klicke auf das Start-Symbol bei **„Plugins aktualisieren“**.
4. Gehe in den **Plugin-Katalog** – die neue Version steht zum Update bereit!
