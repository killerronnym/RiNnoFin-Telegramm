namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

public class TelegramUserLink
{
    public long TelegramUserId { get; set; }
    
    public string TelegramUsername { get; set; } = string.Empty;
    
    public string JellyfinUsername { get; set; } = string.Empty;
    
    public bool SubscribeEmailNewsletter { get; set; } = true;
    
    public bool SubscribeTelegramNewsletter { get; set; } = true;
    
    public System.Guid JellyfinUserId { get; set; }
    
    public string EmailAddress { get; set; } = string.Empty;
    
    public System.DateTime? ExpirationDate { get; set; }
    
    public bool ExpirationNotified { get; set; } = false;
    
    public System.Collections.Generic.List<string> AuthorizedDevices { get; set; } = new();
}
