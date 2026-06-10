using System;
using System.Linq;

namespace Jellyfin.Plugin.RiNnoFinTelegramm;

public class ExtraPageInfo
{
    public string Name { get; set; } = string.Empty;
    public string EmbeddedResourcePath { get; set; } = string.Empty;
    public bool NeedsReplacement { get; set; }
}

public static class Constants
{
    internal const string GroupWelcomeMessage =
        "Willkommen bei *RiNnoFin Media*! 🍿\n\n" +
        "Diese Telegram-Gruppe ist aktuell noch nicht mit unserem System verknüpft.\n" +
        "Ein Administrator kann die Verknüpfung jederzeit mit dem Befehl `/link` herstellen.";

    internal const string PrivateAdminWelcomeMessage =
        "Willkommen bei *RiNnoFin Media*! 🎬🍿\n\n" +
        "Ich bin dein persönlicher Assistent und helfe dir dabei, deinen Jellyfin-Server direkt über Telegram zu verwalten.\n\n" +
        "🛠️ *Admin-Befehle:*\n" +
        "🔹 `/ping` - Verbindungsstatus und Profil prüfen\n" +
        "🔹 `/passwort <neu>` - Persönliches Passwort ändern\n" +
        "🔹 `/newsletter` - Interaktives Newsletter-Menü öffnen\n" +
        "🔹 `/abonnieren` - Benachrichtigungen für neue Medien aktivieren\n" +
        "🔹 `/deabonnieren` - Benachrichtigungen deaktivieren\n" +
        "🔹 `/link` - Gruppe mit Jellyfin verknüpfen (nur Admin)\n" +
        "🔹 `/status` - Aktuelle Server-Ressourcen anzeigen (nur Admin)\n" +
        "🔹 `/userlist` - Liste aller registrierten Benutzer anzeigen (nur Admin)\n" +
        "🔹 `/quiz` - Ein Trivia-Quiz starten";

    internal const string PrivateUserWelcomeMessage =
        "Willkommen bei *RiNnoFin Media*! 🎬🍿\n\n" +
        "Ich bin dein persönlicher Assistent für dein perfektes Streaming-Erlebnis.\n\n" +
        "📱 *Verfügbare Befehle:*\n" +
        "🔹 `/ping` - Verbindungsstatus und Profil prüfen\n" +
        "🔹 `/passwort <neu>` - Dein persönliches Passwort ändern\n" +
        "🔹 `/newsletter` - Interaktives Newsletter-Menü öffnen\n" +
        "🔹 `/abonnieren` - Benachrichtigungen für neue Filme & Serien aktivieren\n" +
        "🔹 `/deabonnieren` - Benachrichtigungen deaktivieren\n" +
        "🔹 `/quiz` - Ein kleines Film/Serien-Trivia spielen";

    internal const string LinkPrefix = "l:";

    public static readonly ExtraPageInfo[] LoginFiles =
    [
        new() { Name = "index", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.login.html", NeedsReplacement = true },
        new() { Name = "login.css", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.login.css", NeedsReplacement = true },
        new() { Name = "login.js", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.login.js", NeedsReplacement = true },
        new() { Name = "material_icons.woff2", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.material_icons.woff2" },
        new() { Name = DefaultUserImageExtraFile, EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.RiNnoFinLogo.png" },
        new() { Name = "invite", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Invite.invite.html", NeedsReplacement = true },
        new() { Name = "forgot", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Recovery.forgot.html", NeedsReplacement = true },
        new() { Name = "reset", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Recovery.reset.html", NeedsReplacement = true }
    ];

    // Unique GUID for RiNnoFin Telegramm so it does not conflict with TeleJelly
    public static Guid Id => Guid.Parse("9e1d84f2-901d-44a6-ba92-7fcf1a5598ba");

    public static string PluginName => "RiNnoFin Telegramm";

    public static string PluginDataFolder => "data";

    public static string UserImageFolder => "userimages";

    public static string DefaultUserImageExtraFile => "rinnofinlogo.png";

    public static string DefaultBotToken => "12345678:xxxxxxxxxxxxxxx";
}
