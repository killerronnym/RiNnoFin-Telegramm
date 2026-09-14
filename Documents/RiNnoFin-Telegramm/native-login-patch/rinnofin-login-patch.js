/*
 * RiNnoFin Telegramm - Native-Login-Patch
 * ----------------------------------------
 * Ersetzt den "Passwort vergessen"-Button auf der ECHTEN Jellyfin-Login-Seite
 * durch einen Link zu unserem eigenen, funktionierenden Passwort-Reset
 * (E-Mail + Telegram statt Server-Dateizugriff).
 *
 * Wird von Patch-JellyfinLogin.ps1 automatisch in die index.html eingebunden.
 * Nicht manuell loeschen - nach jedem Jellyfin-Update muss diese Datei durch
 * erneutes Ausfuehren des PowerShell-Skripts wiederhergestellt werden.
 */
(function () {
    "use strict";

    var TARGET_URL = "/sso/Telegram/forgot";
    var SELECTOR = ".btnForgotPassword";

    function patchButton(btn) {
        if (!btn || btn.getAttribute("data-rinnofin-patched") === "1") {
            return;
        }

        // cloneNode(true) übernimmt Klassen/Text/Icons 1:1, aber KEINE per
        // addEventListener registrierten Klick-Handler von Jellyfin selbst.
        // So verhindern wir zuverlässig, dass der native "Passwort
        // vergessen"-Dialog (der ohne Server-Zugriff eh nicht nutzbar ist)
        // noch aufgeht.
        var clone = btn.cloneNode(true);
        clone.setAttribute("data-rinnofin-patched", "1");
        clone.addEventListener("click", function (e) {
            e.preventDefault();
            window.location.href = TARGET_URL;
        });

        if (btn.parentNode) {
            btn.parentNode.replaceChild(clone, btn);
        }
    }

    function scan(root) {
        if (!root || typeof root.querySelectorAll !== "function") {
            return;
        }
        var buttons = root.querySelectorAll(SELECTOR);
        for (var i = 0; i < buttons.length; i++) {
            patchButton(buttons[i]);
        }
    }

    // Login-Seite ist beim Start evtl. schon da (z.B. nach Hard-Reload)
    scan(document);

    // Jellyfin-web ist eine Single-Page-App - die Login-Seite wird per JS
    // nachgeladen, ohne dass index.html neu geladen wird. Deshalb beobachten
    // wir dauerhaft auf neu eingefügte Elemente.
    var observer = new MutationObserver(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
            var addedNodes = mutations[i].addedNodes;
            for (var j = 0; j < addedNodes.length; j++) {
                var node = addedNodes[j];
                if (node.nodeType !== 1) {
                    continue;
                }
                if (node.matches && node.matches(SELECTOR)) {
                    patchButton(node);
                }
                scan(node);
            }
        }
    });

    var startObserving = function () {
        observer.observe(document.documentElement || document.body, {
            childList: true,
            subtree: true
        });
    };

    if (document.body) {
        startObserving();
    } else {
        document.addEventListener("DOMContentLoaded", startObserving);
    }
})();
