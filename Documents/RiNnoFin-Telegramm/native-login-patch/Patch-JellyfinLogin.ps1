<#
.SYNOPSIS
    RiNnoFin Telegramm - patcht die ECHTE Jellyfin-Login-Seite, damit
    "Passwort vergessen" zu unserem eigenen Reset-Flow (E-Mail/Telegram)
    führt statt zu Jellyfins eingebauter Funktion, die ohne Server-
    Dateizugriff sowieso nicht nutzbar ist.

.DESCRIPTION
    Jellyfin überschreibt bei JEDEM Server-Update den kompletten Web-Ordner
    (jellyfin-web) inklusive index.html. Dadurch geht dieser Patch beim
    nächsten Update wieder verloren.

    Deshalb: Nach jedem Jellyfin-Server-Update dieses Skript einfach erneut
    ausführen - es baut den Patch dann automatisch wieder ein.

    Das Skript ist sicher mehrfach ausführbar (idempotent) und legt beim
    allerersten Lauf ein Backup der Original-index.html an.

.PARAMETER JellyfinWebPath
    Pfad zum jellyfin-web-Ordner (der Ordner, der die index.html enthält).
    Wird automatisch erkannt, wenn nicht angegeben - falls das fehlschlägt,
    fragt das Skript danach.

.EXAMPLE
    .\Patch-JellyfinLogin.ps1

.EXAMPLE
    .\Patch-JellyfinLogin.ps1 -JellyfinWebPath "D:\Jellyfin\jellyfin-web"
#>

param(
    [string]$JellyfinWebPath
)

$ErrorActionPreference = "Stop"

function Find-JellyfinWebPath {
    $candidates = @(
        "C:\Program Files\Jellyfin\Server\jellyfin-web",
        "C:\Program Files (x86)\Jellyfin\Server\jellyfin-web",
        "$env:ProgramFiles\Jellyfin\Server\jellyfin-web",
        "$env:LOCALAPPDATA\Jellyfin\jellyfin-web"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "index.html")) {
            return $c
        }
    }
    return $null
}

Write-Host "=== RiNnoFin Telegramm - Native-Login-Patch ===" -ForegroundColor Cyan
Write-Host ""

if (-not $JellyfinWebPath) {
    Write-Host "Suche automatisch nach dem jellyfin-web Ordner..." -ForegroundColor Cyan
    $JellyfinWebPath = Find-JellyfinWebPath
}

if (-not $JellyfinWebPath -or -not (Test-Path (Join-Path $JellyfinWebPath "index.html"))) {
    Write-Host "Konnte den jellyfin-web-Ordner nicht automatisch finden." -ForegroundColor Yellow
    Write-Host "(Das ist der Ordner, der direkt die Datei 'index.html' von Jellyfin enthaelt," -ForegroundColor Yellow
    Write-Host " oft z.B. 'C:\Program Files\Jellyfin\Server\jellyfin-web')" -ForegroundColor Yellow
    $JellyfinWebPath = Read-Host "Bitte vollstaendigen Pfad zum jellyfin-web-Ordner eingeben"
}

$indexPath = Join-Path $JellyfinWebPath "index.html"

if (-not (Test-Path $indexPath)) {
    Write-Host "FEHLER: Keine index.html gefunden unter: $indexPath" -ForegroundColor Red
    Write-Host "Bitte pruefe den Pfad und starte das Skript erneut." -ForegroundColor Red
    exit 1
}

$jsSourcePath = Join-Path $PSScriptRoot "rinnofin-login-patch.js"
if (-not (Test-Path $jsSourcePath)) {
    Write-Host "FEHLER: 'rinnofin-login-patch.js' wurde nicht gefunden." -ForegroundColor Red
    Write-Host "Diese Datei muss im selben Ordner liegen wie dieses Skript." -ForegroundColor Red
    exit 1
}

$jsDestPath = Join-Path $JellyfinWebPath "rinnofin-login-patch.js"
$marker = "<!-- RiNnoFin-SSO-Patch -->"
$scriptTag = "    $marker`r`n    <script src=`"rinnofin-login-patch.js`"></script>`r`n"

$content = Get-Content -Path $indexPath -Raw -Encoding UTF8

if ($content -like "*$marker*") {
    Write-Host "index.html ist bereits gepatcht - aktualisiere nur die JS-Datei." -ForegroundColor Yellow
    Copy-Item -Path $jsSourcePath -Destination $jsDestPath -Force
    Write-Host ""
    Write-Host "Fertig. rinnofin-login-patch.js wurde aktualisiert." -ForegroundColor Green
    exit 0
}

# Backup nur beim allerersten Patch anlegen, damit spaetere Laeufe
# (nach Updates) nicht versehentlich eine bereits gepatchte Version sichern.
$backupPath = Join-Path $JellyfinWebPath "index.html.original-backup"
if (-not (Test-Path $backupPath)) {
    Copy-Item -Path $indexPath -Destination $backupPath
    Write-Host "Backup der Original-index.html angelegt: $backupPath" -ForegroundColor Cyan
}

Copy-Item -Path $jsSourcePath -Destination $jsDestPath -Force

if ($content -match "</body>") {
    $newContent = $content -replace "</body>", ($scriptTag + "</body>")
} else {
    Write-Host "FEHLER: Kein '</body>' in index.html gefunden - Patch wurde NICHT eingefuegt." -ForegroundColor Red
    Write-Host "Vermutlich hat sich das Format der Jellyfin-index.html grundlegend geaendert." -ForegroundColor Red
    exit 1
}

Set-Content -Path $indexPath -Value $newContent -Encoding UTF8 -NoNewline

Write-Host ""
Write-Host "Erfolgreich gepatcht!" -ForegroundColor Green
Write-Host " - rinnofin-login-patch.js kopiert nach: $jsDestPath"
Write-Host " - Script-Tag in index.html eingefuegt"
Write-Host ""
Write-Host "Bitte die Jellyfin-Login-Seite im Browser mit Strg+F5 (Hard-Reload) neu laden." -ForegroundColor Cyan
Write-Host ""
Write-Host "WICHTIG: Nach jedem Jellyfin-Server-Update wird der jellyfin-web-Ordner" -ForegroundColor Yellow
Write-Host "komplett ueberschrieben und der Patch geht verloren. Einfach dieses" -ForegroundColor Yellow
Write-Host "Skript danach erneut ausfuehren, dann ist er wieder da." -ForegroundColor Yellow
