using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;
using MediaBrowser.Controller;
using MediaBrowser.Controller.Plugins;
using Microsoft.Extensions.DependencyInjection;

namespace Jellyfin.Plugin.RiNnoFinTelegramm;

public class RiNnoFinServiceRegistrator : IPluginServiceRegistrator
{
    public void RegisterServices(IServiceCollection serviceCollection, IServerApplicationHost applicationHost)
    {
        serviceCollection.AddSingleton<ICommandProvider, DefaultCommandProvider>();
        serviceCollection.AddSingleton<TelegramBotClientWrapper>();
        serviceCollection.AddSingleton<RequestService>();
        serviceCollection.AddSingleton<NotificationService>();

        serviceCollection.AddHostedService<TelegramBackgroundService>();
    }
}
