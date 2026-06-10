using System;
using System.Collections.Generic;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm;

public class RiNnoFinPlugin : BasePlugin<PluginConfiguration>, IPlugin, IHasWebPages, IDisposable
{
    private readonly ILibraryManager _libraryManager;
    private readonly NotificationService _notificationService;
    private readonly ILogger<RiNnoFinPlugin> _logger;

    public static MediaBrowser.Controller.Library.IUserManager? UserManager { get; private set; }
    public static MediaBrowser.Model.Cryptography.ICryptoProvider? CryptoProvider { get; private set; }

    public RiNnoFinPlugin(
        ILogger<RiNnoFinPlugin> logger,
        IApplicationPaths applicationPaths,
        IXmlSerializer xmlSerializer,
        ILibraryManager libraryManager,
        NotificationService notificationService,
        MediaBrowser.Controller.Library.IUserManager userManager,
        MediaBrowser.Model.Cryptography.ICryptoProvider cryptoProvider)
        : base(applicationPaths, xmlSerializer)
    {
        _logger = logger;
        ApplicationPaths = applicationPaths;
        Instance = this;
        UserManager = userManager;
        CryptoProvider = cryptoProvider;
        _libraryManager = libraryManager;
        _notificationService = notificationService;
        
        _libraryManager.ItemAdded += _notificationService.OnItemAdded;
        _libraryManager.ItemUpdated += _notificationService.OnItemUpdated;
        
        _logger.LogInformation("{PluginName} initialisiert.", nameof(RiNnoFinPlugin));
    }

    public static RiNnoFinPlugin? Instance { get; private set; }

    public ILibraryManager LibraryManager => _libraryManager;

    public new IApplicationPaths ApplicationPaths { get; }

    public void Dispose()
    {
        _libraryManager.ItemAdded -= _notificationService.OnItemAdded;
        _libraryManager.ItemUpdated -= _notificationService.OnItemUpdated;
        GC.SuppressFinalize(this);
    }

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
            new PluginPageInfo { Name = "RiNnoFinTelegramm_v10424.js", EmbeddedResourcePath = $"{typeof(RiNnoFinPlugin).Namespace}.Assets.Config.config.js" },
            new PluginPageInfo { Name = "RiNnoFinTelegramm.css", EmbeddedResourcePath = $"{typeof(RiNnoFinPlugin).Namespace}.Assets.Config.config.css" }
        ];
    }

    public override string Name => Constants.PluginName;

    public override Guid Id => Constants.Id;
}
