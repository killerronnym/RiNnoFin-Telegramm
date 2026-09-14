namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

public record TelegramAuthResult
{
    public bool Ok { get; set; }

    public string? ErrorMessage { get; set; }
}
