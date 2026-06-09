namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

public class TelegramUserLink
{
    public long TelegramUserId { get; set; }
    
    public string TelegramUsername { get; set; } = string.Empty;
    
    public string JellyfinUsername { get; set; } = string.Empty;
    
    public bool SubscribedToNewsletter { get; set; } = true;
    
    public System.Guid JellyfinUserId { get; set; }
    
    public string EmailAddress { get; set; } = string.Empty;
}
