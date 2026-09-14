using System;
using System.Collections.Generic;
using System.Linq;
using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;

namespace Jellyfin.Plugin.RiNnoFinTelegramm;

public class RiNnoFinPlugin : BasePlugin<PluginConfiguration>, IPlugin, IHasWebPages
{
    public static object? UserManager { get; private set; }
    public static MediaBrowser.Model.Cryptography.ICryptoProvider? CryptoProvider { get; private set; }
    public static ILibraryManager? LibraryManager { get; private set; }
    public static IServiceProvider? ServiceProvider { get; private set; }
    public static RiNnoFinPlugin? Instance { get; private set; }

    public RiNnoFinPlugin(
        IApplicationPaths applicationPaths,
        IXmlSerializer xmlSerializer,
        IServiceProvider serviceProvider)
        : base(applicationPaths, xmlSerializer)
    {
        ApplicationPaths = applicationPaths;
        Instance = this;
        ServiceProvider = serviceProvider;

        try
        {
            var umType = System.AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return Array.Empty<Type>(); } })
                .FirstOrDefault(t => t.Name == "IUserManager" || t.FullName == "MediaBrowser.Controller.Library.IUserManager");
            if (umType != null)
            {
                UserManager = serviceProvider.GetService(umType);
            }

            CryptoProvider = serviceProvider.GetService(typeof(MediaBrowser.Model.Cryptography.ICryptoProvider)) as MediaBrowser.Model.Cryptography.ICryptoProvider;
            LibraryManager = serviceProvider.GetService(typeof(ILibraryManager)) as ILibraryManager;
        }
        catch { }
    }

    private Jellyfin.Plugin.RiNnoFinTelegramm.Services.TelegramBotClientWrapper? _botWrapper;
    public Jellyfin.Plugin.RiNnoFinTelegramm.Services.TelegramBotClientWrapper? GetBotClientWrapper() => _botWrapper;
    public void SetBotClientWrapper(Jellyfin.Plugin.RiNnoFinTelegramm.Services.TelegramBotClientWrapper wrapper) => _botWrapper = wrapper;

    public new IApplicationPaths ApplicationPaths { get; }

    IEnumerable<PluginPageInfo> IHasWebPages.GetPages()
    {
        return
        [
            new PluginPageInfo 
            { 
                Name = Name, 
                EmbeddedResourcePath = $"{typeof(RiNnoFinPlugin).Namespace}.Assets.Config.config.html",
                EnableInMainMenu = true,
                MenuIcon = "send"
            },
            new PluginPageInfo 
            { 
                Name = "RiNnoFinTelegramm", 
                EmbeddedResourcePath = $"{typeof(RiNnoFinPlugin).Namespace}.Assets.Config.config.html",
                EnableInMainMenu = false
            },
            new PluginPageInfo { Name = "RiNnoFinTelegramm_v10467.js", EmbeddedResourcePath = $"{typeof(RiNnoFinPlugin).Namespace}.Assets.Config.config.js" },
            new PluginPageInfo { Name = "RiNnoFinTelegramm.css", EmbeddedResourcePath = $"{typeof(RiNnoFinPlugin).Namespace}.Assets.Config.config.css" }
        ];
    }

    public override string Name => Constants.PluginName;

    public override Guid Id => Constants.Id;
}
