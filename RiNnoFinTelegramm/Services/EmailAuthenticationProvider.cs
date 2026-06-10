using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using MediaBrowser.Controller.Authentication;
using Jellyfin.Plugin.RiNnoFinTelegramm;
using System.Linq;
using System.Threading;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Services;

public class EmailAuthenticationProvider : IAuthenticationProvider
{
    private static readonly AsyncLocal<bool> _isAuthenticating = new AsyncLocal<bool>();
    private readonly IEnumerable<IAuthenticationProvider> _providers;

    public EmailAuthenticationProvider(IEnumerable<IAuthenticationProvider> providers)
    {
        _providers = providers;
    }

    public string Name => "RiNnoFin Email Login";

    public bool IsEnabled => true;

    public async Task<ProviderAuthenticationResult> Authenticate(string username, string password)
    {
        if (_isAuthenticating.Value)
            throw new Exception("Loop detected");

        if (!username.Contains("@"))
            throw new Exception("Not an email");

        var config = RiNnoFinPlugin.Instance?.Configuration;
        var link = config?.TelegramUserLinks?.FirstOrDefault(x => string.Equals(x.EmailAddress, username, StringComparison.OrdinalIgnoreCase));
        if (link == null || string.IsNullOrEmpty(link.JellyfinUsername))
            throw new Exception("Email not registered");

        try
        {
            _isAuthenticating.Value = true;
            foreach (var provider in _providers)
            {
                if (provider is EmailAuthenticationProvider) continue;
                try
                {
                    var result = await provider.Authenticate(link.JellyfinUsername, password).ConfigureAwait(false);
                    if (result != null && !string.IsNullOrEmpty(result.Username))
                    {
                        return result;
                    }
                }
                catch
                {
                    // Ignore and try next
                }
            }
            throw new Exception("Invalid password");
        }
        finally
        {
            _isAuthenticating.Value = false;
        }
    }

    public bool HasPassword(Jellyfin.Database.Implementations.Entities.User user) => true;

    public Task ChangePassword(Jellyfin.Database.Implementations.Entities.User user, string newPassword) => Task.CompletedTask;
}
