using System;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

public class MediaRequest
{
    public Guid ItemId { get; set; }

    public string ImdbId { get; set; } = string.Empty;

    public string Title { get; set; } = string.Empty;

    public int? Year { get; set; }

    public string UserId { get; set; } = "unknown";

    public string UserDisplayName { get; set; } = "Unknown";

    public DateTime RequestedAtUtc { get; set; } = DateTime.UtcNow;
}
