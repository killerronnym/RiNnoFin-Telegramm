using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Xml.Serialization;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

[XmlRoot("PluginConfiguration")]
public class TelegramGroup
{
    [Required]
    [StringLength(32, MinimumLength = 3, ErrorMessage = "String muss zwischen 3 und 32 Zeichen lang sein")]
    [RegularExpression(@"^[a-zA-Z0-9_\-]+$",
        ErrorMessage = "Nur Buchstaben, Zahlen, Unterstriche und Bindestriche sind erlaubt")]
    public string GroupName { get; set; } = "BeispielGruppe";

    public bool EnableAllFolders { get; set; }

    public List<string> EnabledFolders { get; set; } = [];

    public List<string> UserNames { get; set; } = [];

    public TelegramGroupChat? TelegramGroupChat { get; set; }

    [XmlIgnore]
    public bool HasLinkedChat => TelegramGroupChat is { TelegramChatId: not 0 };
}
