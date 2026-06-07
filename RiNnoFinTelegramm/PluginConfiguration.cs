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

    public string? JfaGoUrl { get; set; }

    public string? JfaGoApiKey { get; set; }

    [XmlArray("TelegramGroups")]
    [XmlArrayItem(typeof(TelegramGroup), ElementName = "TelegramGroups")]
    public List<TelegramGroup> TelegramGroups { get; set; } = [];

    [XmlArray("TelegramUserLinks")]
    [XmlArrayItem(typeof(TelegramUserLink), ElementName = "TelegramUserLinks")]
    public List<TelegramUserLink> TelegramUserLinks { get; set; } = [];
}
