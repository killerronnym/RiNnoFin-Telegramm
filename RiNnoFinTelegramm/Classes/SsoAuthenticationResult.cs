using MediaBrowser.Controller.Authentication;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

public class SsoAuthenticationResult
{
    public bool Ok { get; set; }

    public string ServerAddress { get; set; } = default!;

    public string? ErrorMessage { get; set; }

    public AuthenticationResult? AuthenticatedUser { get; set; }
}
