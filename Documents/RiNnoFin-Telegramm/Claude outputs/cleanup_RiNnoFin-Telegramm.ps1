# Aufräum-Skript für C:\Users\Ronny M PC\Documents\RiNnoFin-Telegramm
# Löscht nur Dateileichen, die durch das aktualisierte manifest.json / die
# aktualisierten Release-Docs nicht mehr gebraucht werden. Alles landet im
# Papierkorb (Remove-Item ohne -Force geht in Windows standardmäßig NICHT in
# den Papierkorb -- deshalb wird hier bewusst der Recycle-Bin-Weg genutzt).

$root = "C:\Users\Ronny M PC\Documents\RiNnoFin-Telegramm"

Add-Type -AssemblyName Microsoft.VisualBasic

function Remove-ToRecycleBin($path) {
    if (Test-Path $path) {
        $item = Get-Item $path
        if ($item.PSIsContainer) {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
                $path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        } else {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                $path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        }
        Write-Host "Gelöscht (Papierkorb): $path"
    } else {
        Write-Host "Übersprungen (existiert nicht): $path"
    }
}

# --- Scratch-Ordner / Build-Reste ---
Remove-ToRecycleBin "$root\test_extract"
Remove-ToRecycleBin "$root\v1.0.0.5_test"
Remove-ToRecycleBin "$root\RiNnoFinTelegramm\publish_release"   # doppelter publish_release-Ordner
Remove-ToRecycleBin "$root\RiNnoFinTelegramm\build.log"
Remove-ToRecycleBin "$root\RiNnoFinTelegramm\refactor.py"       # totes Skript, Pfade existieren nicht mehr
Remove-ToRecycleBin "$root\RiNnoFinTelegramm\refactor_js.py"    # totes Skript, Pfade existieren nicht mehr
Remove-ToRecycleBin "$root\publish_release\temp_zip_check"
Remove-ToRecycleBin "$root\publish_release\temp_zip_check_35"

# --- Alte, im (bereinigten) manifest.json nicht mehr referenzierte Release-ZIPs ---
$oldZips = @(
    "1.0.4.7", "1.0.4.8", "1.0.4.9",
    "1.0.4.10", "1.0.4.11", "1.0.4.12", "1.0.4.13", "1.0.4.14",
    "1.0.4.15", "1.0.4.16", "1.0.4.17", "1.0.4.18", "1.0.4.19",
    "1.0.4.20", "1.0.4.21", "1.0.4.23", "1.0.4.24",
    "1.0.4.27", "1.0.4.28", "1.0.4.35", "1.0.4.36"
)
foreach ($v in $oldZips) {
    Remove-ToRecycleBin "$root\publish_release\RiNnoFinTelegramm_$v.zip"
}

Write-Host ""
Write-Host "Fertig. Behalten wurden: RiNnoFinTelegramm.zip (aktuell, v1.0.4.55) sowie die"
Write-Host "versionierten ZIPs 1.0.4.37 bis 1.0.4.46 -- genau die Versionen, die noch im"
Write-Host "manifest.json stehen."
