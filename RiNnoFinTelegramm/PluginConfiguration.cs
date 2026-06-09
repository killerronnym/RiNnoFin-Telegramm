using System.Collections.Generic;
using System.Xml.Serialization;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.RiNnoFinTelegramm;

public class PluginConfiguration : BasePluginConfiguration
{
    public string? LoginBaseUrl { get; set; }

    public string BotToken { get; set; } = Constants.DefaultBotToken;

    public string BotUsername { get; set; } = "INVALID_BOT_TOKEN";

    public bool EnableBotService { get; set; } = true;

    public List<string> AdminUserNames { get; set; } = [];

    public int MaxSessionCount { get; set; } = -1;

    public string ForcedUrlScheme { get; set; } = "none";



    // Neue SMTP & E-Mail Einstellungen
    public bool EnableEmail { get; set; } = false;
    public string SmtpServer { get; set; } = "smtp.strato.de";
    public int SmtpPort { get; set; } = 587;
    public string SmtpUsername { get; set; } = "RinnoFin@brainless-rp.de";
    public string SmtpPassword { get; set; } = string.Empty;
    public string EmailSenderAddress { get; set; } = "RinnoFin@brainless-rp.de";
    public string EmailSenderName { get; set; } = "Rinno Einladungssystem";
    public bool SmtpUseSsl { get; set; } = true;

    [XmlArray("TelegramGroups")]
    [XmlArrayItem(typeof(TelegramGroup), ElementName = "TelegramGroups")]
    public List<TelegramGroup> TelegramGroups { get; set; } = [];

    [XmlArray("TelegramUserLinks")]
    [XmlArrayItem(typeof(TelegramUserLink), ElementName = "TelegramUserLinks")]
    public List<TelegramUserLink> TelegramUserLinks { get; set; } = [];
}
