namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

public class ValidateBotTokenResponse
{
    public bool Ok { get; set; }

    public string? ErrorMessage { get; set; }

    public string? BotUsername { get; set; }
    
    public bool AdminMessageSent { get; set; }
}
