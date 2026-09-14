#!/bin/sh
# RiNnoFin Telegramm - Native-Login-Patch fuer Jellyfin auf der Synology
# ------------------------------------------------------------------------
# Wird NICHT direkt gestartet, sondern von Patch-JellyfinLogin.bat (Windows)
# per SSH auf der Synology ausgefuehrt. Findet automatisch heraus, ob
# Jellyfin als natives Paket oder als Docker-Container laeuft, und baut
# den Passwort-vergessen-Patch entsprechend ein.

MARKER="RiNnoFin-SSO-Patch"
WORKDIR="$(cd "$(dirname "$0")" && pwd)"
JS_FILE="$WORKDIR/rinnofin-login-patch.js"
TMP_INDEX="/tmp/rinnofin_index.html"
TMP_INDEX_PATCHED="/tmp/rinnofin_index.patched.html"

echo "=== RiNnoFin Telegramm - Native-Login-Patch (Synology) ==="

if [ ! -f "$JS_FILE" ]; then
    echo "FEHLER: rinnofin-login-patch.js liegt nicht neben diesem Skript ($WORKDIR)."
    exit 1
fi

# Fuegt den Script-Tag per awk vor </body> ein (nur beim ersten Treffer) -
# portabler als sed, weil auch BusyBox-awk auf der Synology das kann.
patch_html() {
    src="$1"
    dst="$2"
    awk -v marker="$MARKER" '
        BEGIN { done = 0 }
        /<\/body>/ && done == 0 {
            print "<!-- " marker " -->"
            print "<script src=\"rinnofin-login-patch.js\"></script>"
            done = 1
        }
        { print }
    ' "$src" > "$dst"
}

WEBDIR=""

# --- 1. Natives Synology-Paket (Paket-Zentrum / SynoCommunity) ---
for candidate in \
    /var/packages/JellyfinServer/target/jellyfin-web \
    /var/packages/jellyfin-server/target/jellyfin-web \
    /var/packages/Jellyfin/target/jellyfin-web \
    /var/packages/jellyfin/target/web
do
    if [ -f "$candidate/index.html" ]; then
        WEBDIR="$candidate"
        break
    fi
done

if [ -n "$WEBDIR" ]; then
    echo "Natives Jellyfin-Paket gefunden: $WEBDIR"

    if grep -q "$MARKER" "$WEBDIR/index.html" 2>/dev/null; then
        echo "index.html ist bereits gepatcht - aktualisiere nur die JS-Datei."
        cp "$JS_FILE" "$WEBDIR/rinnofin-login-patch.js"
        echo "Fertig."
        exit 0
    fi

    if [ ! -f "$WEBDIR/index.html.original-backup" ]; then
        cp "$WEBDIR/index.html" "$WEBDIR/index.html.original-backup"
        echo "Backup angelegt: $WEBDIR/index.html.original-backup"
    fi

    patch_html "$WEBDIR/index.html" "$WEBDIR/index.html.tmp" \
        && mv "$WEBDIR/index.html.tmp" "$WEBDIR/index.html"
    cp "$JS_FILE" "$WEBDIR/rinnofin-login-patch.js"

    echo "Fertig! Native Login-Seite wurde gepatcht (natives Paket)."
    echo "Browser mit Strg+F5 neu laden."
    exit 0
fi

# --- 2. Docker-Container ---
if ! command -v docker >/dev/null 2>&1; then
    echo "FEHLER: Weder ein natives Jellyfin-Paket gefunden, noch ist 'docker' verfuegbar."
    echo "Bitte melde dich - dann passen wir das Skript an dein Setup an."
    exit 1
fi

CONTAINER="$(docker ps --format '{{.Names}}' | grep -i jellyfin | head -n1)"

if [ -z "$CONTAINER" ]; then
    echo "FEHLER: Kein laufender Docker-Container mit 'jellyfin' im Namen gefunden."
    echo "Bitte im Container Manager nachschauen, wie der Container genau heisst,"
    echo "und kurz melden - dann passen wir das Skript an."
    exit 1
fi

echo "Docker-Container gefunden: $CONTAINER"

CONTAINER_WEBDIR="$(docker exec "$CONTAINER" sh -c 'find / -maxdepth 6 -type d -iname jellyfin-web 2>/dev/null | head -n1')"

if [ -z "$CONTAINER_WEBDIR" ]; then
    echo "FEHLER: Konnte den jellyfin-web-Ordner im Container '$CONTAINER' nicht finden."
    echo "Bitte melde dich - dann suchen wir gezielt nach dem richtigen Pfad."
    exit 1
fi

echo "jellyfin-web im Container gefunden: $CONTAINER_WEBDIR"

docker cp "$CONTAINER:$CONTAINER_WEBDIR/index.html" "$TMP_INDEX" 2>/dev/null
if [ ! -f "$TMP_INDEX" ]; then
    echo "FEHLER: Konnte index.html nicht aus dem Container kopieren."
    exit 1
fi

if grep -q "$MARKER" "$TMP_INDEX"; then
    echo "index.html ist im Container bereits gepatcht - aktualisiere nur die JS-Datei."
    docker cp "$JS_FILE" "$CONTAINER:$CONTAINER_WEBDIR/rinnofin-login-patch.js"
    rm -f "$TMP_INDEX"
    echo "Fertig."
    exit 0
fi

if ! docker exec "$CONTAINER" sh -c "test -f '$CONTAINER_WEBDIR/index.html.original-backup'" 2>/dev/null; then
    docker cp "$TMP_INDEX" "$CONTAINER:$CONTAINER_WEBDIR/index.html.original-backup"
    echo "Backup im Container angelegt (index.html.original-backup)."
fi

patch_html "$TMP_INDEX" "$TMP_INDEX_PATCHED"
docker cp "$TMP_INDEX_PATCHED" "$CONTAINER:$CONTAINER_WEBDIR/index.html"
docker cp "$JS_FILE" "$CONTAINER:$CONTAINER_WEBDIR/rinnofin-login-patch.js"
rm -f "$TMP_INDEX" "$TMP_INDEX_PATCHED"

echo "Fertig! Native Login-Seite wurde im Docker-Container gepatcht."
echo "Browser mit Strg+F5 neu laden, um die Aenderung zu sehen."
