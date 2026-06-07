using System;
using Microsoft.AspNetCore.Http;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

internal static class ControllerExtensions
{
    public static string GetRequestBase(this HttpRequest request, PluginConfiguration configuration)
    {
        if (request == null)
        {
            throw new ArgumentNullException(nameof(request), "Request ist null.");
        }

        var configSchema = configuration.ForcedUrlScheme;
        var requestPort = request.Host.Port ?? -1;
        var requestScheme =
            string.Equals(configSchema, "http", StringComparison.OrdinalIgnoreCase)
            || string.Equals(configSchema, "https", StringComparison.OrdinalIgnoreCase)
                ? configSchema
                : request.Scheme;

        if ((requestPort == 80 && string.Equals(requestScheme, "http", StringComparison.OrdinalIgnoreCase))
            || (requestPort == 443 && string.Equals(requestScheme, "https", StringComparison.OrdinalIgnoreCase)))
        {
            requestPort = -1;
        }

        return new UriBuilder { Scheme = requestScheme, Host = request.Host.Host, Port = requestPort, Path = request.PathBase }.ToString().TrimEnd('/');
    }
}
