@echo off
setlocal enabledelayedexpansion

:: ================================================================
:: RiNnoFin Telegramm - Native-Login-Patch ueber die Synology (SSH)
:: ================================================================
:: Kopiert die Patch-Dateien per SCP auf die Synology und fuehrt sie
:: dort per SSH aus. Das Skript erkennt automatisch, ob Jellyfin als
:: natives Paket oder als Docker-Container laeuft.
::
:: Nach jedem Jellyfin-Update einfach dieses Skript per Doppelklick
:: erneut ausfuehren - der Patch wird dann automatisch wieder eingebaut.
::
:: EINMALIG unten ausfuellen:

set NAS_HOST=10.0.0.85
set NAS_USER=root
set NAS_PORT=22

:: ================================================================
:: Ab hier nichts mehr aendern.
:: ================================================================

if "%NAS_HOST%"=="DEINE-NAS-IP-ODER-HOSTNAME" (
    set /p NAS_HOST=Bitte NAS-IP oder Hostname eingeben (z.B. 192.168.1.50^):
)
if "%NAS_USER%"=="DEIN-SSH-BENUTZERNAME" (
    set /p NAS_USER=Bitte SSH-Benutzernamen eingeben:
)

set SCRIPT_DIR=%~dp0
set REMOTE_DIR=/tmp/rinnofin-patch

echo.
echo === RiNnoFin Telegramm - Verbinde mit %NAS_USER%@%NAS_HOST% ===
echo Du wirst gleich nach deinem SSH-Passwort gefragt (evtl. mehrmals).
echo.

where ssh >nul 2>nul
if errorlevel 1 (
    echo FEHLER: "ssh" wurde nicht gefunden.
    echo Windows 10/11 bringt SSH normalerweise mit ^(Einstellungen -^> Apps -^>
    echo Optionale Features -^> "OpenSSH-Client" installieren^). Danach diese
    echo Datei erneut ausfuehren.
    goto :error
)

ssh -p %NAS_PORT% %NAS_USER%@%NAS_HOST% "mkdir -p %REMOTE_DIR%"
if errorlevel 1 goto :error

scp -O -P %NAS_PORT% "%SCRIPT_DIR%rinnofin-login-patch.js" %NAS_USER%@%NAS_HOST%:%REMOTE_DIR%/
if errorlevel 1 goto :error

scp -O -P %NAS_PORT% "%SCRIPT_DIR%patch-jellyfin-nas.sh" %NAS_USER%@%NAS_HOST%:%REMOTE_DIR%/
if errorlevel 1 goto :error

ssh -p %NAS_PORT% %NAS_USER%@%NAS_HOST% "sh %REMOTE_DIR%/patch-jellyfin-nas.sh"
if errorlevel 1 goto :error

echo.
echo === Fertig! ===
echo Bitte lade die Jellyfin-Login-Seite im Browser mit Strg+F5 neu.
pause
exit /b 0

:error
echo.
echo === Es ist ein Fehler aufgetreten - bitte die Meldungen oben pruefen. ===
echo Haeufige Ursachen: falscher NAS-Host/Benutzername, falsches Passwort,
echo oder SSH ist auf der Synology doch nicht aktiviert.
pause
exit /b 1
