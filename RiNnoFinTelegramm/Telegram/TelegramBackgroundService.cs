using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.RiNnoFinTelegramm.Services;
using Jellyfin.Plugin.RiNnoFinTelegramm.Telegram.Commands;
using MediaBrowser.Model.Plugins;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Telegram;

public interface ICommandProvider
{
    ICommandBase[] GetCommands();
}

public class DefaultCommandProvider : ICommandProvider
{
    private readonly ICommandBase[] _commands;

    public DefaultCommandProvider()
    {
        _commands = GetType().Assembly.GetTypes()
            .Where(t =>
                typeof(ICommandBase).IsAssignableFrom(t) &&
                t is { IsClass: true, IsAbstract: false }
            )
            .Select(t => Activator.CreateInstance(t) as ICommandBase
                         ?? throw new Exception($"Fehler beim Initialisieren des Befehls: {t.FullName}"))
            .ToArray();
    }

    public ICommandBase[] GetCommands()
    {
        return _commands;
    }
}

public sealed class TelegramBackgroundService : IHostedService, IDisposable
{
    private readonly TelegramBotClientWrapper _botClientWrapper;
    private readonly ICommandBase[] _commands;
    private readonly ILogger<TelegramBackgroundService> _logger;
    private readonly RiNnoFinPlugin _plugin;
    private readonly IServiceProvider _serviceProvider;

    private TelegramBotService? _botService;
    private Timer? _inactivityTimer;
    private const int InactivityCheckIntervalMinutes = 30;
    private const int InactivityThresholdHours = 24;

    private string _currentToken = string.Empty;

    public TelegramBackgroundService(IServiceProvider serviceProvider, ILogger<TelegramBackgroundService> logger,
        TelegramBotClientWrapper botClientWrapper, ICommandProvider commandProvider)
    {
        _plugin = RiNnoFinPlugin.Instance ?? throw new ArgumentException("RiNnoFinPlugin Instanz ist null.");
        _logger = logger;
        _botClientWrapper = botClientWrapper;
        _serviceProvider = serviceProvider;

        _commands = commandProvider.GetCommands();
        var commandNames = _commands.Select(c => c.Command).ToArray();

        var duplicateCommands = commandNames
            .GroupBy(x => x.ToLower())
            .Where(g => g.Count() > 1)
            .Select(g => g.Key)
            .ToList();

        if (duplicateCommands.Any())
        {
            throw new InvalidOperationException(
                $"Doppelte Befehlsnamen gefunden: {string.Join(", ", duplicateCommands)}. " +
                "Jeder Befehl muss einen eindeutigen Namen haben.");
        }

        _logger.LogInformation("Registrierte '{Count}' Telegram-Bot-Befehle: [{CommandNames}]", _commands.Length, string.Join(", ", commandNames));
    }

    public void Dispose()
    {
        DisposeBotService();
        GC.SuppressFinalize(this);
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _plugin.ConfigurationChanged += OnConfigChange;

        ConfigureBot(_plugin.Configuration);

        _inactivityTimer = new Timer(
            CheckForInactivity,
            null,
            TimeSpan.FromMinutes(InactivityCheckIntervalMinutes),
            TimeSpan.FromMinutes(InactivityCheckIntervalMinutes));

        _logger.LogInformation("RiNnoFin Telegram-Hintergrunddienst gestartet");

        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _plugin.ConfigurationChanged -= OnConfigChange;

        DisposeBotService();

        _logger.LogInformation("RiNnoFin Telegram-Hintergrunddienst gestoppt");

        return Task.CompletedTask;
    }

    private void OnConfigChange(object? sender, BasePluginConfiguration baseConfig)
    {
        if (baseConfig is PluginConfiguration configuration)
        {
            _logger.LogInformation("Telegram-Bot-Konfiguration geändert. Konfiguriere neu...");
            ConfigureBot(configuration);
        }
        else
        {
            _logger.LogError("BasePluginConfiguration ist nicht vom Typ PluginConfiguration: {TypeName}", baseConfig.GetType().FullName);
        }
    }

    private void ConfigureBot(PluginConfiguration config)
    {
        var newToken = config.BotToken.Trim();
        if (!config.EnableBotService || string.IsNullOrWhiteSpace(newToken) || newToken.Equals(Constants.DefaultBotToken))
        {
            DisposeBotService();
            _logger.LogInformation("Telegram-Bot-Dienst deaktiviert, Token leer oder ungültig.");
            return;
        }

        if (newToken == _currentToken)
        {
            _logger.LogInformation("Telegram-Bot-Token ist unverändert. Konfiguration aktualisiert.");
            _botService?.UpdateConfig(config);
            return;
        }

        DisposeBotService();

        try
        {
            _botService = new TelegramBotService(_logger, newToken, config, _serviceProvider, _botClientWrapper, _commands);
            _botService.StartAsync().ConfigureAwait(false);
            _currentToken = newToken;
        }
        catch (Exception ex)
        {
            _logger.LogError("Fehler beim Konfigurieren des Telegram-Bot-Dienstes: {Msg}", ex.Message);
            DisposeBotService();
        }
    }

    private void CheckForInactivity(object? state)
    {
        if (_botService?.StartTime == null)
        {
            return;
        }

        var inactivityDuration = DateTime.UtcNow - _botService.LastActivityTime;
        if (inactivityDuration.TotalHours < InactivityThresholdHours)
        {
            return;
        }

        _logger.LogInformation(
            "Telegram-Bot war für {Hours} Stunden inaktiv. Reorganisation auslösen...",
            inactivityDuration.TotalHours);

        ConfigureBot(_plugin.Configuration);
    }

    private void DisposeBotService()
    {
        _inactivityTimer?.Dispose();
        _inactivityTimer = null;

        if (_botService != null)
        {
            _botService.Dispose();
            _botService = null;
            _logger.LogInformation("Telegram-Bot-Dienst freigegeben");
        }

        _currentToken = string.Empty;
    }
}
