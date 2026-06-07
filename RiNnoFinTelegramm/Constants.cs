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
        "Willkommen bei RiNnoFin Telegramm! Diese Gruppe ist noch nicht verknüpft.\n\n" +
        "Ein Administrator kann dies mit dem Befehl /link tun.";

    internal const string PrivateAdminWelcomeMessage =
        "Willkommen bei RiNnoFin Telegramm! Ich kann dir und deinen Freunden helfen, euch mit eurem Jellyfin-Server über Telegram zu authentifizieren.\n\n" +
        "Verfügbare Befehle:\n" +
        "/ping - Prüft die Verbindung zum Bot und zeigt deinen Status\n" +
        "/passwort <neues_passwort> - Ändert dein persönliches Passwort\n" +
        "/newsletter - Interaktives Menü für Medien-Benachrichtigungen\n" +
        "/abonnieren - Abonniert den Newsletter für neue Filme, Serien & Musik\n" +
        "/deabonnieren - Deaktiviert den Newsletter\n" +
        "/link - Verknüpft diese Gruppe mit einer Jellyfin-Gruppe (nur für Admins)\n" +
        "/status - Zeigt Server-Ressourcen (nur für Admins)";

    internal const string PrivateUserWelcomeMessage =
        "Willkommen bei RiNnoFin Telegramm!\n\n" +
        "Verfügbare Befehle:\n" +
        "/ping - Prüft die Verbindung zum Bot und zeigt deinen Status\n" +
        "/passwort <neues_passwort> - Ändert dein persönliches Passwort\n" +
        "/newsletter - Interaktives Menü für Medien-Benachrichtigungen\n" +
        "/abonnieren - Abonniert den Newsletter für neue Filme, Serien & Musik\n" +
        "/deabonnieren - Deaktiviert den Newsletter";

    internal const string LinkPrefix = "l:";

    public static readonly ExtraPageInfo[] LoginFiles =
    [
        new() { Name = "index", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.login.html", NeedsReplacement = true },
        new() { Name = "login.css", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.login.css", NeedsReplacement = true },
        new() { Name = "login.js", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.login.js", NeedsReplacement = true },
        new() { Name = "material_icons.woff2", EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.material_icons.woff2" },
        new() { Name = DefaultUserImageExtraFile, EmbeddedResourcePath = "Jellyfin.Plugin.RiNnoFinTelegramm.Assets.Login.RiNnoFinLogo.png" }
    ];

    // Unique GUID for RiNnoFin Telegramm so it does not conflict with TeleJelly
    public static Guid Id => Guid.Parse("9e1d84f2-901d-44a6-ba92-7fcf1a5598ba");

    public static string PluginName => "RiNnoFin Telegramm";

    public static string PluginDataFolder => "data";

    public static string UserImageFolder => "userimages";

    public static string DefaultUserImageExtraFile => "rinnofinlogo.png";

    public static string DefaultBotToken => "12345678:xxxxxxxxxxxxxxx";
}
