using Telegram.Bot;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Services;

public class TelegramBotClientWrapper
{
    public ITelegramBotClient? Client { get; set; }
}
